from symbolchain.core.CryptoTypes import PublicKey
from symbolchain.core.nis1.Network import Address, Network
from symbolchain.core.nis1.NetworkTimestamp import NetworkTimestamp

from nem.pod import TransactionSnapshot
from nem.TimeoutHTTPAdapter import create_http_session

MICROXEM_PER_XEM = 1000000.0
SUPERNODE_ACCOUNT_PUBLIC_KEY = 'd96366cdd47325e816ff86039a6477ef42772a455023ccddae4a0bd5d27b8d23'
TRANSACTION_TYPES = {
    'transfer': 257,
    'multisig': 4100
}


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
        json_response = self._get_account_page('harvests', address, start_id)

        snapshots = []
        for json_harvest in json_response['data']:
            snapshot = TransactionSnapshot(address, 'harvest')

            snapshot.timestamp = NetworkTimestamp(json_harvest['timeStamp']).to_datetime()
            snapshot.amount = int(json_harvest['totalFee']) / MICROXEM_PER_XEM
            snapshot.height = int(json_harvest['height'])
            snapshot.collation_id = int(json_harvest['id'])
            snapshots.append(snapshot)

        return snapshots

    def get_transfers(self, address, start_id=None):
        json_response = self._get_account_page('transfers/all', address, start_id)

        snapshots = []
        for json_transaction_and_meta in json_response['data']:
            json_transaction = json_transaction_and_meta['transaction']
            json_meta = json_transaction_and_meta['meta']

            if TRANSACTION_TYPES['multisig'] == int(json_transaction['type']):
                json_transaction = json_transaction['otherTrans']

            tag = 'supernode' if SUPERNODE_ACCOUNT_PUBLIC_KEY == json_transaction['signer'] else 'transfer'
            snapshot = TransactionSnapshot(address, tag)
            snapshot.timestamp = NetworkTimestamp(json_transaction['timeStamp']).to_datetime()

            (amount_microxem, fee_microxem) = self._process_xem_changes(snapshot, json_transaction)

            snapshot.amount = amount_microxem / MICROXEM_PER_XEM
            snapshot.fee_paid = fee_microxem / MICROXEM_PER_XEM
            snapshot.height = int(json_meta['height'])
            snapshot.collation_id = json_meta['id']
            snapshot.hash = json_meta['hash']['data']
            snapshots.append(snapshot)

        return snapshots

    @staticmethod
    def _process_xem_changes(snapshot, json_transaction):
        amount_microxem = 0
        fee_microxem = 0
        transaction_type = int(json_transaction['type'])
        if TRANSACTION_TYPES['transfer'] == transaction_type:
            if json_transaction.get('mosaics'):
                multiplier = int(json_transaction['amount'])

                for json_mosaic in json_transaction['mosaics']:
                    if 'nem' == json_mosaic['mosaicId']['namespaceId'] and 'xem' == json_mosaic['mosaicId']['name']:
                        amount_microxem += multiplier * int(json_mosaic['quantity'])
            else:
                amount_microxem = int(json_transaction['amount'])

            if snapshot.address != json_transaction['recipient']:
                amount_microxem *= -1
        else:
            snapshot.comments = 'unsupported transaction of type {}'.format(transaction_type)

        if NisClient._is_signer(snapshot.address, json_transaction):
            fee_microxem = -int(json_transaction['fee'])

        return (amount_microxem, fee_microxem)

    @staticmethod
    def _is_signer(address, json_transaction):
        return Address(address) == Network.MAINNET.public_key_to_address(PublicKey(json_transaction['signer']))

    def _get_account_page(self, name, address, start_id):
        rest_path = 'account/{}?address={}'.format(name, address)
        if start_id:
            rest_path += '&id={}'.format(start_id)

        return self._get_json(rest_path)

    def _get_json(self, rest_path):
        json_http_headers = {'Content-type': 'application/json'}
        return self.session.get('http://{}:7890/{}'.format(self.node_host, rest_path), headers=json_http_headers).json()
