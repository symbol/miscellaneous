import argparse
import json
import os
from datetime import datetime

from zenlog import log


class NodeTracker:
	"""
	Class for tracking the number of nodes in a network.
	"""

	@staticmethod
	def _load_time_series_data(output):
		"""
		Loads the time series data from the output file.
		"""

		time_series_data = []
		if os.path.exists(output) and os.path.getsize(output) > 0:
			try:
				with open(output, 'r', encoding='utf8') as infile:
					time_series_data = json.load(infile)
			except Exception as ex:
				raise ValueError(f'Error reading input file: {str(ex)}') from ex

		return time_series_data

	def _add_data_point(self, data_point, output_file):  # pylint: disable=no-self-use
		"""
		Adds a new data point to the time series data.
		"""

		# Load existing time series data
		time_series = self._load_time_series_data(output_file)

		# Check if snapshot already exists
		if time_series and time_series[-1]['date'] == data_point['date']:
			raise ValueError(f'Time series data for {data_point["date"]} already exists')

		time_series.append(data_point)

		with open(output_file, 'w', encoding='utf8') as outfile:
			json.dump(time_series, outfile, indent=4, sort_keys=True)

		log.info(f'Saved time series data to: {output_file}')

	def _count_roles(self, nodes):  # pylint: disable=no-self-use
		"""
		Counts the number of nodes for each role.
		"""

		node_roles = ['1', '2', '3', '4', '5', '6', '7']

		roles = {}
		for role in node_roles:
			roles[role] = 0

		for node in nodes:
			role = str(node['roles'])
			if role in node_roles:
				roles[role] += 1
			else:
				log.warning(f'Unknown node role: {role}')

		roles['total'] = sum(roles.values())

		return roles

	def generate_time_series(self, input_file, output_file):
		"""
		Generates a time series data file from the node snapshots.
		"""

		try:
			with open(input_file, 'r', encoding='utf8') as infile:
				nodes = json.load(infile)
		except Exception as ex:
			raise ValueError(f'Error reading input file: {str(ex)}') from ex

		roles = self._count_roles(nodes)

		new_snapshot = {
			'date': datetime.utcnow().strftime('%Y-%m-%d'),
			'values': roles
		}

		# Save time series data
		self._add_data_point(new_snapshot, output_file)


def main():
	parser = argparse.ArgumentParser(description='Track and analyze node count over time')
	parser.add_argument('--input', help='nodes json file', required=True)
	parser.add_argument('--output', help='Output file for time series data', required=True)

	args = parser.parse_args()

	node_tracker = NodeTracker()
	node_tracker.generate_time_series(args.input, args.output)


if '__main__' == __name__:
	main()
