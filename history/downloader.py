import argparse
import csv
import datetime
from pathlib import Path
from threading import Thread

from zenlog import log

from core.CoinGeckoClient import CoinGeckoClient
from core.ResourceLoader import create_blockchain_api_client, load_resources


class ChainActivityDownloader:
    def __init__(self, resources, account_descriptor):
        self.resources = resources
        self.account_descriptor = account_descriptor

    def download(self, start_date, end_date, output_filepath):
        log.info('[{}] downloading chain activity from {} to {}'.format(output_filepath,  start_date, end_date))

        with open(output_filepath, 'w') as outfile:
            column_names = ['timestamp', 'amount', 'fee_paid', 'height', 'address', 'tag', 'comments', 'hash']
            csv_writer = csv.DictWriter(outfile, column_names, extrasaction='ignore')
            csv_writer.writeheader()

            num_rows_written = 0
            for mode in ['harvests', 'transfers']:
                num_rows_written += self._download_batch(mode, start_date, end_date, output_filepath, csv_writer)

        if not num_rows_written:
            Path(output_filepath).unlink()

    def _download_batch(self, mode, start_date, end_date, output_filepath, csv_writer):
        # pylint: disable=too-many-arguments

        api_client = create_blockchain_api_client(self.resources)
        downloader = api_client.get_harvests if 'harvests' == mode else api_client.get_transfers

        num_rows_written = 0
        start_id = None
        while True:
            snapshots = downloader(self.account_descriptor.address, start_id)
            if not snapshots:
                return num_rows_written

            for snapshot in snapshots:
                if snapshot.timestamp.date() < start_date:
                    return num_rows_written

                if snapshot.timestamp.date() > end_date:
                    continue

                snapshot.address = self.account_descriptor.name
                csv_writer.writerow(vars(snapshot))
                num_rows_written += 1

            start_id = snapshots[-1].collation_id

            log.debug('[{}::{}] finished processing {}'.format(output_filepath, mode, snapshots[-1].timestamp))


class PriceDownloader:
    def __init__(self, resources, fiat_currency):
        self.resources = resources
        self.fiat_currency = fiat_currency

    def download(self, start_date, end_date, output_filepath):
        log.info('[{}] downloading prices from {} to {}'.format(output_filepath,  start_date, end_date))

        coin_gecko_client = CoinGeckoClient()

        with open(output_filepath, 'w') as outfile:
            csv_writer = csv.DictWriter(outfile, ['date', 'price', 'volume', 'market_cap', 'comments'])
            csv_writer.writeheader()

            current_date = start_date
            while current_date <= end_date:
                snapshot = coin_gecko_client.get_price_snapshot(current_date, self.resources.ticker_name, self.fiat_currency)
                if 'no price data available' == snapshot.comments:
                    snapshot.price = self.resources.premarket_price
                    snapshot.comments = 'premarket price'

                csv_writer.writerow(vars(snapshot))

                log.debug('[{}] finished processing {}'.format(output_filepath, current_date))

                current_date += datetime.timedelta(days=1)


def main():
    parser = argparse.ArgumentParser(
        description='download transactions from nem or symbol networks',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--input', help='input resources file', required=True)
    parser.add_argument('--output', help='output directory', required=True)
    parser.add_argument('--start-date', help='start date', required=True)
    parser.add_argument('--end-date', help='end date', default=datetime.date.today().isoformat())
    parser.add_argument('--fiat-currency', help='fiat currency', default='usd')
    args = parser.parse_args()

    output_directory = Path(args.output)
    if output_directory.exists():
        log.warn('output directory \'{}\' already exists'.format(args.output))
        return

    log.info('starting downloads!')

    output_directory.mkdir(parents=True)

    resources = load_resources(args.input)
    start_date = datetime.date.fromisoformat(args.start_date)
    end_date = datetime.date.fromisoformat(args.end_date)

    threads = []
    for account_descriptor in resources.accounts.find_all_by_role(None):
        chain_activity_downloader = ChainActivityDownloader(resources, account_descriptor)
        account_output_filepath = output_directory / '{}.csv'.format(account_descriptor.name)
        threads.append(Thread(target=chain_activity_downloader.download, args=(start_date, end_date, account_output_filepath)))

    price_downloader = PriceDownloader(resources, args.fiat_currency)
    price_output_filepath = output_directory / '{}_{}.csv'.format(resources.ticker_name, args.fiat_currency)
    threads.append(Thread(target=price_downloader.download, args=(start_date, end_date, price_output_filepath)))

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    log.info('all downloads complete!')


if '__main__' == __name__:
    main()
