from binascii import unhexlify

from symbolchain.core.CryptoTypes import PublicKey
from symbolchain.core.sym.Network import Address, Network
from symbolchain.core.sym.NetworkTimestamp import NetworkTimestamp
from zenlog import log

from nem.pod import TransactionSnapshot
from nem.TimeoutHTTPAdapter import create_http_session

XYM_MOSAIC_IDS = ['6BED913FA20223F8', 'E74B99BA41F4AFEE']
MICROXYM_PER_XYM = 1000000.0
RECEIPT_TYPES = {
    'harvest': 0x2143,
    'inflation': 0x5143,
    'hashlock_expired': 0x2348,
    'mosaic_expiry': 0x414D,
    'namespace_expiry': 0x414E
}
TRANSACTION_TYPES = {
    'transfer': 0x4154,
    'aggregate_complete': 0x4141,
    'aggregate_bonded': 0x4142
}


class AccountInfo:
    def __init__(self):
        self.address = None
        self.balance = 0
        self.public_key = ''
        self.importance = 0.0

        self.remote_status = None


class SymClient:
    def __init__(self, host):
        self.session = create_http_session()
        self.node_host = host

    def get_chain_height(self):
        json_response = self._get_json('chain/info')
        return int(json_response['height'])

    def get_account_info(self, address):
        json_response = self._get_json('accounts/{}'.format(address))

        json_account = json_response['account']

        account_info = AccountInfo()
        account_info.address = address
        xym_mosaic = next((mosaic for mosaic in json_account['mosaics'] if mosaic['id'] in XYM_MOSAIC_IDS), None)
        if xym_mosaic:
            account_info.balance = int(xym_mosaic['amount']) / MICROXYM_PER_XYM

        account_info.public_key = json_account['publicKey']
        account_info.importance = float(json_account['importance']) / (9 * 10 ** 15 - 1)

        account_info.remote_status = ['Unlinked', 'Main', 'Remote', 'Remote_Unlinked'][json_account['accountType']]
        return account_info

    def get_harvests(self, address, start_id=None):
        json_response = self._get_page('statements/transaction?targetAddress={}&order=desc'.format(address), start_id)

        snapshots = []
        for json_statement_envelope in json_response['data']:
            json_statement = json_statement_envelope['statement']

            snapshot = TransactionSnapshot(address, 'harvest')
            snapshot.height = int(json_statement['height'])
            snapshot.timestamp = self._get_block_time_and_multiplier(snapshot.height)[0]

            for json_receipt in json_statement['receipts']:
                receipt_type = json_receipt['type']
                if any(RECEIPT_TYPES[name] == receipt_type for name in ['harvest', 'hashlock_expired']):
                    if Address(address) == Address(unhexlify(json_receipt['targetAddress'])):
                        snapshot.amount += int(json_receipt['amount'])
                elif receipt_type not in RECEIPT_TYPES.values():
                    log.warn('detected receipt of unknown type 0x{:X}'.format(receipt_type))
                    continue

            snapshot.amount /= MICROXYM_PER_XYM
            snapshot.collation_id = json_statement_envelope['id']
            snapshots.append(snapshot)

        return snapshots

    def get_transfers(self, address, start_id=None):
        json_response = self._get_page('transactions/confirmed?address={}&order=desc&embedded=true'.format(address), start_id)

        snapshots = []
        for json_transaction_and_meta in json_response['data']:
            json_transaction = json_transaction_and_meta['transaction']
            json_meta = json_transaction_and_meta['meta']

            snapshot = TransactionSnapshot(address, 'transfer')
            snapshot.height = int(json_meta['height'])
            (snapshot.timestamp, fee_multiplier) = self._get_block_time_and_multiplier(snapshot.height)

            snapshot.hash = json_meta['hash']
            (amount_microxym, fee_microxym) = self._process_xym_changes(snapshot, json_transaction, snapshot.hash, fee_multiplier)

            snapshot.amount = amount_microxym / MICROXYM_PER_XYM
            snapshot.fee_paid = fee_microxym / MICROXYM_PER_XYM
            snapshot.collation_id = json_transaction_and_meta['id']
            snapshots.append(snapshot)

        return snapshots

    def _process_xym_changes(self, snapshot, json_transaction, transaction_hash, fee_multiplier):
        effective_fee = int(json_transaction['size'] * fee_multiplier)

        amount_microxym = 0
        fee_microxym = 0
        transaction_type = json_transaction['type']
        if self._is_aggregate(transaction_type):
            json_aggregate_transaction = self._get_json('transactions/confirmed/{}'.format(transaction_hash))
            json_embedded_transactions = [
                json_embedded_transaction_and_meta['transaction']
                for json_embedded_transaction_and_meta in json_aggregate_transaction['transaction']['transactions']
            ]
            amount_microxym = self._calculate_transfer_amount(snapshot.address, json_embedded_transactions)
        elif TRANSACTION_TYPES['transfer'] == transaction_type:
            amount_microxym = self._calculate_transfer_amount(snapshot.address, [json_transaction])
        else:
            snapshot.comments = 'unsupported transaction of type 0x{:X}'.format(transaction_type)

        if self._is_signer(snapshot.address, json_transaction):
            fee_microxym = -effective_fee

        return (amount_microxym, fee_microxym)

    @staticmethod
    def _calculate_transfer_amount(address, json_transactions):
        amount_microxym = 0
        for json_transaction in json_transactions:
            if TRANSACTION_TYPES['transfer'] != json_transaction['type']:
                continue

            direction = 0
            if SymClient._is_signer(address, json_transaction):
                direction = -1
            elif SymClient._is_recipient(address, json_transaction):
                direction = 1

            for json_mosaic in json_transaction['mosaics']:
                if json_mosaic['id'] in XYM_MOSAIC_IDS:
                    amount_microxym += int(json_mosaic['amount']) * direction

        return amount_microxym

    @staticmethod
    def _is_signer(address, json_transaction):
        return Address(address) == Network.PUBLIC.public_key_to_address(PublicKey(json_transaction['signerPublicKey']))

    @staticmethod
    def _is_recipient(address, json_transaction):
        return Address(address) == Address(unhexlify(json_transaction['recipientAddress']))

    @staticmethod
    def _is_aggregate(transaction_type):
        return any(TRANSACTION_TYPES[name] == transaction_type for name in ['aggregate_complete', 'aggregate_bonded'])

    def _get_block_time_and_multiplier(self, height):
        json_block_and_meta = self._get_json('blocks/{}'.format(height))
        json_block = json_block_and_meta['block']
        return (NetworkTimestamp(int(json_block['timestamp'])).to_datetime(), json_block['feeMultiplier'])

    def _get_page(self, rest_path, start_id):
        return self._get_json(rest_path if not start_id else '{}&offset={}'.format(rest_path, start_id))

    def _get_json(self, rest_path):
        json_http_headers = {'Content-type': 'application/json'}
        return self.session.get('http://{}:3000/{}'.format(self.node_host, rest_path), headers=json_http_headers).json()
