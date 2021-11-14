import argparse
import csv
import random
import time
from threading import Lock, Thread

from symbolchain.core.CryptoTypes import PublicKey
from zenlog import log

from client.ResourceLoader import create_blockchain_facade, load_resources, locate_blockchain_client_class

from .PeersMapBuilder import NodeDescriptor, PeersMapBuilder


class HarvesterDescriptor:
    def __init__(self):
        self.signer_public_key = None
        self.signer_address = None
        self.main_public_key = None
        self.main_address = None
        self.balance = 0


class BatchDownloader:
    # pylint: disable=too-many-instance-attributes

    def __init__(self, resources, thread_count):
        self.resources = resources
        self.thread_count = thread_count
        self.nodes = self.resources.nodes.find_all_not_by_role('seed-only')

        self.max_height = 0
        self.next_height = 0

        self.facade = create_blockchain_facade(self.resources)
        self.api_clients = []
        self.public_key_to_descriptor_map = {}
        self.lock = Lock()

    def download_all(self, num_blocks):
        for node_descriptor in self.nodes:
            self.api_clients.append(locate_blockchain_client_class(self.resources)(node_descriptor.host, timeout=60, retry_post=True))

        chain_height = random.choice(self.api_clients).get_chain_height()

        log.info('chain height is {}'.format(chain_height))
        min_height = max(1, chain_height - num_blocks + 1)
        self.max_height = chain_height
        self.next_height = min_height

        log.info('starting {} harvester download threads [{}, {}]'.format(self.thread_count, min_height, self.max_height))
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

    def _get_balance_follow_links(self, api_client, address):
        account_info = api_client.get_account_info(address)

        if 'REMOTE' == account_info.remote_status:  # nem
            account_info = api_client.get_account_info(address, forwarded=True)
        if 'Remote' == account_info.remote_status:  # symbol
            main_address = self.facade.network.public_key_to_address(PublicKey(account_info.linked_public_key))
            account_info = api_client.get_account_info(main_address)

        return (account_info.address, account_info.public_key, account_info.balance)


class HarvesterDownloader:
    def __init__(self, resources, num_blocks, nodes_input_filepath):
        self.resources = resources
        self.num_blocks = num_blocks
        self.nodes_input_filepath = nodes_input_filepath

        self.peers_map = {}

    def download(self, thread_count, output_filepath):
        self.peers_map = self._build_peers_map()

        log.info('downloading harvester activity to {} for last {} blocks'.format(output_filepath, self.num_blocks))

        batch_downloader = BatchDownloader(self.resources, thread_count)
        batch_downloader.download_all(self.num_blocks)

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
        builder = PeersMapBuilder(self.resources, self.nodes_input_filepath)
        builder.build()
        return builder.peers_map


def main():
    parser = argparse.ArgumentParser(description='downloads harvester account information for a network')
    parser.add_argument('--resources', help='directory containing resources', required=True)
    parser.add_argument('--days', help='number of days of blocks to analyze', type=float, default=7)
    parser.add_argument('--nodes', help='(optional) nodes json file')
    parser.add_argument('--output', help='output file', required=True)
    parser.add_argument('--thread-count', help='number of threads', type=int, default=16)
    args = parser.parse_args()

    resources = load_resources(args.resources)
    blocks_per_day = 60 if 'nem' == resources.friendly_name else 120
    downloader = HarvesterDownloader(resources, int(args.days * 24 * blocks_per_day), args.nodes)
    downloader.download(args.thread_count, args.output)


if '__main__' == __name__:
    main()
