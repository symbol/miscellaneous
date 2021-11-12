import argparse
import json
import time
from threading import Lock, Thread

from requests.exceptions import RequestException
from symbolchain.core.CryptoTypes import PublicKey
from symbolchain.core.nem.Network import Network as NemNetwork
from symbolchain.core.Network import NetworkLocator
from zenlog import log

from client.ResourceLoader import load_resources, locate_blockchain_client_class


class NodeDownloader:
    # pylint: disable=too-many-instance-attributes

    def __init__(self, resources, thread_count, timeout, certificate_directory):
        self.resources = resources
        self.thread_count = thread_count
        self.timeout = timeout
        self.certificate_directory = certificate_directory

        self.api_client_class = locate_blockchain_client_class(resources)
        self.visited_hosts = set()
        self.remaining_api_clients = []
        self.public_key_to_node_info_map = {}
        self.busy_thread_count = 0
        self.lock = Lock()

    def discover(self):
        log.info('seeding crawler with known hosts')
        self.remaining_api_clients = [
            self.api_client_class(node_descriptor.host) for node_descriptor in self.resources.nodes.find_all_by_role(None)
        ]

        log.info('starting {} crawler threads'.format(self.thread_count))
        threads = [Thread(target=self._discover_thread) for i in range(0, self.thread_count)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        log.info('crawling completed and discovered {} nodes'.format(len(self.public_key_to_node_info_map)))

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

            log.debug('processing {} [{} discovered, {} remaining, {} busy]'.format(
                api_client.node_host,
                len(self.public_key_to_node_info_map),
                len(self.remaining_api_clients),
                self.busy_thread_count))

            is_reachable = False
            try:
                json_node = api_client.get_node_info()

                if 'nem' == self.resources.friendly_name:
                    network = NetworkLocator.find_by_identifier(NemNetwork.NETWORKS, json_node['metaData']['networkId'])
                    node_address = network.public_key_to_address(PublicKey(json_node['identity']['public-key']))
                    main_account_info = api_client.get_account_info(node_address, forwarded=True)

                    if 'ACTIVE' == main_account_info.remote_status:
                        json_node['identity']['node-public-key'] = json_node['identity']['public-key']
                        json_node['identity']['public-key'] = main_account_info.public_key

                    main_public_key = json_node['identity']['public-key']
                else:
                    main_public_key = json_node['publicKey']

                is_reachable = True

                json_peers = api_client.get_peers()
            except (RequestException, TimeoutError, ConnectionRefusedError):
                log.warning('failed to load peers from {}:{} (reachable node? {})'.format(
                    api_client.node_host,
                    api_client.node_port,
                    is_reachable))
                json_peers = []

            with self.lock:
                if is_reachable:
                    self._update(main_public_key, json_node, json_peers)

                self.busy_thread_count -= 1

            if self.busy_thread_count < self.thread_count - 1:
                log.debug('idling threads detected; only {} busy'.format(self.busy_thread_count))

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
        log.info('saving nodes json to {}'.format(output_filepath))
        with open(output_filepath, 'w') as outfile:
            json.dump(list(self.public_key_to_node_info_map.values()), outfile, indent=2, sort_keys='identity.name')


def main():
    parser = argparse.ArgumentParser(description='downloads node information from a network')
    parser.add_argument('--resources', help='directory containing resources', required=True)
    parser.add_argument('--output', help='output file', required=True)
    parser.add_argument('--thread-count', help='number of threads', type=int, default=16)
    parser.add_argument('--timeout', help='peer timeout', type=int, default=20)
    parser.add_argument('--certs', help='ssl certificate directory (required for Symbol peer node communication)')
    args = parser.parse_args()

    resources = load_resources(args.resources)
    downloader = NodeDownloader(resources, args.thread_count, args.timeout, args.certs)
    downloader.discover()
    downloader.save(args.output)


if '__main__' == __name__:
    main()
