import json
from collections import namedtuple

from symbolchain.CryptoTypes import PublicKey
from zenlog import log

from client.ResourceLoader import create_blockchain_api_client

NodeDescriptor = namedtuple('NodeDescriptor', ['name', 'host', 'version', 'height', 'finalized_height'])


EMPTY_NODE_DESCRIPTOR = NodeDescriptor('', '', '', 0, 0)


class PeersMapBuilder:
	def __init__(self, resources, nodes_input_filepath):
		self.resources = resources
		self.nodes_input_filepath = nodes_input_filepath
		self.is_nem = 'nem' == self.resources.friendly_name

		self.peers_map = {}

	def build(self):
		if not self.nodes_input_filepath:
			log.info('pulling peers from node')

			json_peers = create_blockchain_api_client(self.resources).get_peers()
			self._build_peers_map_from_json(json_peers)
		else:
			log.info(f'processing node information from {self.nodes_input_filepath}')
			with open(self.nodes_input_filepath, 'rt', encoding='utf8') as infile:
				self._build_peers_map_from_json(json.load(infile))

		log.info(f'found {len(self.peers_map)} mappings')

	def _build_peers_map_from_json(self, json_peers):
		for json_node in json_peers:
			public_key = PublicKey(self._get_public_key(json_node))
			self.peers_map[public_key] = self._create_node_descriptor(json_node)

	def _get_public_key(self, json_node):
		return json_node['identity']['public-key'] if self.is_nem else json_node['publicKey']

	def _create_node_descriptor(self, json_node):
		json_extra_data = json_node.get('extraData', {})

		if self.is_nem:
			json_identity = json_node['identity']
			json_endpoint = json_node['endpoint']
			json_metadata = json_node['metaData']

			node_protocol = json_endpoint['protocol']
			node_host = json_endpoint['host']
			node_port = json_endpoint['port']
			return NodeDescriptor(
				json_identity['name'],
				f'{node_protocol}://{node_host}:{node_port}',
				json_metadata['version'],
				json_extra_data.get('height', 0),
				0)

		node_host = json_node['host']
		node_port = json_node['port']
		if json_node['roles'] & 2:
			node_port = 3000  # use REST (default) port

		return NodeDescriptor(
			json_node['friendlyName'],
			f'http://{node_host}:{node_port}' if node_host else '',
			self._format_symbol_version(json_node['version']),
			json_extra_data.get('height', 0),
			json_extra_data.get('finalizedHeight', 0))

	@staticmethod
	def _format_symbol_version(version):
		version_parts = [(version >> 24) & 0xFF, (version >> 16) & 0xFF, (version >> 8) & 0xFF, version & 0xFF]
		return '.'.join(str(version_part) for version_part in version_parts)
