import asyncio
import json
import indy_sdk, indy
from indy_sdk import ledger, did, pairwise

# create pool ledger configuration
pool_handle = indy_sdk.pool.create_pool_ledger_config('pool1', '{"genesis_txn": "path/to/genesis_txn"}')

# create wallet
wallet_handle = indy_sdk.wallet.create_wallet('wallet1', None, None, None, 'default')
indy_sdk.wallet.open_wallet('wallet1', None, None)

# define consent schema for vc
consent_schema_name = "consent"
consent_schema_version = "1.0"
consent_schema_attributes = ["user_id", "data_type", "recipient_id", "consent_given"]
consent_schema_id, consent_schema = indy_sdk.anoncreds.issuer_create_schema("Issuer1", consent_schema_name, consent_schema_version, consent_schema_attributes)

#  create & store consent credential definition
consent_cred_def_config = {'tag': 'default'}
consent_cred_def = indy_sdk.anoncreds.issuer_create_and_store_credential_def(wallet_handle, 'Issuer1', consent_schema, 'CL', json.dumps(consent_cred_def_config))
consent_cred_def_id = consent_cred_def['id']

# function to give consent
async def give_consent(user_id, data_type, recipient_id):
    user_did, user_key = await did.create_and_store_my_did(wallet_handle, "{}")
    recipient_did, recipient_key = await did.create_and_store_my_did(wallet_handle, "{}")
    pairwise_config = json.dumps({'my_did': user_did, 'their_did': recipient_did})
    await pairwise.create_pairwise(wallet_handle, pairwise_config)

    consent_record = {
        "user_id": user_id,
        "data_type": data_type,
        "recipient_id": recipient_id,
        "consent_given": True
    }

    consent_record_json = json.dumps(consent_record)
    pool_handle = await indy_sdk.pool.open_pool_ledger('pool1', None)

    cred_offer = await indy_sdk.anoncreds.issuer_create_credential_offer(wallet_handle, consent_cred_def_id)
    send_cred_offer(recipient_id, cred_offer)
    
    cred_req, cred_req_metadata = await indy_sdk.anoncreds.prover_create_credential_req(wallet_handle, user_did, cred_offer, consent_cred_def, "{}")
    cred_values = json.dumps({"attributes": consent_record})
    cred, _, _ = await indy_sdk.anoncreds.issuer_create_credential(wallet_handle, cred_offer, cred_req, cred_values, None, None)
    await indy_sdk.anoncreds.prover_store_credential(wallet_handle, None, cred_req_metadata, cred, consent_cred_def, "{}")

    # Write the consent record onto the Indy blockchain
    credential_request = {
        'operation': {
            'type': '101',
            'config': {
                'data': json.loads(cred),
                'source_id': user_id
            }
        }
    }
    credential_request_json = json.dumps(credential_request)
    credential_response = await indy_sdk.ledger.sign_and_submit_request(pool_handle, wallet_handle, user_did, credential_request_json)

# function to revoke consent
async def revoke_consent(user_id, data_type, recipient_id):
    (user_did, user_key), (recipient_did, recipient_key) = await get_pairwise_dids(wallet_handle, recipient_id)
    # Modified consent record to change the attribute consent_given to false
    consent_record = {
        "user_id": user_id,
        "data_type": data_type,
        "recipient_id": recipient_id,
        "consent_given": False
    }
    consent_record_json = json.dumps(consent_record)

    cred_offer = await indy_sdk.anoncreds.issuer_create_credential_offer(wallet_handle, consent_cred_def_id)

    await send_cred_offer(recipient_id, cred_offer)

    cred_req, cred_req_metadata = await indy_sdk.anoncreds.prover_create_credential_req(wallet_handle, user_did, cred_offer, consent_cred_def, "{}")
    cred_values = json.dumps({"attributes": consent_record})
    cred, _, _ = await indy_sdk.anoncreds.issuer_create_credential(wallet_handle, cred_offer, cred_req, cred_values, None, None)
    await indy_sdk.anoncreds.prover_store_credential(wallet_handle, None, cred_req_metadata, cred, consent_cred_def, "{}")
    
    # Revoke the pairwise connection
    pairwise_config = json.dumps({'my_did': user_did, 'their_did': recipient_did})
    await pairwise.delete_pairwise(wallet_handle, pairwise_config)

# function to check if consent has been given to third parties for data exchange 
async def check_consent(user_id, data_type, recipient_id):
    (user_did, user_key), (recipient_did, recipient_key) = await get_pairwise_dids(wallet_handle, recipient_id)
    
    # Get the credential for given user, datatype and recipient
    cred_search_handle = await indy_sdk.anoncreds.prover_search_credentials_for_proof_req(wallet_handle, json.dumps({
        "name": "consent",
        "version": "1.0",
        "requested_attributes": {
            "attr1_referent": {"name": "user_id", "restrictions": [{"issuer_did": "Issuer1"}]},
            "attr2_referent": {"name": "data_type", "restrictions": [{"issuer_did": "Issuer1"}]},
            "attr3_referent": {"name": "recipient_id", "restrictions": [{"issuer_did": "Issuer1"}]},
            "attr4_referent": {"name": "consent_given", "restrictions": [{"issuer_did": "Issuer1"}]}
        }   
    }))

    # Search for the credential that matches the given user_id, data_type, and recipient_id
    cred_id = None
    while True:
        (cred_for_attr, cred_id, _) = await indy_sdk.anoncreds.prover_fetch_credentials_for_proof_req(cred_search_handle, "attr1_referent", 1)
        if not cred_for_attr:
            break
        for value in json.loads(cred_for_attr[0]['cred_info']['attrs']['attr2_referent']):
            if value == data_type:
                for value in json.loads(cred_for_attr[0]['cred_info']['attrs']['attr3_referent']):
                    if value == recipient_id:
                        cred_id = cred_for_attr[0]['cred_info']['referent']
                        break
        if cred_id:
            break

    # Close the search handle
    await indy_sdk.anoncreds.prover_close_credentials_search_for_proof_req(cred_search_handle)

    if not cred_id:
        return False

    # Get the credential and check if consent was given
    cred = await indy_sdk.anoncreds.prover_get_credential(wallet_handle, cred_id)
    cred_values = json.loads(cred['values'])
    return cred_values['attributes']['attr4_referent'] == "True"