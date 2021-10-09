"""Symbol Harvester Statistics Script"""

import argparse
import json
import os
from harvester import *


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--accounts_path", type=str, default='accounts.json', help="path to load accounts from")
    parser.add_argument("--state_path", type=str, default='state_map.msgpack', help="path to load state map from")
    parser.add_argument("--headers_path", type=str, default='block_header_df.pkl', help="path to load headers from")
    parser.add_argument("--output_path", type=str, default='output', help="path to write analyzed files to")
    parser.add_argument("--freq", type=str, default='D,W,M', help="comma-delimited list of frequencies to sample with no spaces; for options see https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#offset-aliases")
    
    args = parser.parse_args()

    print(f"Reading account information from {args.accounts_path}")
    with open(args.accounts_path,'r') as f:
        accounts = json.loads(f.read())['accounts']

    print(f"Loading chain data from {args.state_path} and {args.headers_path}")
    state_map, dt_map = load_data(args.state_path,args.headers_path)
    
    print("Analyzing blocks . . .")
    balance_df = get_balances(accounts,state_map,dt_map)
    fee_df = get_fees(accounts,state_map,dt_map)
    block_df = get_block_counts(accounts,state_map,dt_map)
    
    print(f"Writing files for frequencies {args.freq}")
    for freq in args.freq.split(','):
        balance_df.resample(freq).sum().cumsum().to_csv(
            os.path.join(args.output_path,f'account_balances_{freq}.csv'))
        fee_df.resample(freq).sum().to_csv(
            os.path.join(args.output_path,f'harvester_fees_{freq}.csv'))
        block_df.resample(freq).sum().to_csv(
            os.path.join(args.output_path,f'blocks_harvested_{freq}.csv'))

    print("Harvester analysis complete!")