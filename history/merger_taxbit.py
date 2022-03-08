import argparse
import csv
import datetime
from pathlib import Path

from zenlog import log

import client.pod


class TransactionsLoader():
    def __init__(self, ticker, start_date, end_date):
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date

        self.transaction_snapshots = []

    def load(self, filepath):
        log.info(f'loading transactions from {filepath}')

        with open(filepath, 'rt', encoding='utf8') as infile:
            csv_reader = csv.DictReader(infile)

            for row in csv_reader:
                self._process_row(row)

    def _process_row(self, row):
        snapshot = client.pod.AugmentedTransactionSnapshot()
        snapshot.__dict__.update(row)
        raw_timestamp = snapshot.timestamp
        snapshot.fix_types()

        if self.start_date and snapshot.timestamp.date() < self.start_date:
            return

        if snapshot.timestamp.date() > self.end_date:
            return

        if 0 == snapshot.amount and 0 == snapshot.fee_paid:
            return

        self._fixup_tag(snapshot)
        snapshot.timestamp = datetime.datetime.fromisoformat(raw_timestamp).isoformat()
        snapshot.timestamp = snapshot.timestamp.replace('+00:00', 'Z')
        self.transaction_snapshots.append(snapshot)

    @staticmethod
    def _fixup_tag(snapshot):
        snapshot.amount_sent = 0
        snapshot.amount_received = 0

        if snapshot.amount < 0:
            snapshot.tag = 'Expense'
            snapshot.amount_sent = -snapshot.amount
        elif snapshot.amount > 0:
            snapshot.tag = 'Income'
            snapshot.amount_received = snapshot.amount
        elif 0 != snapshot.fee_paid:
            # TaxBit does not support 'fee only' transactions, so treat as expense
            snapshot.tag = 'Expense'
            snapshot.amount_sent = -snapshot.fee_paid
            snapshot.fee_paid = 0

        if snapshot.fee_paid:
            snapshot.fee_paid = -snapshot.fee_paid

    def save(self, filename):
        log.info(f'saving merged report to {filename}')

        self.transaction_snapshots.sort(key=lambda snapshot: snapshot.timestamp)

        # count the number of times each transaction hash appears
        # if it occurs multiple times, assume it is a transfer of funds between (owned) accounts
        transaction_hash_counts = {}
        for snapshot in self.transaction_snapshots:
            transaction_hash_counts[snapshot.hash] = transaction_hash_counts.get(snapshot.hash, 0) + 1

        with open(filename, 'wt', newline='', encoding='utf8') as outfile:
            column_headers = [
                'Date and Time',
                'Transaction Type',
                'Sent Quantity',
                'Sent Currency',
                'Sending Source',
                'Received Quantity',
                'Received Currency',
                'Receiving Destination',
                'Fee',
                'Fee Currency',
                'Exchange Transaction ID',
                'Blockchain Transaction Hash'
            ]

            csv_writer = csv.writer(outfile)
            csv_writer.writerow(column_headers)

            # map of transaction hash to last id
            # this is only populated for duplicate hashes in order to generate a unique postfix for disambiguation
            transaction_hash_to_last_id = {}

            taxbit_ticker = 'XEM' if 'nem' == self.ticker else 'XYM'
            for snapshot in self.transaction_snapshots:
                transaction_id = None  # used for disambiguation of duplicate hashes
                if transaction_hash_counts[snapshot.hash] > 1:
                    transaction_id = transaction_hash_to_last_id.get(snapshot.hash, 0) + 1
                    transaction_hash_to_last_id[snapshot.hash] = transaction_id

                is_income = 'Income' == snapshot.tag
                if transaction_id:
                    snapshot.tag = 'Transfer In' if is_income else 'Transfer Out'

                csv_writer.writerow([
                    snapshot.timestamp,
                    snapshot.tag,
                    '' if is_income else snapshot.amount_sent,
                    '' if is_income else taxbit_ticker,
                    '' if is_income else f'{taxbit_ticker} Wallet',
                    '' if not is_income else snapshot.amount_received,
                    '' if not is_income else taxbit_ticker,
                    '' if not is_income else f'{taxbit_ticker} Wallet',
                    '' if not snapshot.fee_paid else snapshot.fee_paid,
                    '' if not snapshot.fee_paid else taxbit_ticker,
                    '',
                    f'{snapshot.hash}-{transaction_id}' if transaction_id else str(snapshot.hash)
                ])


def main():
    parser = argparse.ArgumentParser(description='generates a merged report that can be imported into TaxBit')
    parser.add_argument('--input', help='input directory', required=True)
    parser.add_argument('--output', help='output filename', required=True)
    parser.add_argument('--ticker', help='ticker symbol', default='nem')
    parser.add_argument('--start-date', help='start date')
    parser.add_argument('--end-date', help='end date', default=datetime.datetime.today())
    args = parser.parse_args()

    start_date = datetime.date.fromisoformat(args.start_date) if args.start_date else None
    end_date = datetime.date.fromisoformat(args.end_date)
    transactions_loader = TransactionsLoader(args.ticker, start_date, end_date)

    for filepath in Path(args.input).glob('**/*.csv'):
        if not filepath.name.startswith(args.ticker):
            transactions_loader.load(filepath)

    transactions_loader.save(args.output)


if '__main__' == __name__:
    main()
