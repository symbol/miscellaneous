#!/usr/bin/env python3
"""Symbol delegate identification script"""

import argparse
import json

from block.delegates.delegates import find_delegates
from block.extractor import XYMStateMap

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=str, default='resources/accounts.json', help='path to load node information from')
    parser.add_argument('--output', type=str, default='delegates/output/node_delegates.json', help='path to write delegates json')
    parser.add_argument('--state_path', type=str, default='resources/state_map.msgpack', help='path to load state map from')

    args = parser.parse_args()

    print(f'Reading state from {args.state_path}')
    state_map = XYMStateMap.read_msgpack(args.state_path)

    print(f'Reading nodes from {args.input}')
    with open(args.input, 'r') as f:
        accounts = json.loads(f.read())['accounts']

    print('Identifying delegates . . .')
    delegate_accounts = find_delegates(accounts, state_map)

    print(f'All accounts processed, writing output to {args.output}')
    with open(args.output, 'w') as f:
        f.write(json.dumps(delegate_accounts, indent=4))

    print('Delegate analysis complete!')
