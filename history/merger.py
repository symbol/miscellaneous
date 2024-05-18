import argparse
import csv
import datetime
from pathlib import Path

from zenlog import log

import client.pod
from history.constants import MERGER_FIELD_NAMES


class TransactionsLoader():
	def __init__(self, directory, ticker, currency, human_readable):
		self.directory = Path(directory)
		self.ticker = ticker
		self.currency = currency
		self.human_readable = human_readable

		self.price_map = {}
		self.transaction_snapshots = []

	def load_price_map(self):
		filename = f'{self.ticker}_{self.currency}.csv'
		log.info(f'loading price map from {filename}')

		with open(self.directory / filename, 'rt', encoding='utf8') as infile:
			csv_reader = csv.DictReader(infile)

			for row in csv_reader:
				snapshot = client.pod.PriceSnapshot(None)
				snapshot.__dict__.update(row)
				snapshot.fix_types()

				self.price_map[snapshot.date] = snapshot

	def load(self, filename):
		log.info(f'loading transactions from {filename}')

		with open(self.directory / filename, 'rt', encoding='utf8') as infile:
			csv_reader = csv.DictReader(infile)

			for row in csv_reader:
				snapshot = client.pod.AugmentedTransactionSnapshot()
				snapshot.__dict__.update(row)
				raw_timestamp = snapshot.timestamp
				snapshot.fix_types()

				price_snapshot = self.price_map[snapshot.timestamp.date()]
				snapshot.set_price(price_snapshot.price)

				self._fixup_comments(snapshot, price_snapshot)
				self._fixup_tag(snapshot)

				if self.human_readable:
					snapshot.address = snapshot.address_name
				else:
					snapshot.timestamp = datetime.datetime.fromisoformat(raw_timestamp).isoformat()
					snapshot.timestamp = snapshot.timestamp.replace('+00:00', 'Z')

				self.transaction_snapshots.append(snapshot)

	@staticmethod
	def _fixup_comments(snapshot, price_snapshot):
		comments = []
		if snapshot.comments:
			comments.append(snapshot.comments)

		if price_snapshot.comments:
			comments.append(price_snapshot.comments)

		if 0 == price_snapshot.price:
			comments.append(f'detected zero price for {snapshot.timestamp}')
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
		log.info(f'saving merged report to {filename}')

		self.transaction_snapshots.sort(key=lambda snapshot: snapshot.timestamp)

		with open(filename, 'wt', newline='', encoding='utf8') as outfile:
			field_names = MERGER_FIELD_NAMES
			column_headers = field_names[:1] + [
				f'{self.currency}_amount',
				f'{self.currency}_fee_paid',
				f'{self.ticker}_amount',
				f'{self.ticker}_fee_paid',
				f'{self.ticker}/{self.currency}'
			] + field_names[6:]

			if not self.human_readable:
				field_names += ['address_name']
				column_headers += ['address_name']

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
	parser.add_argument('--human-readable', help='outputs a more human readable format', action='store_true')
	args = parser.parse_args()

	transactions_loader = TransactionsLoader(args.input, args.ticker, args.currency, args.human_readable)
	transactions_loader.load_price_map()

	for filepath in Path(args.input).glob('**/*.csv'):
		if not filepath.name.startswith(args.ticker):
			transactions_loader.load(filepath.name)

	transactions_loader.save(args.output)


if '__main__' == __name__:
	main()
