from nem.pod import TransactionSnapshot
from nem.TimeoutHTTPAdapter import create_http_session

XYM_MOSAIC_ID = '6BED913FA20223F8'
MICROXYM_PER_XYM = 1000000.0


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
        xym_mosaic = next((mosaic for mosaic in json_account['mosaics'] if XYM_MOSAIC_ID == mosaic['id']), None)
        if xym_mosaic:
            account_info.balance = int(xym_mosaic['amount']) / MICROXYM_PER_XYM

        account_info.public_key = json_account['publicKey']
        account_info.importance = float(json_account['importance']) / (9 * 10 ** 15 - 1)

        account_info.remote_status = ['Unlinked', 'Main', 'Remote', 'Remote_Unlinked'][json_account['accountType']]
        return account_info

    def get_harvests(self, address):
        json_response = self._get_json('statements/transaction?targetAddress={}&receiptType=8515&order=desc'.format(address))

        snapshots = []
        for json_statement_envelope in json_response['data']:
            json_statement = json_statement_envelope['statement']

            snapshot = TransactionSnapshot(address, 'harvest')
            snapshot.height = int(json_statement['height'])

            for json_receipt in json_statement['receipts']:
                snapshot.amount += int(json_receipt['amount'])

            snapshot.amount /= MICROXYM_PER_XYM
            snapshot.collation_id = json_statement_envelope['id']
            snapshots.append(snapshot)

        return snapshots

    def _get_json(self, rest_path):
        json_http_headers = {'Content-type': 'application/json'}
        return self.session.get('http://{}:3000/{}'.format(self.node_host, rest_path), headers=json_http_headers).json()
