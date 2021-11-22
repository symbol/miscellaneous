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

        self.finalization_epoch = 0
        self.voters_map = {}
        self.public_key_to_descriptor_map = {}

    def download(self, output_filepath):
        self._prepare_nodes()

        log.info(f'downloading rich list activity to {output_filepath} for accounts with {self.mosaic_id} balances'
                 f' at least {self.min_balance}')
        self._download_finalization_information()

        page_number = 1
        with open(output_filepath, 'wt', encoding='utf8') as outfile:
            column_names = [
                'address', 'balance', 'is_voting', 'has_ever_voted', 'voting_end_epoch', 'current_epoch_votes',
                'host', 'name', 'height', 'finalized_height', 'version'
            ]
            csv_writer = csv.DictWriter(outfile, column_names)
            csv_writer.writeheader()

            while True:
                log.debug(f'processing page {page_number}')

                if not self._download_page(page_number, csv_writer):
                    return

                page_number += 1

    def _prepare_nodes(self):
        if not self.nodes_input_filepath:
            return

        builder = PeersMapBuilder(self.resources, self.nodes_input_filepath)
        builder.build()
        self.public_key_to_descriptor_map = builder.peers_map

    def _download_finalization_information(self):
        self.finalization_epoch = self.api_client.get_finalization_info().epoch
        self.voters_map = self.api_client.get_voters(self.finalization_epoch)

        log.info(f'finalization epoch is {self.finalization_epoch} ({len(self.voters_map)} participating voters)')

    def _download_page(self, page_number, csv_writer):
        for account_info in self.api_client.get_richlist_account_infos(page_number, 100, self.mosaic_id):
            if account_info.balance < self.min_balance:
                log.info(f'found account {account_info.address} with balance {account_info.balance} less than min balance')
                return False

            active_voting_public_key = next(
                (voting_public_key.public_key for voting_public_key in account_info.voting_public_keys
                    if voting_public_key.start_epoch <= self.finalization_epoch <= voting_public_key.end_epoch),
                None
            )

            max_voting_end_epoch = 0
            if account_info.voting_public_keys:
                max_voting_end_epoch = max(voting_public_key.end_epoch for voting_public_key in account_info.voting_public_keys)

            node_descriptor = self.public_key_to_descriptor_map.get(account_info.public_key, EMPTY_NODE_DESCRIPTOR)

            csv_writer.writerow({
                'address': account_info.address,
                'balance': account_info.balance,
                'is_voting': 'True' if active_voting_public_key else 'False',
                'has_ever_voted': any(account_info.voting_public_keys),
                'voting_end_epoch': max_voting_end_epoch,
                'current_epoch_votes': '|'.join(self.voters_map.get(active_voting_public_key, [])),

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
