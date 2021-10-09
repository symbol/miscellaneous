"""Symbol Chain State Representation Module"""

import msgpack
import numpy as np
import networkx as nx
from binascii import unhexlify
from collections import defaultdict

from util import public_key_to_address

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

    def __init__(self,state_map={},account_map={}):
        
        if len(state_map):
            state_map = {k:{
                'xym_balance': defaultdict(lambda:0,v['xym_balance']),
                'harvest_fees': defaultdict(lambda:0,v['harvest_fees']),
                'delegation_requests': defaultdict(list,v['delegation_requests']),
                'vrf_key_link': defaultdict(list,v['vrf_key_link']),
                'node_key_link': defaultdict(list,v['node_key_link']),
                'account_key_link': defaultdict(list,v['account_key_link']),
                'harvested':defaultdict(list,v['harvested']),
                'delegated':defaultdict(list,v['delegated'])
            } for k,v in state_map.items()}

        self.state_map = defaultdict(lambda:{
                'xym_balance': defaultdict(lambda:0),
                'harvest_fees': defaultdict(lambda:0),
                'delegation_requests': defaultdict(list),
                'vrf_key_link': defaultdict(list),
                'node_key_link': defaultdict(list),
                'account_key_link': defaultdict(list),
                'harvested':defaultdict(list),
                'delegated':defaultdict(list)
            }, state_map)

        self.account_map = account_map

        self.tracked_mosaics = ['0x6bed913fa20223f8','0xe74b99ba41f4afee'] # only care about XYM for now, hardcoded alias
        self.node_color = 'CornflowerBlue'
        self.harvester_color = 'LightBlue'


    def __getitem__(self,addr):
        return self.state_map[addr]


    @classmethod
    def read_msgpack(cls,msgpack_path):
        """Read data from a mesgpack binary blob and build a state map"""
        if type(msgpack_path) == str:
            with open(msgpack_path,'rb') as f:
                state_map, account_map = msgpack.unpack(f,unicode_errors=None,raw=False)
        else:
            raise TypeError(f"Unrecognized type {type(msgpack_path)} for read_msgpack, path str")

        return cls(state_map=state_map,account_map=account_map)


    def to_dict(self):
        """Convert internal state map to serializable dictionary"""
        sm_dict = dict(self.state_map)
        for k, v in sm_dict.items():
            sm_dict[k] = dict(v)
            for kk, vv in v.items():
                sm_dict[k][kk] = dict(vv)
        return sm_dict


    def to_msgpack(self,msgpack_path):
        """Produce serialized blob with msgpack"""
        with open(msgpack_path, 'wb') as f:
            f.write(msgpack.packb((self.to_dict(),self.account_map)))


    def keys(self):
        """Produce a view of all addresses in the state map"""
        return self.state_map.keys()


    def values(self):
        """Produce a view of all address data in the state map"""
        return self.state_map.values()


    def insert_tx(self,tx,height,fee_multiplier):
        """Insert a transaction into the state map and record resulting changes
        
        Parameters
        ----------
        tx: dict
            Deserialized transaction
        height: int
            Height of transaction
        fee_multiplier: float
            Fee multiplier for transaction's containing block

        """

        # TODO: handle flows for *all* mosaics, not just XYM
        address = public_key_to_address(unhexlify(tx['signer_public_key']))
        
        if tx['type'] == b'4154': # transfer tx
            if len(tx['payload']['message']) and tx['payload']['message'][0] == 0xfe:
                self.state_map[address]['delegation_requests'][tx['payload']['recipient_address']].append(height)
            elif tx['payload']['mosaics_count'] > 0:
                for mosaic in tx['payload']['mosaics']:
                    if hex(mosaic['mosaic_id']) in self.tracked_mosaics:
                        self.state_map[address]['xym_balance'][height] -= mosaic['amount']
                        self.state_map[tx['payload']['recipient_address']]['xym_balance'][height] += mosaic['amount']
        
        elif tx['type'] in [b'4243',b'424c',b'414c']: # key link tx          
            if tx['type'] == b'4243': 
                link_key = 'vrf_key_link'
            elif tx['type'] == b'424c': 
                link_key = 'node_key_link'
            elif tx['type'] == b'414c': 
                link_key = 'account_key_link'
                self.account_map[public_key_to_address(tx['payload']['linked_public_key'])] = address
            if tx['payload']['link_action'] == 1:
                self.state_map[address][link_key][public_key_to_address(tx['payload']['linked_public_key'])].append([height,np.inf])
            else:
                self.state_map[address][link_key][public_key_to_address(tx['payload']['linked_public_key'])][-1][1] = height
        
        elif tx['type'] in [b'4141',b'4241']: # aggregate tx
            for sub_tx in tx['payload']['embedded_transactions']:
                self.insert_tx(sub_tx,height,None)
        
        if fee_multiplier is not None: # handle fees
            self.state_map[address]['xym_balance'][height] -= min(tx['max_fee'],tx['size']*fee_multiplier)


    def insert_rx(self,rx,height):
        """Insert a receipt into the state map and record resulting changes
        
        Parameters
        ----------
        rx: dict
            Deserialized receipt
        height: int
            Height of receipt

        """
    
        if rx['type'] in [0x124D, 0x134E]: # rental fee receipts
            if hex(rx['payload']['mosaic_id']) in ['0x6bed913fa20223f8','0xe74b99ba41f4afee']:
                self.state_map[rx['payload']['sender_address']]['xym_balance'][height] -= rx['payload']['amount']
                self.state_map[rx['payload']['recipient_address']]['xym_balance'][height] += rx['payload']['amount']
                
        elif rx['type'] in [0x2143,0x2248,0x2348,0x2252,0x2352]: # balance change receipts (credit)
            self.state_map[rx['payload']['target_address']]['xym_balance'][height] += rx['payload']['amount']
            if rx['type'] == 0x2143: # harvest fee
                self.state_map[rx['payload']['target_address']]['harvest_fees'][height] += rx['payload']['amount']
            
        elif rx['type'] in [0x3148,0x3152]: # balance change receipts (debit)
            self.state_map[rx['payload']['target_address']]['xym_balance'][height] -= rx['payload']['amount']
        
        if rx['type'] == 0xE143: # aggregate receipts
            for sub_rx in rx['receipts']:
                self.insert_rx(sub_rx,height)


    def insert_block(self,block):
        """Insert a block into the state map and record resulting changes
        
        Parameters
        ----------
        block: dict
            Deserialized block

        """
        header = block['header']
        height = header['height']

        # handle harvester information
        harvester = header['harvester']
        if harvester in self.account_map:
            harvester = self.account_map[harvester]

        self.state_map[harvester]['harvested'][height] = header['beneficiary_address']
        if harvester != header['beneficiary_address']:
            self.state_map[header['beneficiary_address']]['delegated'][height] = harvester

        # handle transactions
        for tx in block['footer']['transactions']:
            self.insert_tx(tx,height,header['fee_multiplier'])

    
    def get_harvester_graph(self,height=np.inf,min_harvester_size=10000, min_node_size=10000, track_remote=False):
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
        """
        harvester_map = {}
        node_map = defaultdict(list)
        
        for k,v in self.state_map.items():
            balance = sum([x for h,x in v['xym_balance'].items() if h <= height]) / 1e6
            if balance >= min_harvester_size:
                curr_node = None
                link_start = 0
                for addr,links in v['node_key_link'].items():
                    for link in links:
                        if link[0] <= height <= link[1]:
                            curr_node = addr
                            link_start = link[0]
                            break
                        else:
                            link_start = max(link_start, link[1])
                    if curr_node is not None:
                        break

                num_h = sum(map(lambda x:int(link_start<=x<=height),v['harvested'].keys()))
                min_height = min(v['xym_balance'].keys())
                
                if curr_node is None: # not currently a delegated harvester, no node key link
                    if track_remote:
                        if num_h > 0:
                            harvester_map[k] = {'type':'remote_harvester','color':self.harvester_color,'balance':balance,'size':np.sqrt(balance),'link_age':height-link_start,'min_height':min_height}
                            # node_map[k].append((k,balance,height-link_start))
                else:
                    harvester_map[k] = {'type':'delegated_harvester','color':self.harvester_color,'balance':balance,'size':np.sqrt(balance),'link_age':height-link_start,'min_height':min_height}
                    node_map[curr_node].append((k,balance,height-link_start,link_start))

        graph = nx.DiGraph()
        graph.add_nodes_from(harvester_map.items())
        graph.add_nodes_from([
            (k,{'type':'node',
                'color':self.node_color,
                'balance':sum([x[1] for x in v]),
                'size':np.sqrt(sum([x[1] for x in v])),
                'link_age':np.mean([[x[2] for x in v]]),
                'min_height':min([x[3] for x in v])}) 
            for k,v in node_map.items()
            if sum([x[1] for x in v]) >= min_node_size])
        
        for node,delegates in node_map.items():
            graph.add_edges_from([(node,d[0],{'link_age':d[2]}) for d in delegates])
        
        return graph


    def get_harvester_bubbles(self,min_height=0,max_height=np.inf,min_harvester_size=1,min_delegate_size=1):
        """Produce a bubble chart representing harvester-node relationships for a range of network heights
           
        Parameters
        ----------
        min_height: int
            Height at which to begin recording harvesting signatures
        max_height: int
            Height 
        min_harvester_size: int, optional
        min_delegate_size: int, optional
            
        """
        harvester_map = defaultdict(lambda:[])
        
        for k,v in self.state_map.items():
            for height, addr in v['harvested'].items():
                if min_height <= height <= max_height:
                    harvester_map[k].append(addr)

        delegate_map = defaultdict(lambda:[])
    
        for k,v in self.state_map.items():
            for height, addr in v['delegated'].items():
                if min_height <= height <= max_height:
                    delegate_map[k].append(addr)
        
        harvester_size_map = {k:{'size':len(v),'color':self.node_color, 'type': 'node'} for k,v in harvester_map.items() if len(v) >= min_harvester_size}
        delegate_size_map = {k:{'size':len(v),'color':self.harvester_color, 'parent': max(set(v), key = v.count), 'type': 'delegate'} for k,v in delegate_map.items() if len(v) >= min_delegate_size}

        graph = nx.Graph()
        graph.add_nodes_from(harvester_size_map.items())
        graph.add_nodes_from(delegate_size_map.items())
        
        return graph


if __name__ == "__main__":
    print("Nothing to do here; if you need to build a state map use extractor!")