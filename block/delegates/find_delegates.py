"""Symbol Delegate Identification Script"""

import argparse
import json
import pathlib
import os
from delegates import *


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes_path", type=str, default='node_accounts.json', help="path to load node information from")
    parser.add_argument("--out_path", type=str, default='node_delegates.json', help="path to load node information from")
    parser.add_argument("--state_path", type=str, default='state_map.msgpack', help="path to load state map from")
    
    args = parser.parse_args()

    print(f"Reading state from {args.state_path}")
    state_map = get_state_map(args.state_path)

    print(f"Reading nodes from {args.nodes_path}")
    with open(args.nodes_path,'r') as f:
        accounts = json.loads(f.read())['accounts']

    print("Identifying delegates . . .")
    delegate_accounts = find_delegates(accounts,state_map)
    
    print(f"All accounts processed, writing output to {args.out_path}")
    with open(args.out_path,'w') as f:
        f.write(json.dumps(delegate_accounts,indent=4))

    print("Delegate analysis complete!")