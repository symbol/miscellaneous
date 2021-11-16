import argparse
import csv

from zenlog import log

from client.ResourceLoader import create_blockchain_api_client, load_resources

from .PeersMapBuilder import EMPTY_NODE_DESCRIPTOR, PeersMapBuilder

MAINNET_XYM_MOSAIC_ID = '6BED913FA20223F8'


class RichListDownloader:
    def __init__(self, resources, min_balance, mosaic_id, nodes_input_filepath):
        self.resources = resources
        self.min_balance = min_balance
        self.mosaic_id = mosaic_id
        self.nodes_input_filepath = nodes_input_filepath
        self.api_client = create_blockchain_api_client(self.resources)

        self.public_key_to_descriptor_map = {}

    def download(self, output_filepath):
        self._prepare_nodes()

        log.info('downloading rich list activity to {} for accounts with {} balances at least {}'.format(
            output_filepath,
            self.mosaic_id,
            self.min_balance))
        finalization_epoch = self._get_finalization_epoch()

        page_number = 1
        with open(output_filepath, 'w') as outfile:
            column_names = [
                'address', 'balance', 'is_voting', 'has_ever_voted', 'voting_end_epoch',
                'host', 'name', 'height', 'finalized_height', 'version'
            ]
            csv_writer = csv.DictWriter(outfile, column_names)
            csv_writer.writeheader()

            while True:
                log.debug('processing page {}'.format(page_number))

                if not self._download_page(page_number, finalization_epoch, csv_writer):
                    return

                page_number += 1

    def _prepare_nodes(self):
        if not self.nodes_input_filepath:
            return

        builder = PeersMapBuilder(self.resources, self.nodes_input_filepath)
        builder.build()
        self.public_key_to_descriptor_map = builder.peers_map

        log.info('found {} mappings'.format(len(self.public_key_to_descriptor_map)))

    def _get_finalization_epoch(self):
        finalization_epoch = self.api_client.get_finalization_info().epoch
        log.info('finalization epoch is {}'.format(finalization_epoch))
        return finalization_epoch

    def _download_page(self, page_number, finalization_epoch, csv_writer):
        for account_info in self.api_client.get_richlist_account_infos(page_number, 100, self.mosaic_id):
            if account_info.balance < self.min_balance:
                log.info('found account {} with balance {} less than min balance'.format(account_info.address, account_info.balance))
                return False

            voting_epoch_ranges = account_info.voting_epoch_ranges

            is_voting = any(
                voting_epoch_range[0] <= finalization_epoch <= voting_epoch_range[1]
                for voting_epoch_range in voting_epoch_ranges
            )

            max_voting_end_epoch = 0
            if voting_epoch_ranges:
                max_voting_end_epoch = max(voting_epoch_range[1] for voting_epoch_range in voting_epoch_ranges)

            node_descriptor = self.public_key_to_descriptor_map.get(account_info.public_key, EMPTY_NODE_DESCRIPTOR)

            csv_writer.writerow({
                'address': account_info.address,
                'balance': account_info.balance,
                'is_voting': is_voting,
                'has_ever_voted': any(voting_epoch_ranges),
                'voting_end_epoch': max_voting_end_epoch,

                'host': node_descriptor.host,
                'name': node_descriptor.name,
                'height': node_descriptor.height,
                'finalized_height': node_descriptor.finalized_height,
                'version': node_descriptor.version
            })

        return True


def main():
    parser = argparse.ArgumentParser(description='downloads high balance account information for a Symbol network')
    parser.add_argument('--resources', help='directory containing resources', required=True)
    parser.add_argument('--min-balance', help='minimum balance to include', type=int, default=3000000)
    parser.add_argument('--mosaic-id', help='mosaic id', default=MAINNET_XYM_MOSAIC_ID)
    parser.add_argument('--nodes', help='(optional) nodes json file')
    parser.add_argument('--output', help='output file', required=True)
    args = parser.parse_args()

    resources = load_resources(args.resources)
    downloader = RichListDownloader(resources, args.min_balance, args.mosaic_id, args.nodes)
    downloader.download(args.output)


if '__main__' == __name__:
    main()
