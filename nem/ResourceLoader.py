from collections import namedtuple

import yaml
from symbolchain.core.AccountDescriptorRepository import AccountDescriptorRepository
from symbolchain.core.NodeDescriptorRepository import NodeDescriptorRepository

Resources = namedtuple('Resources', [
    'friendly_name', 'ticker_name', 'currency_symbol', 'ico_price', 'accounts', 'nodes'
])


def load_resources(resources_path):
    with open(resources_path, 'r') as infile:
        resources = yaml.load(infile, Loader=yaml.SafeLoader)
        return Resources(**{
            'friendly_name': resources['friendly_name'],
            'ticker_name': resources['ticker_name'],
            'currency_symbol': resources['currency_symbol'],
            'ico_price': resources['ico_price'],

            'accounts': AccountDescriptorRepository(resources['accounts']),
            'nodes': NodeDescriptorRepository(resources['nodes']),
        })
