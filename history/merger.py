import argparse
import csv
from pathlib import Path

from zenlog import log

import client.pod
from history.constants import MERGER_FIELD_NAMES


class TransactionsLoader():
    def __init__(self, directory, ticker, currency):
        self.directory = Path(directory)
        self.ticker = ticker
        self.currency = currency

        self.price_map = dict()
        self.transaction_snapshots = []

    def load_price_map(self):
        filename = '{}_{}.csv'.format(self.ticker, self.currency)
        log.info('loading price map from {}'.format(filename))

        with open(self.directory / filename, 'r') as infile:
            csv_reader = csv.DictReader(infile)

            for row in csv_reader:
                snapshot = client.pod.PriceSnapshot(None)
                snapshot.__dict__.update(row)
                snapshot.fix_types()

                self.price_map[snapshot.date] = snapshot

    def load(self, filename):
        log.info('loading transactions from {}'.format(filename))

        with open(self.directory / filename, 'r') as infile:
            csv_reader = csv.DictReader(infile)

            for row in csv_reader:
                snapshot = client.pod.AugmentedTransactionSnapshot()
                snapshot.__dict__.update(row)
                snapshot.fix_types()

                price_snapshot = self.price_map[snapshot.timestamp.date()]
                snapshot.set_price(price_snapshot.price)

                self._fixup_comments(snapshot, price_snapshot)
                self._fixup_tag(snapshot)
                self.transaction_snapshots.append(snapshot)

    @staticmethod
    def _fixup_comments(snapshot, price_snapshot):
        comments = []
        if snapshot.comments:
            comments.append(snapshot.comments)

        if price_snapshot.comments:
            comments.append(price_snapshot.comments)

        if 0 == price_snapshot.price:
            comments.append('detected zero price for {}'.format(snapshot.timestamp))
            log.warn(comments[-1])

        snapshot.comments = '\n'.join(comments)

    @staticmethod
    def _fixup_tag(snapshot):
        if 'transfer' != snapshot.tag:
            return

        if snapshot.amount < 0:
            snapshot.tag = 'outgoing'
        elif snapshot.amount > 0:
            snapshot.tag = 'incoming'

            if 1 == snapshot.height:
                snapshot.tag += ' (seed)'
        elif 0 != snapshot.fee_paid:
            snapshot.tag = 'fee only'

    def save(self, filename):
        log.info('saving merged report to {}'.format(filename))

        self.transaction_snapshots.sort(key=lambda snapshot: snapshot.timestamp)

        with open(filename, 'w', newline='') as outfile:
            field_names = MERGER_FIELD_NAMES
            column_headers = field_names[:1] + [
                '{}_amount'.format(self.currency),
                '{}_fee_paid'.format(self.currency),
                '{}_amount'.format(self.ticker),
                '{}_fee_paid'.format(self.ticker),
                '{}/{}'.format(self.ticker, self.currency)
            ] + field_names[6:]

            csv_writer = csv.DictWriter(outfile, field_names, extrasaction='ignore')
            csv_writer.writerow(dict(zip(field_names, column_headers)))

            for snapshot in self.transaction_snapshots:
                csv_writer.writerow(vars(snapshot))


def main():
    parser = argparse.ArgumentParser(description='generates a merged pricing and account report')
    parser.add_argument('--input', help='input directory', required=True)
    parser.add_argument('--output', help='output filename', required=True)
    parser.add_argument('--ticker', help='ticker symbol', default='nem')
    parser.add_argument('--currency', help='fiat currency', default='usd')

    args = parser.parse_args()
    transactions_loader = TransactionsLoader(args.input, args.ticker, args.currency)
    transactions_loader.load_price_map()

    for filepath in Path(args.input).iterdir():
        if not filepath.name.startswith(args.ticker):
            transactions_loader.load(filepath.name)

    transactions_loader.save(args.output)


if '__main__' == __name__:
    main()
