import argparse
import json
import random
import time
from threading import Lock, Thread

from requests.exceptions import RequestException
from symbolchain.core.CryptoTypes import PublicKey
from symbolchain.core.nem.Network import Network as NemNetwork
from symbolchain.core.Network import NetworkLocator
from symbolchain.core.symbol.Network import Network as SymbolNetwork
from zenlog import log

from client.ResourceLoader import load_resources, locate_blockchain_client_class


class NodeDownloader:
    # pylint: disable=too-many-instance-attributes

    def __init__(self, resources, thread_count, timeout, network_name, certificate_directory):
        # pylint: disable=too-many-arguments

        self.resources = resources
        self.thread_count = thread_count
        self.timeout = timeout
        self.network_name = network_name
        self.certificate_directory = certificate_directory

        self.api_client_class = locate_blockchain_client_class(resources)
        self.visited_hosts = set()
        self.remaining_api_clients = []
        self.strong_api_clients = []
        self.public_key_to_node_info_map = {}
        self.busy_thread_count = 0
        self.lock = Lock()

    @property
    def is_nem(self):
        return 'nem' == self.resources.friendly_name

    def discover(self):
        log.info('seeding crawler with known hosts')
        self.remaining_api_clients = [
            self.api_client_class(node_descriptor.host) for node_descriptor in self.resources.nodes.find_all_by_role(None)
        ]
        self.strong_api_clients = [
            self.api_client_class(node_descriptor.host) for node_descriptor in self.resources.nodes.find_all_not_by_role('seed-only')
        ]

        log.info(f'starting {self.thread_count} crawler threads')
        threads = [Thread(target=self._discover_thread) for i in range(0, self.thread_count)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        log.info(f'crawling completed and discovered {len(self.public_key_to_node_info_map)} nodes')

    def _discover_thread(self):
        while self.remaining_api_clients or self.busy_thread_count:
            if not self.remaining_api_clients:
                time.sleep(2)
                continue

            with self.lock:
                api_client = self._pop_next_api_client()
                if not api_client:
                    time.sleep(2)
                    continue

            log.debug(f'processing {api_client.node_host} [{len(self.public_key_to_node_info_map)} discovered,'
                      f' {len(self.remaining_api_clients)} remaining, {self.busy_thread_count} busy]')

            is_reachable = False
            try:
                json_node = api_client.get_node_info()
                json_node['extraData'] = {'balance': 0, 'height': 0, 'finalizedHeight': 0}

                network = self._get_and_check_network(json_node)
                if network:
                    main_public_key = self._find_main_public_key(network, json_node)
                    is_reachable = True

                    json_peers = api_client.get_peers()

                    self._add_supplemental_account_information(network, main_public_key, json_node, api_client)

            except (RequestException, TimeoutError, ConnectionRefusedError) as ex:
                log.warning(f'failed to load peers from {api_client.node_host}:{api_client.node_port} (reachable node? {is_reachable})\n'
                            f'{ex}')
                json_peers = []

            finally:
                with self.lock:
                    if is_reachable:
                        self._update(main_public_key, json_node, json_peers)

                    self.busy_thread_count -= 1

                if self.busy_thread_count < self.thread_count - 1:
                    log.debug(f'idling threads detected; only {self.busy_thread_count} busy')

    def _get_and_check_network(self, json_node):
        if self.is_nem:
            networks = NemNetwork.NETWORKS
            network_identifier = json_node['metaData']['networkId'] & 0xFF  # coerce to unsigned
        else:
            networks = SymbolNetwork.NETWORKS
            network_identifier = json_node['networkIdentifier']

        try:
            network = NetworkLocator.find_by_identifier(networks, network_identifier)
        except StopIteration:
            log.warning(f'rejecting node from network with unknown identifier {network_identifier}')
            return None

        expected_network = NetworkLocator.find_by_name(networks, self.network_name)

        if network.identifier == expected_network.identifier:
            return network

        log.warning(f'rejecting node from network {network.name} when looking for nodes from {self.network_name}')
        return None

    def _find_main_public_key(self, network, json_node):
        strong_api_client = random.choice(self.strong_api_clients)

        if self.is_nem:
            node_address = network.public_key_to_address(PublicKey(json_node['identity']['public-key']))
            main_account_info = strong_api_client.get_account_info(node_address, forwarded=True)

            if 'ACTIVE' == main_account_info.remote_status:
                json_node['identity']['node-public-key'] = json_node['identity']['public-key']
                json_node['identity']['public-key'] = main_account_info.public_key

            return PublicKey(json_node['identity']['public-key'])

        return PublicKey(json_node['publicKey'])

    def _add_supplemental_account_information(self, network, main_public_key, json_node, api_client):
        strong_api_client = random.choice(self.strong_api_clients)

        main_account_info = strong_api_client.get_account_info(network.public_key_to_address(main_public_key))

        json_node['extraData']['balance'] = main_account_info.balance if main_account_info else 0
        json_node['extraData']['height'] = api_client.get_chain_height()

        if not self.is_nem:
            json_node['extraData']['finalizedHeight'] = api_client.get_finalization_info().height

    # this function must be called in context of self.lock
    def _pop_next_api_client(self):
        api_client = None
        while self.remaining_api_clients:
            api_client = self.remaining_api_clients.pop(0)
            if api_client and api_client.node_host not in self.visited_hosts:
                break

            api_client = None

        if not api_client:
            return None

        self.visited_hosts.add(api_client.node_host)
        self.busy_thread_count += 1
        return api_client

    # this function must be called in context of self.lock
    def _update(self, public_key, json_node, json_peers):
        self.public_key_to_node_info_map[public_key] = json_node
        for json_peer in json_peers:
            peer_api_client = self.api_client_class.from_node_info_dict(
                json_peer,
                retry_count=2,
                timeout=self.timeout,
                certificate_directory=self.certificate_directory)
            if (peer_api_client and peer_api_client.node_host not in self.visited_hosts
                    and not any(peer_api_client.node_host == api_client.node_host for api_client in self.remaining_api_clients)):
                self.remaining_api_clients.append(peer_api_client)

    def save(self, output_filepath):
        class PublicKeyAwareEncoder(json.JSONEncoder):
            def default(self, o):
                if isinstance(o, PublicKey):
                    return str(o)

                return json.JSONEncoder.default(self, o)

        log.info(f'saving nodes json to {output_filepath}')
        with open(output_filepath, 'wt', encoding='utf8') as outfile:
            json.dump(
                list(self.public_key_to_node_info_map.values()),
                outfile,
                indent=2,
                sort_keys='identity.name',
                cls=PublicKeyAwareEncoder)


def main():
    parser = argparse.ArgumentParser(description='downloads node information from a network')
    parser.add_argument('--resources', help='directory containing resources', required=True)
    parser.add_argument('--output', help='output file', required=True)
    parser.add_argument('--thread-count', help='number of threads', type=int, default=16)
    parser.add_argument('--timeout', help='peer timeout', type=int, default=20)
    parser.add_argument('--network', help='network name filter', default='mainnet')
    parser.add_argument('--certs', help='ssl certificate directory (required for Symbol peer node communication)')
    args = parser.parse_args()

    resources = load_resources(args.resources)
    downloader = NodeDownloader(resources, args.thread_count, args.timeout, args.network, args.certs)
    downloader.discover()
    downloader.save(args.output)


if '__main__' == __name__:
    main()
