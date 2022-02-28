"""Symbol delegate mapping utilities"""

from binascii import unhexlify

import requests

from block.extractor import public_key_to_address


def find_delegates(accounts, state_map):
    """Find current delegates for each node based on chain state at final height"""
    # TODO: add the ability to specify a height

    accounts = accounts.copy()
    for acc in accounts:
        if 'nodePublicKey' in acc:
            node_address = public_key_to_address(unhexlify(acc['nodePublicKey']))
        else:
            print('No node public key present, trying to collect from API')
            try:
                node_key = requests.get(f'http://{acc["name"]}:3000/node/info').json()['nodePublicKey']
                node_address = public_key_to_address(unhexlify(node_key))
            except requests.exceptions.ConnectionError:
                print(f'Failed to connect, skipping node: {acc["name"]}')
                continue

        # initialize delegates with node address
        valid_delegates = [acc['address']]
        invalid_delegates = []

        for key, val in state_map.items():
            if node_address in val['node_key_link']:
                if val['node_key_link'][node_address][-1][1] == float('inf'):
                    if sum(val['xym_balance'].values()) >= (10000 * 1e6):
                        valid_delegates.append(key)
                    else:
                        invalid_delegates.append(key)
        acc.update({
            'node_address': node_address,
            'valid_delegates': valid_delegates,
            'invalid_delegates': invalid_delegates
        })
    return accounts
