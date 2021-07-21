import os
import random

import yaml


def is_historical_node(node_descriptor):
    return 'historical' in node_descriptor and node_descriptor['historical']


class ResourceLoader:
    def __init__(self, network_prefix, resources_path=None):
        self.network_prefix = network_prefix

        if not resources_path:
            for search_directory in ['.', '..']:
                resources_path = os.path.join(search_directory, 'resources')
                if os.path.exists(resources_path):
                    break

        if not resources_path or not os.path.exists(resources_path):
            raise 'could not autodetect resources path'

        with open(os.path.join(resources_path, self._qualify('addresses.yaml')), 'r') as infile:
            self.account_descriptors = yaml.load(infile, Loader=yaml.SafeLoader)

        with open(os.path.join(resources_path, self._qualify('nodes.yaml')), 'r') as infile:
            self.node_descriptors = yaml.load(infile, Loader=yaml.SafeLoader)

    def get_descriptor_by_address(self, address):
        return next((descriptor for descriptor in self.account_descriptors if address == descriptor['address']), None)

    def get_account_descriptors(self, filter_type):
        return [descriptor for descriptor in self.account_descriptors if filter_type in descriptor['roles']]

    def get_random_node_host(self):
        return random.choice([descriptor for descriptor in self.node_descriptors if not is_historical_node(descriptor)])['host']

    def _qualify(self, filename):
        return '{}.{}'.format(self.network_prefix, filename)
