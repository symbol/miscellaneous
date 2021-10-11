"""Symbol Harvester Extraction Utilities"""

import pandas as pd
from block.extractor import XYMStateMap


def load_data(state_path, headers_path):
    state_map = XYMStateMap.read_msgpack(state_path)
    headers = pd.read_pickle(headers_path)
    dt_map = headers[['height']].reset_index().set_index('height')
    return state_map, dt_map


def get_balances(accounts, state_map, dt_map, use_name=True):
    balances = [dt_map]
    for acc in accounts:
        name = acc['name'] if use_name else acc['address']
        b_series = pd.Series(state_map[acc['address']]['xym_balance'], name=name, dtype=float)
        balances.append(b_series)
    return pd.concat(balances, axis=1).set_index('dateTime') / 1000000  # divide by one million to get units of XYM


def get_fees(accounts, state_map, dt_map, use_name=True):
    fees = [dt_map]
    for acc in accounts:
        name = acc['name'] if use_name else acc['address']
        f_series = pd.Series(state_map[acc['address']]['harvest_fees'], name=name, dtype=float)
        fees.append(f_series)
    return pd.concat(fees, axis=1).set_index('dateTime') / 1000000


def get_block_counts(accounts, state_map, dt_map, use_name=True):
    b_counts = [dt_map]
    for acc in accounts:
        name = acc['name'] if use_name else acc['address']
        bc_series = pd.Series({x: 1 for x in state_map[acc['address']]['harvested'].keys()}, name=name, dtype=float)
        b_counts.append(bc_series)
    return pd.concat(b_counts, axis=1).set_index('dateTime')
