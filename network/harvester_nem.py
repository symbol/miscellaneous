import argparse
import csv
from collections import namedtuple

from symbolchain.core.CryptoTypes import PublicKey
from symbolchain.core.facade.NemFacade import NemFacade
from zenlog import log

from client.ResourceLoader import create_blockchain_api_client, load_resources

NodeDescriptor = namedtuple('NodeDescriptor', ['name', 'host'])


class HarvesterDownloader:
    def __init__(self, resources, network, num_blocks):
        self.resources = resources
        self.num_blocks = num_blocks
        self.facade = NemFacade(network)

    @property
    def api_client(self):
        return create_blockchain_api_client(self.resources)

    def download(self, output_filepath):
        log.info('downloading harvester activity to {} for last {} blocks'.format(output_filepath, self.num_blocks))

        harvester_signer_public_keys = self._load_recent_harvester_signer_public_keys()
        peers_map = self._build_peers_map()

        with open(output_filepath, 'w') as outfile:
            column_names = ['signer_address', 'main_address', 'host', 'name', 'balance']
            csv_writer = csv.DictWriter(outfile, column_names, extrasaction='ignore')
            csv_writer.writeheader()

            log.info('processing {} harvester signer public keys'.format(len(harvester_signer_public_keys)))

            i = 1
            for signer_public_key in harvester_signer_public_keys:
                signer_address = self.facade.network.public_key_to_address(PublicKey(signer_public_key))

                (main_address, balance) = self._get_balance_follow_links(signer_address)
                log.debug('[{:4}/{:4}] signer account {} is linked to {} with balance {}'.format(
                    i,
                    len(harvester_signer_public_keys),
                    signer_address,
                    main_address,
                    balance))

                node_descriptor = peers_map[signer_public_key] if signer_public_key in peers_map else NodeDescriptor('', '')

                csv_writer.writerow({
                    'signer_address': signer_address,
                    'main_address': main_address,

                    'host': node_descriptor.host,
                    'name': node_descriptor.name,
                    'balance': balance
                })

                i += 1

    def _build_peers_map(self):
        json_peers = self.api_client.get_peers()

        peers_map = {}
        for key in json_peers:
            for json_peer in json_peers[key]:
                json_identity = json_peer['identity']
                json_endpoint = json_peer['endpoint']
                node_descriptor = NodeDescriptor(
                    json_identity['name'],
                    '{}://{}:{}'.format(json_endpoint['protocol'], json_endpoint['host'], json_endpoint['port']))

                peers_map[json_identity['public-key']] = node_descriptor

        return peers_map

    def _load_recent_harvester_signer_public_keys(self):
        chain_height = self.api_client.get_chain_height()
        log.info('chain height is {}'.format(chain_height))

        log.info('processing {} blocks starting at {}'.format(self.num_blocks, chain_height))

        height = chain_height
        signer_public_keys = []
        while height >= 1 and chain_height - height < self.num_blocks:
            log.debug('[{:4}/{:4}] processing block at {}'.format(chain_height - height + 1, self.num_blocks, height))

            signer_public_key = self.api_client.get_harvester_signer_public_key(height)
            signer_public_keys.append(signer_public_key)

            height -= 1

        return set(signer_public_keys)

    def _get_balance_follow_links(self, address):
        account_info = self.api_client.get_account_info(address)

        if 'REMOTE' == account_info.remote_status:
            account_info = self.api_client.get_account_info(address, forwarded=True)

        return (account_info.address, account_info.balance)


def main():
    parser = argparse.ArgumentParser(description='downloads harvester account information for a NEM network')
    parser.add_argument('--resources', help='directory containing resources', required=True)
    parser.add_argument('--network', help='network name', default='mainnet')
    parser.add_argument('--days', help='number of days of blocks to analyze', type=float, default=7)
    parser.add_argument('--output', help='output file', required=True)
    args = parser.parse_args()

    resources = load_resources(args.resources)
    downloader = HarvesterDownloader(resources, args.network, int(args.days * 24 * 60))
    downloader.download(args.output)


if '__main__' == __name__:
    main()
