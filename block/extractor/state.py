"""Symbol Chain State Representation Module"""

from binascii import unhexlify
from collections import defaultdict
import msgpack
import networkx as nx
import numpy as np
import pandas as pd
from block.extractor.util import public_key_to_address


class XYMStateMap():
    """Efficient, mutable representation of XYM network state

    Parameters
    ----------
    state_map: dict, optional
        Pre-existing state map to initialize internal state

    Attributes
    ----------
    state_map: defaultdict
        Dict mapping addresses to recorded quantities
    tracked_mosaics: list[str]
        List of string aliases for mosaic(s) to track the balance of

    """

    def __init__(self, state_map=None, account_map=None):

        if state_map is None:
            state_map = {}

        if account_map is None:
            account_map = {}

        if len(state_map):
            state_map = {key: {
                'xym_balance': defaultdict(lambda: 0, val['xym_balance']),
                'harvest_fees': defaultdict(lambda: 0, val['harvest_fees']),
                'delegation_requests': defaultdict(list, val['delegation_requests']),
                'vrf_key_link': defaultdict(list, val['vrf_key_link']),
                'node_key_link': defaultdict(list, val['node_key_link']),
                'account_key_link': defaultdict(list, val['account_key_link']),
                'harvested': defaultdict(list, val['harvested']),
                'delegated': defaultdict(list, val['delegated'])
            } for key, val in state_map.items()}

        self._state_map = defaultdict(lambda: {
                'xym_balance': defaultdict(lambda: 0),
                'harvest_fees': defaultdict(lambda: 0),
                'delegation_requests': defaultdict(list),
                'vrf_key_link': defaultdict(list),
                'node_key_link': defaultdict(list),
                'account_key_link': defaultdict(list),
                'harvested': defaultdict(list),
                'delegated': defaultdict(list)
            }, state_map)

        # TODO: invertible account map
        self._account_map = account_map

        self._height_ts_map = {}

        self.tracked_mosaics = ['0x6bed913fa20223f8', '0xe74b99ba41f4afee']  # only care about XYM for now, hardcoded alias
        self.node_color = 'CornflowerBlue'
        self.harvester_color = 'LightBlue'

    def __getitem__(self, addr):
        return self._state_map[addr]

    @classmethod
    def read_msgpack(cls, msgpack_path):
        """Read data from a mesgpack binary blob and build a state map"""
        if isinstance(msgpack_path, str):
            with open(msgpack_path, 'rb') as file:
                state_map, account_map = msgpack.unpack(file, unicode_errors=None, raw=False)
        else:
            raise TypeError(f'Unrecognized type {type(msgpack_path)} for read_msgpack, path str')

        return cls(state_map=state_map, account_map=account_map)

    def to_dict(self):
        """Convert internal state map to serializable dictionary"""
        sm_dict = dict(self._state_map)
        for key, val in sm_dict.items():
            sm_dict[key] = dict(val)
            for subkey, subval in val.items():
                sm_dict[key][subkey] = dict(subval)
        return sm_dict

    def to_msgpack(self, msgpack_path):
        """Produce serialized blob with msgpack"""
        with open(msgpack_path, 'wb') as file:
            file.write(msgpack.packb((self.to_dict(), self._account_map)))

    def keys(self):
        """Produce a view of all addresses in the state map"""
        return self._state_map.keys()

    def values(self):
        """Produce a view of all address data in the state map"""
        return self._state_map.values()

    def items(self):
        """Produce a list of tuples containing addresses and data"""
        return self._state_map.items()

    def insert_txn(self, txn, height, fee_multiplier):
        """Insert a transaction into the state map and record resulting changes

        Parameters
        ----------
        txn: dict
            Deserialized transaction
        height: int
            Height of transaction
        fee_multiplier: float
            Fee multiplier for transaction's containing block

        """

        # TODO: handle flows for *all* mosaics, not just XYM
        address = public_key_to_address(unhexlify(txn['signer_public_key']))

        if txn['type'] == b'4154':  # transfer txn
            if len(txn['payload']['message']) and txn['payload']['message'][0] == 0xfe:
                self._state_map[address]['delegation_requests'][txn['payload']['recipient_address']].append(height)
            elif txn['payload']['mosaics_count'] > 0:
                for mosaic in txn['payload']['mosaics']:
                    if hex(mosaic['mosaic_id']) in self.tracked_mosaics:
                        self._state_map[address]['xym_balance'][height] -= mosaic['amount']
                        self._state_map[txn['payload']['recipient_address']]['xym_balance'][height] += mosaic['amount']

        elif txn['type'] in [b'4243', b'424c', b'414c']:  # key link txn
            if txn['type'] == b'4243':
                link_key = 'vrf_key_link'
            elif txn['type'] == b'424c':
                link_key = 'node_key_link'
            elif txn['type'] == b'414c':
                link_key = 'account_key_link'
                self._account_map[public_key_to_address(txn['payload']['linked_public_key'])] = address
            if txn['payload']['link_action'] == 1:
                self._state_map[address][link_key][public_key_to_address(txn['payload']['linked_public_key'])].append([height, np.inf])
            else:
                self._state_map[address][link_key][public_key_to_address(txn['payload']['linked_public_key'])][-1][1] = height

        elif txn['type'] in [b'4141', b'4241']:  # aggregate txn
            for sub_txn in txn['payload']['embedded_transactions']:
                self.insert_txn(sub_txn, height, None)

        if fee_multiplier is not None:  # handle fees
            self._state_map[address]['xym_balance'][height] -= min(txn['max_fee'], txn['size']*fee_multiplier)

    def insert_rcpt(self, rcpt, height):
        """Insert a receipt into the state map and record resulting changes

        Parameters
        ----------
        rcpt: dict
            Deserialized receipt
        height: int
            Height of receipt

        """

        if rcpt['type'] in [0x124D, 0x134E]:  # rental fee receipts
            if hex(rcpt['payload']['mosaic_id']) in ['0x6bed913fa20223f8', '0xe74b99ba41f4afee']:
                self._state_map[rcpt['payload']['sender_address']]['xym_balance'][height] -= rcpt['payload']['amount']
                self._state_map[rcpt['payload']['recipient_address']]['xym_balance'][height] += rcpt['payload']['amount']

        elif rcpt['type'] in [0x2143, 0x2248, 0x2348, 0x2252, 0x2352]:  # balance change receipts (credit)
            self._state_map[rcpt['payload']['target_address']]['xym_balance'][height] += rcpt['payload']['amount']
            if rcpt['type'] == 0x2143:  # harvest fee
                self._state_map[rcpt['payload']['target_address']]['harvest_fees'][height] += rcpt['payload']['amount']

        elif rcpt['type'] in [0x3148, 0x3152]:  # balance change receipts (debit)
            self._state_map[rcpt['payload']['target_address']]['xym_balance'][height] -= rcpt['payload']['amount']

        if rcpt['type'] == 0xE143:  # aggregate receipts
            for sub_rcpt in rcpt['receipts']:
                self.insert_rcpt(sub_rcpt, height)

    def insert_block(self, block):
        """Insert a block into the state map and record resulting changes

        Parameters
        ----------
        block: dict
            Deserialized block

        """
        header = block['header']
        height = header['height']
        self._height_ts_map[height] = pd.to_datetime(header['timestamp'], origin=pd.to_datetime('2021-03-16 00:06:25'), unit='ms')

        # handle harvester information
        harvester = header['harvester']
        if harvester in self._account_map:
            harvester = self._account_map[harvester]

        self._state_map[harvester]['harvested'][height] = header['beneficiary_address']
        if harvester != header['beneficiary_address']:
            self._state_map[header['beneficiary_address']]['delegated'][height] = harvester

        # handle transactions
        for txn in block['footer']['transactions']:
            self.insert_txn(txn, height, header['fee_multiplier'])

    def get_balance_series(self, address, freq=None):
        """Produce a time-series representing xym balance for a given address

        Parameters
        ----------
        address: str
            Size (in XYM) below which harvesters are ignored
        freq: str, optional
            Frequency at which balance series should be resampled

        Returns
        -------
        balance_series: pandas.Series
            Series with balances in XYM and a datetime index
        """
        b_series = pd.Series({self._height_ts_map[k]: v for k, v in self[address]['xym_balance'].items()}, dtype=float)
        if freq is not None:
            b_series = b_series.resample(freq).sum()
        return b_series / 1000000  # divide by one million to get units of XYM

    def get_harvester_graph(self, height=np.inf, min_harvester_size=10000, min_node_size=10000, track_remote=False):
        """Produce a graph representing harvester-node relationships for a range of network heights

        Parameters
        ----------
        height: int
            Height at which to represent harvester connections
        min_harvester_size: int, optional
            Size (in XYM) below which harvesters are ignored
        min_node_size: int, optional
            Size (in XYM, representing total delegated harvester balance) below which nodes are ignored
        track_remote: bool
            Determines whether remote harvesters (i.e. non-delegated harvesters) should be tracked

        Returns
        -------
        harvester_graph: networkx.DiGraph
            Graph in which addresses are represented as nodes and edges represent a delegated harvesting relationship
        """
        harvester_map = {}
        node_map = defaultdict(list)

        for key, val in self._state_map.items():
            balance = sum([x for h, x in val['xym_balance'].items() if h <= height]) / 1e6
            if balance >= min_harvester_size:
                curr_node = None
                link_start = 0
                for addr, links in val['node_key_link'].items():
                    for link in links:
                        if link[0] <= height <= link[1]:
                            curr_node = addr
                            link_start = link[0]
                            break
                        link_start = max(link_start, link[1])
                    if curr_node is not None:
                        break

                num_h = sum(map(lambda x: int(link_start <= x <= height), val['harvested'].keys()))
                min_height = min(val['xym_balance'].keys())

                if curr_node is None:  # not currently a delegated harvester, no node key link
                    if track_remote:
                        if num_h > 0:
                            harvester_map[key] = {
                                'type': 'remote_harvester',
                                'color': self.harvester_color,
                                'balance': balance, 'size': np.sqrt(balance),
                                'link_age': height-link_start,
                                'min_height': min_height}
                            # node_map[k].append((k, balance, height-link_start))
                else:
                    harvester_map[key] = {
                        'type': 'delegated_harvester',
                        'color': self.harvester_color,
                        'balance': balance,
                        'size': np.sqrt(balance),
                        'link_age': height-link_start,
                        'min_height': min_height}
                    node_map[curr_node].append((key, balance, height-link_start, link_start))

        graph = nx.DiGraph()
        graph.add_nodes_from(harvester_map.items())
        graph.add_nodes_from([
            (k, {
                'type': 'node',
                'color': self.node_color,
                'balance': sum([x[1] for x in v]),
                'size': np.sqrt(sum([x[1] for x in v])),
                'link_age': np.mean([[x[2] for x in v]]),
                'min_height': min([x[3] for x in v])})
            for k, v in node_map.items()
            if sum([x[1] for x in v]) >= min_node_size])

        for node, delegates in node_map.items():
            graph.add_edges_from([(node, d[0], {'link_age': d[2]}) for d in delegates])

        return graph

    def get_harvester_bubbles(self, min_height=0, max_height=np.inf, min_harvester_size=1, min_delegate_size=1):
        """Produce a bubble chart representing harvester-node relationships for a range of network heights

        Parameters
        ----------
        min_height: int
            Height at which to begin recording harvesting signatures
        max_height: int
            Height at which to stop recording harvesting signatures
        min_harvester_size: int, optional
        min_delegate_size: int, optional

        Returns
        -------
        bubble_graph: networkx.Graph
            Graph in which addresses are represented as nodes and parent attributes represent a delegated harvesting relationship
        """
        harvester_map = defaultdict(lambda: [])

        for key, val in self._state_map.items():
            for height, addr in val['harvested'].items():
                if min_height <= height <= max_height:
                    harvester_map[key].append(addr)

        delegate_map = defaultdict(lambda: [])

        for key, val in self._state_map.items():
            for height, addr in val['delegated'].items():
                if min_height <= height <= max_height:
                    delegate_map[key].append(addr)

        harvester_size_map = {k: {
                'size': len(v),
                'color': self.node_color,
                'type': 'node'}
            for k, v in harvester_map.items() if len(v) >= min_harvester_size}

        delegate_size_map = {k: {
                'size': len(v),
                'color': self.harvester_color,
                'parent': max(set(v), key=v.count),
                'type': 'delegate'}
            for k, v in delegate_map.items() if len(v) >= min_delegate_size}

        graph = nx.Graph()
        graph.add_nodes_from(harvester_size_map.items())
        graph.add_nodes_from(delegate_size_map.items())

        return graph


if __name__ == '__main__':
    print('Nothing to do here; if you need to build a state map use extract.py!')
