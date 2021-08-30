import argparse
import csv
from pathlib import Path

from zenlog import log

from core.pod import AugmentedTransactionSnapshot
from history.constants import GROUPER_FIELD_NAMES


class Loader():
    def __init__(self, directory, mode, use_fiat):
        self.directory = Path(directory)
        self.mode = mode
        self.use_fiat = use_fiat

        self.key_names = {}
        self.rows = []

    def load(self, filename):
        log.info('loading input from {}'.format(filename))

        snapshots = []
        with open(self.directory / filename, 'r') as infile:
            csv_reader = csv.DictReader(infile, GROUPER_FIELD_NAMES)
            next(csv_reader)  # skip header

            for row in csv_reader:
                snapshot = AugmentedTransactionSnapshot()
                snapshot.__dict__.update(row)
                snapshot.fix_types(date_only=True)
                snapshots.append(snapshot)

        self._aggregate(snapshots)

    def _aggregate(self, snapshots):
        timestamp = None
        height = None

        row = {}
        for snapshot in snapshots:
            if not timestamp:
                timestamp = snapshot.timestamp
                height = snapshot.height

            timestamp = max(timestamp, snapshot.timestamp)
            height = max(height, snapshot.height)

            key = snapshot.address if 'account' == self.mode else snapshot.tag
            balance = snapshot.fiat_amount + snapshot.fiat_fee_paid if self.use_fiat else snapshot.amount + snapshot.fee_paid

            row[key] = balance
            self.key_names[key] = None

        row.update({'date': timestamp, 'height': height})
        self.rows.append(row)

    def fixup(self):
        # zero out any missing entries
        for key_name in self.key_names:
            for row in self.rows:
                if key_name not in row:
                    row[key_name] = 0

    def save(self, filename):
        log.info('saving {} {} balance table to {}'.format(self.mode, 'fiat' if self.use_fiat else 'token', filename))

        field_names = ['date', 'height'] + sorted(self.key_names.keys())
        with open(filename, 'w', newline='') as outfile:
            csv_writer = csv.DictWriter(outfile, field_names)
            csv_writer.writerow(dict(zip(field_names, field_names)))

            for row in sorted(self.rows, key=lambda row: row['date']):
                csv_writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description='generates a balance table based on options')
    parser.add_argument('--input', help='input directory', required=True)
    parser.add_argument('--output', help='output filename', required=True)
    parser.add_argument('--mode', help='report mode', choices=('account', 'tag'), required=True)
    parser.add_argument('--use-fiat', help='use fiat values', action='store_true')

    args = parser.parse_args()

    loader = Loader(args.input, args.mode, args.use_fiat)
    for filepath in Path(args.input).iterdir():
        loader.load(filepath.name)

    loader.fixup()
    loader.save(args.output)


if '__main__' == __name__:
    main()
