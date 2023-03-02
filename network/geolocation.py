import argparse
import json
from socket import gaierror, error, gethostbyname
import threading
import queue
import time
from zenlog import log
from client.GeolocationClient import GeolocationClient

REQUEST_RATE = 15  # 15 requests / 1 minute
CHUNK_SIZE = 100  # up to 100 IPs per request

class NodeGeolocation:
    """
    Class for geolocating nodes from a JSON file using IP addresses.
    """

    def __init__(self, nodes_file_directory, output_file_directory):
        self.nodes_file_directory = nodes_file_directory
        self.output_file_directory = output_file_directory
        self.hosts = []

    def _create_host_ip_info(self, host):
        """
        Returns a dictionary with the hostname and IP address of a node.
        If an error occurs during the lookup, returns None.
        """

        try:
            ip_address = gethostbyname(host)

            if not host:
                return None
            return {'host': host, 'ip': ip_address}
        except (gaierror, error) as ex:
            log.error(f'Error {host}: {ex}')
            return None

    def get_nodes_geolocation(self):
        """
        Loads the list of nodes from a JSON file and creates a queue of IP addresses
        to be processed by the geolocation client.
        """

        with open(self.nodes_file_directory, 'r') as nodes_file:
            nodes = json.load(nodes_file)

        for node in nodes:
            result = self._create_host_ip_info(node['host'])
            if result is not None:
                self.hosts.append(result)

        log.info(f'loaded {len(self.hosts)} nodes from {self.nodes_file_directory}')

        ips = [host['ip'] for host in self.hosts]

        requestGeolocationQueue = queue.Queue()

        groups = [ips[i:i+CHUNK_SIZE] for i in range(0, len(ips), CHUNK_SIZE)]

        for i in range(len(groups)):
            requestGeolocationQueue.put(groups[i])

        t = threading.Thread(target=self._get_nodes_geolocation_thread, args=(requestGeolocationQueue,))
        t.start()

    def _process_ips(self, ips):
        """
        Processes the geolocation of the given IP addresses.
        """

        geolocation_client = GeolocationClient()
        result = geolocation_client.get_ip_geolocation(ips)

        self._update_host_geolocation(result)

    def _update_host_geolocation(self, geolocation_results):
        """
        Updates the 'geolocation' attribute of each host in hosts.
        """

        for host in self.hosts:
            for geolocation in geolocation_results:
                if host['ip'] == geolocation['query']:
                    host['geolocation'] = geolocation

    def _get_nodes_geolocation_thread(self, requestGeolocationQueue):
        """
        Method that runs in a separate thread to fetch the geolocation of the IP addresses
        in the `requestGeolocationQueue`.
        """

        log.info(f'starting crawler geolocation threads')

        totalQueue = requestGeolocationQueue.qsize()

        while True:
            if not requestGeolocationQueue.empty():
                ips = requestGeolocationQueue.get()

                self._process_ips(ips)

                if totalQueue > REQUEST_RATE:
                    time.sleep(60 / REQUEST_RATE)

                log.info(f'queue progress: {totalQueue - requestGeolocationQueue.qsize()} / {totalQueue}')
            else:
                log.info('completed')
                self.save(self.output_file_directory)
                break

    def save(self, output_filepath):
        log.info(f'saving nodes geolocation json to {output_filepath}')
        with open(output_filepath, 'wt', encoding='utf8') as outfile:
            json.dump(
                self.hosts,
                outfile,
                indent=2)

def main():
    parser = argparse.ArgumentParser(description='downloads node information from a network')
    parser.add_argument('--input', help='nodes json file', required=True)
    parser.add_argument('--output', help='output file', required=True)
    args = parser.parse_args()

    nodeGeolocation = NodeGeolocation(args.input, args.output)
    nodeGeolocation.get_nodes_geolocation()

if '__main__' == __name__:
    main()
