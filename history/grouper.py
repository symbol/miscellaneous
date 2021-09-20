import argparse
import csv

from zenlog import log

from client.pod import AugmentedTransactionSnapshot
from history.constants import GROUPER_FIELD_NAMES


class GroupKey():
    def __init__(self):
        self.time_point = 'ALL'
        self.tag = 'ALL'
        self.account_type = 'ALL'

    def __str__(self):
        return '{}::{}::{}'.format(self.time_point, self.tag, self.account_type)


class Grouper():
    def __init__(self, mode):
        self.mode = mode

        self.map = dict()
        self.field_names = GROUPER_FIELD_NAMES
        self.column_names = []

    def load(self, filename):
        log.info('loading all transactions from {}'.format(filename))

        with open(filename, 'r') as infile:
            csv_reader = csv.DictReader(infile, self.field_names)
            self.column_names = next(csv_reader)  # skip header

            for row in csv_reader:
                snapshot = AugmentedTransactionSnapshot()
                snapshot.__dict__.update(row)
                snapshot.fix_types(date_only=True)

                group_key = self._make_group_key(snapshot)
                compact_group_key = str(group_key)
                if compact_group_key not in self.map:
                    aggregate_snapshot = AugmentedTransactionSnapshot()
                    aggregate_snapshot.timestamp = snapshot.timestamp if 'ALL' == group_key.time_point else group_key.time_point
                    aggregate_snapshot.tag = group_key.tag
                    aggregate_snapshot.address = group_key.account_type
                    aggregate_snapshot.comments = ''
                    self.map[compact_group_key] = aggregate_snapshot

                aggregate_snapshot = self.map[compact_group_key]
                self._aggregate(aggregate_snapshot, snapshot)

        for value in self.map.values():
            value.round()

    def _make_group_key(self, snapshot):
        key = GroupKey()
        if 'daily' == self.mode:
            key.time_point = snapshot.timestamp

        if 'daily' == self.mode or 'tag' in self.mode:
            key.tag = snapshot.tag

        if 'account' in self.mode:
            key.account_type = snapshot.address

        return key

    @staticmethod
    def _aggregate(snapshot, new_snapshot):
        snapshot.timestamp = max(snapshot.timestamp, new_snapshot.timestamp)

        price_denominator = (snapshot.amount - snapshot.fee_paid) + (new_snapshot.amount - new_snapshot.fee_paid)
        price_numerator = (snapshot.fiat_amount - snapshot.fiat_fee_paid) + (new_snapshot.fiat_amount - new_snapshot.fiat_fee_paid)
        snapshot.price = 0 if not price_denominator else price_numerator / price_denominator

        snapshot.fiat_amount += new_snapshot.fiat_amount
        snapshot.fiat_fee_paid += new_snapshot.fiat_fee_paid
        snapshot.amount += new_snapshot.amount
        snapshot.fee_paid += new_snapshot.fee_paid

        if snapshot.comments:
            if new_snapshot.comments and snapshot.comments != new_snapshot.comments:
                snapshot.comments += '\n' + new_snapshot.comments
        elif new_snapshot.comments:
            snapshot.comments = new_snapshot.comments

        snapshot.height = max(snapshot.height, new_snapshot.height)

    def save(self, filename):
        log.info('saving {} grouped report to {}'.format(self.mode, filename))

        with open(filename, 'w', newline='') as outfile:
            csv_writer = csv.DictWriter(outfile, self.field_names, extrasaction='ignore')
            csv_writer.writerow(self.column_names)

            for value in sorted(self.map.values(), key=lambda snapshot: (snapshot.timestamp, snapshot.tag, snapshot.address)):
                csv_writer.writerow(vars(value))


def main():
    parser = argparse.ArgumentParser(description='produces grouped report by aggregating input data based on mode')
    parser.add_argument('--input', help='input filename', required=True)
    parser.add_argument('--output', help='output filename', required=True)
    parser.add_argument('--mode', help='aggregation mode', choices=('daily', 'account', 'tag', 'account_tag'), required=True)

    args = parser.parse_args()

    grouper = Grouper(args.mode)
    grouper.load(args.input)
    grouper.save(args.output)


if '__main__' == __name__:
    main()
