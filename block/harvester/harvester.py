"""Symbol Harvester Extraction Utilities"""

from sys import path
import pathlib
# Hack to enable imports without building a proper package. Please forgive the heresy.
path.append(str(pathlib.Path(__file__).parent.parent.absolute()))

import pandas as pd
from state import XYMStateMap


def load_data(state_path,headers_path):
    state_map = XYMStateMap.read_msgpack(state_path)
    headers = pd.read_pickle(headers_path)
    dt_map = headers[['height']].reset_index().set_index('height')
    return state_map, dt_map


def get_balances(accounts,state_map,dt_map,use_name=True):
    balances = [dt_map]
    for a in accounts:
        name = a['name'] if use_name else a['address']
        b_series = pd.Series(state_map[a['address']]['xym_balance'],name=name,dtype=float)
        balances.append(b_series)
    return pd.concat(balances,axis=1).set_index('dateTime') / 1000000 # divide by one million to get units of XYM


def get_fees(accounts,state_map,dt_map,use_name=True):
    fees = [dt_map]
    for a in accounts:
        name = a['name'] if use_name else a['address']
        f_series = pd.Series(state_map[a['address']]['harvest_fees'],name=name,dtype=float)
        fees.append(f_series)
    return pd.concat(fees,axis=1).set_index('dateTime') / 1000000


def get_block_counts(accounts,state_map,dt_map,use_name=True):
    b_counts = [dt_map]
    for a in accounts:
        name = a['name'] if use_name else a['address']
        bc_series = pd.Series({x:1 for x in state_map[a['address']]['harvested'].keys()},name=name,dtype=float)
        b_counts.append(bc_series)
    return pd.concat(b_counts,axis=1).set_index('dateTime')