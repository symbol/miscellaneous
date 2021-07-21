from nem.pod import TransactionSnapshot
from nem.TimeoutHTTPAdapter import create_http_session

MICROXEM_PER_XEM = 1000000.0


class AccountInfo:
    def __init__(self):
        self.address = None
        self.vested_balance = 0
        self.balance = 0
        self.public_key = ''
        self.importance = 0.0
        self.harvested_blocks = 0

        self.remote_status = None


class NisClient:
    def __init__(self, host):
        self.session = create_http_session()
        self.node_host = host

    def get_chain_height(self):
        json_response = self._get_json('chain/height')
        return int(json_response['height'])

    def get_account_info(self, address):
        json_response = self._get_json('account/get?address={}'.format(address))

        json_account = json_response['account']
        json_meta = json_response['meta']

        account_info = AccountInfo()
        account_info.address = address
        account_info.vested_balance = json_account['vestedBalance'] / MICROXEM_PER_XEM
        account_info.balance = json_account['balance'] / MICROXEM_PER_XEM
        account_info.public_key = json_account['publicKey']
        account_info.importance = json_account['importance']
        account_info.harvested_blocks = json_account['harvestedBlocks']

        account_info.remote_status = json_meta['remoteStatus']
        return account_info

    def get_harvests(self, address, start_id=None):
        json_response = self._issue_account_request('harvests', address, start_id)

        snapshots = []
        for json_harvest in json_response['data']:
            snapshot = TransactionSnapshot(address, 'harvest')

            snapshot.timestamp = json_harvest['timeStamp']
            snapshot.amount = int(json_harvest['totalFee']) / MICROXEM_PER_XEM
            snapshot.height = int(json_harvest['height'])
            snapshot.collation_id = int(json_harvest['id'])
            snapshots.append(snapshot)

        return snapshots

    def _issue_account_request(self, name, address, start_id):
        rest_path = 'account/{}?address={}'.format(name, address)
        if start_id:
            rest_path += '&id={}'.format(start_id)

        return self._get_json(rest_path)

    def _get_json(self, rest_path):
        json_http_headers = {'Content-type': 'application/json'}
        return self.session.get('http://{}:7890/{}'.format(self.node_host, rest_path), headers=json_http_headers).json()
