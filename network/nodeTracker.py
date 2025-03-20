import argparse
import json
import os
from datetime import datetime

from zenlog import log


class NodeTracker:
	"""
	Class for tracking the number of nodes in a network.
	"""

	def __init__(self, history_directory):
		self.history_directory = history_directory

		if not os.path.exists(self.history_directory):
			os.makedirs(self.history_directory)
			log.info(f'Created history directory: {self.history_directory}')

	def capture_snapshot(self, nodes_file):
		"""
		Captures a snapshot of the current number of nodes in the network.
		"""

		try:
			with open(nodes_file, 'r', encoding='utf8') as infile:
				nodes = json.load(infile)
		except Exception as ex:
			raise ValueError(f'Error reading input file: {str(ex)}') from ex

		roles = {}
		for node in nodes:
			role = node['roles']
			if role in roles:
				roles[role] += 1
			else:
				roles[role] = 1

		timestamp = datetime.utcnow()
		snapshot_file = os.path.join(self.history_directory, f'nodes_snapshot_{timestamp}.json')

		with open(snapshot_file, 'w', encoding='utf8') as outfile:
			json.dump(roles, outfile, indent=4, sort_keys=True)

		log.info(f'Captured node snapshot with {len(nodes)} nodes: {snapshot_file}')

	def _get_snapshot_files(self, file_date=None):
		"""
		Returns a list of snapshot files in the history directory.
		"""

		snapshot_files = [f for f in os.listdir(self.history_directory) if f.startswith('nodes_snapshot_')]
		filtered_files = []

		for snapshot_file in snapshot_files:
			timestamp_file = snapshot_file.replace('nodes_snapshot_', '').replace('.json', '')
			timestamp = datetime.strptime(timestamp_file, '%Y-%m-%d %H:%M:%S.%f').date()

			if file_date and timestamp < datetime.strptime(file_date, '%Y%m%d').date():
				continue

			if file_date and timestamp > datetime.strptime(file_date, '%Y%m%d').date():
				continue

			filtered_files.append(snapshot_file)

		return filtered_files

	def _calculate_average_counts(self, snapshots):  # pylint: disable=no-self-use
		"""
		Calculates the average number of nodes in the snapshots.
		"""

		average_counts = {}
		for snapshot in snapshots:
			node_roles = ['1', '2', '3', '4', '5', '6', '7']

			# Count nodes for each role
			for node_role in node_roles:
				if node_role not in average_counts:
					average_counts[node_role] = 0

				if node_role in snapshot:
					average_counts[node_role] += snapshot[node_role]

		# Calculate averages
		for node_role in average_counts:
			average_counts[node_role] = round(average_counts[node_role] / len(snapshots))

		# Add total
		average_counts['total'] = sum(average_counts.values())
		return average_counts

	def _load_time_series_data(self, output):  # pylint: disable=no-self-use
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

	def _save_time_series_data(self, time_series_data, output):  # pylint: disable=no-self-use
		"""
		Saves the time series data to the output file.
		"""

		with open(output, 'w', encoding='utf8') as outfile:
			json.dump(time_series_data, outfile, indent=4, sort_keys=True)

		log.info(f'Saved time series data to: {output}')

	def generate_time_series(self, output=None, snapshot_date=None):
		"""
		Generates a time series data file from the node snapshots.
		"""

		# Get snapshot files by date range
		snapshot_files = self._get_snapshot_files(snapshot_date)

		# Load snapshots data
		snapshots = []
		for snapshot_file in snapshot_files:
			with open(os.path.join(self.history_directory, snapshot_file), 'r', encoding='utf8') as infile:
				snapshot = json.load(infile)
				snapshots.append(snapshot)

		if not snapshots:
			raise ValueError('No snapshots found')

		# Calculate average counts
		average_counts = self._calculate_average_counts(snapshots)

		# Load existing time series data from output file
		time_series_data = self._load_time_series_data(output)

		new_snapshot = {
			'date': datetime.strptime(snapshot_date, '%Y%m%d').strftime('%Y-%m-%d'),
			'values': average_counts
		}

		# Check if snapshot already exists
		existing_dates = {entry['date'] for entry in time_series_data}
		if new_snapshot['date'] in existing_dates:
			raise ValueError(f'Time series data for {snapshot_date} already exists')

		time_series_data.append(new_snapshot)

		# Save time series data
		self._save_time_series_data(time_series_data, output)


def main():
	parser = argparse.ArgumentParser(description='Track and analyze node count over time')
	parser.add_argument('--action', choices=('capture', 'generate'), required=True, help='capture a new snapshot or generate data')
	parser.add_argument('--input', help='nodes json file', required=False)
	parser.add_argument('--history-directory', default='./network_node_history', help='Directory to store node history snapshots')
	parser.add_argument('--output', help='Output file for time series data', required=False)
	parser.add_argument('--snapshot-date', help='snapshot date for analysis (YYYYMMDD)', required=False)

	args = parser.parse_args()

	node_tracker = NodeTracker(args.history_directory)

	if 'capture' == args.action:
		if not args.input:
			raise ValueError('--input is required for capture action')

		node_tracker.capture_snapshot(args.input)
	elif 'generate' == args.action:
		if not args.output:
			raise ValueError('--output is required for generate action')

		if not args.snapshot_date:
			raise ValueError('--snapshot-date is required for generate action')

		node_tracker.generate_time_series(args.output, args.snapshot_date)


if '__main__' == __name__:
	main()
