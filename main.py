import asyncio 
import json

from indy import pool, wallet, did, ledger
from indy.error import ErrorCode, IndyError




async def create_wallet(identity):
    print("\"{}\" -> Create wallet".format(identity['name']))
    try:
        await wallet.create_wallet(identity['wallet_config'],
                                   identity['wallet_credentials'])
    except IndyError as ex:
        if ex.error_code == ErrorCode.PoolLedgerConfigAlreadyExistsError:
            pass
        identity['wallet'] = await wallet.open_wallet(identity['wallet_config'],
                                                      identity['wallet_credentials'])


async def getting_verinym(from_, to):
    await create_wallet(to)

    (to['did'], to['key']) = await did.create_and_store_my_did(to['wallet'], "{}")

    from_['info'] = {
        'did': to['did'],
        'verkey': to['key'],
        'role': to['role'] or None
    }

    await send_nym(from_['pool'], from_['wallet'], from_['did'], from_['info']['did'],
                    from_['info']['verkey'], from_['info']['role'])

async def send_nym(pool_handle, wallet_handle, _did, new_did, new_key, role):
    nym_request = await ledger.build_nym_request(_did, new_did, new_key, None, role)
    print(nym_request)
    await ledger.sign_and_submit_request(pool_handle, wallet_handle, _did, nym_request)


async def run():
    print("Indy demo program")
    print("STEP 1")
    pool_ = {
        "name": "pool1"
    }

    print("Open Pool Ledger: {}".format(pool_['name']))
    pool_['genesis_txn_path'] = "pool1.txn"
    pool_['config'] = json.dumps({"genesis_txn": str(pool_['genesis_txn_path'])})

    print(pool_)

    # connect to the pool
    await pool.set_protocol_version(2)

    try:
        await pool.create_pool_ledger_config(pool_['name'], pool_['config'])
    except IndyError as ex:
        if ex.error_code == ErrorCode.PoolLedgerConfigAlreadyExistsError:
            pass
        pool_['handle'] = await pool.open_pool_ledger(pool_['name'], None)

        print(pool_['handle'])


        print("STEP 2 - Configuring steward")
        steward = {
            'name': "Sovrin Steward",
            'wallet_config': json.dumps({'id': 'sovrin_steward_wallet'}),
            'wallet_credentials': json.dumps({'key': 'steward_wallet_key'}),
            'pool': pool_['handle'],
            'seed': '000000000000000000000000Steward1'
        }
        print(steward)

        await create_wallet(steward)

        print(steward["wallet"])

        steward["did_info"] = json.dumps({'seed': steward['seed']})
        print(steward["did_info"])

        #did:demoindynetwork:Th7MpTaRZVRYnPiabds81Y
        steward['did'], steward['key'] = await did.create_and_store_my_did(steward['wallet'], steward['did_info '])

        print("STEP 3 - register DID for university and company")

        print("\n\n\n================================")
        print("==   theUniversity getting Verinym   ==")
        print('--------------------------------')

        theUniversity = {
            'name': 'theUniversity',
            'wallet_config': json.dumps({'id': 'theUniversity_wallet'}),
            'wallet_credentials': json.dumps({'key': 'theUniversity_wallet_key'}),
            'pool': pool_['handle'],
            'role': 'TRUST_ANCHOR'
        }

        await getting_verinym(steward, theUniversity)

        print("\n\n\n================================")
        print("==   theCompany getting Verinym   ==")
        print('--------------------------------')

        theCompany = {
            'name': 'theUniversity',
            'wallet_config': json.dumps({'id': 'theCompany_wallet'}),
            'wallet_credentials': json.dumps({'key': 'theCompany_wallet_key'}),
            'pool': pool_['handle'],
            'role': 'TRUST_ANCHOR'
        }

        await getting_verinym(steward, theCompany)  


    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())