import argparse
import csv
import json
import random
import time
from collections import namedtuple
from threading import Lock, Thread

from symbolchain.core.CryptoTypes import PublicKey
from symbolchain.core.facade.NemFacade import NemFacade
from zenlog import log

from client.ResourceLoader import create_blockchain_api_client, load_resources, locate_blockchain_client_class

NodeDescriptor = namedtuple('NodeDescriptor', ['name', 'host', 'version'])


class HarvesterDescriptor:
    def __init__(self):
        self.signer_public_key = None
        self.signer_address = None
        self.main_public_key = None
        self.main_address = None
        self.balance = 0


class BatchDownloader:
    # pylint: disable=too-many-instance-attributes

    def __init__(self, resources, facade, thread_count, height_range):
        self.resources = resources
        self.facade = facade
        self.thread_count = thread_count
        self.min_height = height_range[0]
        self.max_height = height_range[1]
        self.next_height = self.min_height

        self.api_clients = []
        self.public_key_to_descriptor_map = {}
        self.lock = Lock()

    def download_all(self):
        for node_descriptor in self.resources.nodes.find_all_not_by_role('seed-only'):
            self.api_clients.append(locate_blockchain_client_class(self.resources)(node_descriptor.host, timeout=60, retry_post=True))

        log.info('starting {} harvester download threads [{}, {}]'.format(self.thread_count, self.min_height, self.max_height))
        threads = [Thread(target=self._download_thread) for i in range(0, self.thread_count)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

    def _download_thread(self):
        while True:
            with self.lock:
                height = self.next_height
                if height > self.max_height:
                    time.sleep(2)
                    break

                self.next_height += 1

            api_client = random.choice(self.api_clients)

            log.debug('processing block at {} [{} remaining, {} unique harvesters]'.format(
                height,
                self.max_height - height,
                len(self.public_key_to_descriptor_map)))
            signer_public_key = api_client.get_harvester_signer_public_key(height)

            with self.lock:
                if signer_public_key in self.public_key_to_descriptor_map:
                    continue

                self.public_key_to_descriptor_map[signer_public_key] = None

            signer_address = self.facade.network.public_key_to_address(PublicKey(signer_public_key))
            (main_address, main_public_key, balance) = self._get_balance_follow_links(api_client, signer_address)

            log.debug('signer {} is linked to {} with balance {}'.format(signer_address, main_address, balance))

            descriptor = HarvesterDescriptor()
            descriptor.signer_public_key = signer_public_key
            descriptor.signer_address = signer_address
            descriptor.main_public_key = main_public_key
            descriptor.main_address = main_address
            descriptor.balance = balance

            with self.lock:
                self.public_key_to_descriptor_map[signer_public_key] = descriptor

    @staticmethod
    def _get_balance_follow_links(api_client, address):
        account_info = api_client.get_account_info(address)

        if 'REMOTE' == account_info.remote_status:
            account_info = api_client.get_account_info(address, forwarded=True)

        return (account_info.address, account_info.public_key, account_info.balance)


class HarvesterDownloader:
    def __init__(self, resources, network, num_blocks, nodes_input_filepath):
        self.resources = resources
        self.network = network
        self.num_blocks = num_blocks
        self.nodes_input_filepath = nodes_input_filepath

        self.peers_map = {}

    def download(self, thread_count, output_filepath):
        self._build_peers_map()

        log.info('downloading harvester activity to {} for last {} blocks'.format(output_filepath, self.num_blocks))

        chain_height = create_blockchain_api_client(self.resources).get_chain_height()
        log.info('chain height is {}'.format(chain_height))

        log.info('processing {} blocks starting at {}'.format(self.num_blocks, chain_height))

        batch_downloader = BatchDownloader(
            self.resources,
            NemFacade(self.network),
            thread_count,
            (max(1, chain_height - self.num_blocks + 1), chain_height))
        batch_downloader.download_all()

        with open(output_filepath, 'w') as outfile:
            column_names = ['signer_address', 'main_address', 'host', 'name', 'balance', 'version']
            csv_writer = csv.DictWriter(outfile, column_names)
            csv_writer.writeheader()

            for harvester_descriptor in batch_downloader.public_key_to_descriptor_map.values():
                node_descriptor = self.peers_map.get(harvester_descriptor.main_public_key, NodeDescriptor('', '', ''))

                csv_writer.writerow({
                    'signer_address': harvester_descriptor.signer_address,
                    'main_address': harvester_descriptor.main_address,

                    'host': node_descriptor.host,
                    'name': node_descriptor.name,
                    'version': node_descriptor.version,
                    'balance': harvester_descriptor.balance
                })

    def _build_peers_map(self):
        if not self.nodes_input_filepath:
            log.info('pulling peers from node')

            json_peers = create_blockchain_api_client(self.resources).get_peers()
            self._build_peers_map_from_json(json_peers)
        else:
            log.info('processing node information from {}'.format(self.nodes_input_filepath))
            with open(self.nodes_input_filepath, 'r') as infile:
                self._build_peers_map_from_json(json.load(infile))

        log.info('found {} mappings'.format(len(self.peers_map)))

    def _build_peers_map_from_json(self, json_peers):
        for json_node in json_peers:
            public_key = json_node['identity']['public-key']
            self.peers_map[public_key] = self.create_node_descriptor(json_node)

    @staticmethod
    def create_node_descriptor(json_node):
        json_identity = json_node['identity']
        json_endpoint = json_node['endpoint']
        json_metadata = json_node['metaData']
        return NodeDescriptor(
            json_identity['name'],
            '{}://{}:{}'.format(json_endpoint['protocol'], json_endpoint['host'], json_endpoint['port']),
            json_metadata['version'])


def main():
    parser = argparse.ArgumentParser(description='downloads harvester account information for a NEM network')
    parser.add_argument('--resources', help='directory containing resources', required=True)
    parser.add_argument('--network', help='network name', default='mainnet')
    parser.add_argument('--days', help='number of days of blocks to analyze', type=float, default=7)
    parser.add_argument('--nodes', help='(optional) nodes json file')
    parser.add_argument('--output', help='output file', required=True)
    parser.add_argument('--thread-count', help='number of threads', type=int, default=16)
    args = parser.parse_args()

    resources = load_resources(args.resources)
    downloader = HarvesterDownloader(resources, args.network, int(args.days * 24 * 60), args.nodes)
    downloader.download(args.thread_count, args.output)


if '__main__' == __name__:
    main()
