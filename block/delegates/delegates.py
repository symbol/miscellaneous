"""Symbol Delegate Mapping Utilities"""

from sys import path
import pathlib
# A hack to enable imports without building a proper package. Please forgive the heresy.
path.append(str(pathlib.Path(__file__).parent.parent.absolute()))

from state import XYMStateMap
from util import *
import requests
from binascii import unhexlify


def get_state_map(path):
    return XYMStateMap.read_msgpack(path)


def find_delegates(accounts,state_map):
    """Find current delegates for each node based on chain state at final height"""
    # TODO: add the ability to specify a height

    accounts = accounts.copy()
    for acc in accounts:
        if 'nodePublicKey' in acc:
            node_address = public_key_to_address(unhexlify(acc['nodePublicKey']))
        else:
            print("No node public key present, trying to collect from API")
            try:
                node_key = requests.get(f"http://{acc['name']}:3000/node/info").json()['nodePublicKey']
                node_address = public_key_to_address(unhexlify(node_key))
            except:
                print(f"Failed to retrieve node address, skipping node: {acc['name']}")
                continue

        # initialize delegates with node address
        valid_delegates = [acc['address']]
        invalid_delegates = []

        for k,v in state_map.state_map.items():
            if node_address in v['node_key_link']:
                if v['node_key_link'][node_address][-1][1] == float('inf'):
                    if sum(v['xym_balance'].values()) >= (10000 * 1e6):
                        valid_delegates.append(k)
                    else:
                        invalid_delegates.append(k)
        acc.update({
            'node_address':node_address,
            'valid_delegates':valid_delegates,
            'invalid_delegates':invalid_delegates
        })
    return accounts
