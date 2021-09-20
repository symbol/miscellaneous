import random
from collections import namedtuple

import yaml
from symbolchain.core.AccountDescriptorRepository import AccountDescriptorRepository
from symbolchain.core.NodeDescriptorRepository import NodeDescriptorRepository

from .NemClient import NemClient
from .SymbolClient import SymbolClient

Resources = namedtuple('Resources', [
    'friendly_name', 'ticker_name', 'currency_symbol', 'premarket_price', 'accounts', 'nodes'
])


def load_resources(resources_path):
    with open(resources_path, 'r') as infile:
        resources = yaml.load(infile, Loader=yaml.SafeLoader)
        return Resources(**{
            'friendly_name': resources['friendly_name'],
            'ticker_name': resources['ticker_name'],
            'currency_symbol': resources['currency_symbol'],
            'premarket_price': resources['premarket_price'],

            'accounts': AccountDescriptorRepository(resources['accounts']),
            'nodes': NodeDescriptorRepository(resources['nodes']),
        })


def create_blockchain_api_client(resources, node_role=None):
    node_host = random.choice(resources.nodes.find_all_by_role(node_role)).host
    return NemClient(node_host) if 'nem' == resources.friendly_name else SymbolClient(node_host)
