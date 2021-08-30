import argparse
import csv
import sys

from zenlog import log

from core.ResourceLoader import create_blockchain_api_client, load_resources


class Reconciler():
    def __init__(self, resources_path, mode):
        self.resources = load_resources(resources_path)
        self.mode = mode

        self.rows = []
        self.num_errors = 0

    def load(self, filename):
        log.info('loading input from {}'.format(filename))

        with open(filename, 'r') as infile:
            csv_reader = csv.DictReader(infile)

            for row in csv_reader:
                self.rows.append(row)

    def verify(self):
        if 'all' == self.mode:
            self._verify_all()
        else:
            self._verify_spot()

    @property
    def _account_names(self):
        return list(self.rows[0].keys())[2:]

    def _verify_all(self):
        api_client = create_blockchain_api_client(self.resources, 'historical')

        for account_name in self._account_names:
            log.info('[*] verifying {} balances for {}'.format(self.mode, account_name))
            account_descriptor = self.resources.accounts.try_find_by_name(account_name)

            calculated_balance = 0
            for row in self.rows:
                calculated_balance += float(row[account_name])
                calculated_balance = round(calculated_balance, 6)

                reported_balance = api_client.get_historical_balance(account_descriptor.address, row['height'])

                self._print_message(row, account_name, calculated_balance, reported_balance)

    def _verify_spot(self):
        api_client = create_blockchain_api_client(self.resources)

        for account_name in self._account_names:
            log.info('[*] verifying {} balances for {}'.format(self.mode, account_name))
            account_descriptor = self.resources.accounts.try_find_by_name(account_name)

            calculated_balance = 0
            for row in self.rows:
                calculated_balance += float(row[account_name])
                calculated_balance = round(calculated_balance, 6)

            reported_balance = api_client.get_account_info(account_descriptor.address).balance

            self._print_message(self.rows[-1], account_name, calculated_balance, reported_balance)

    def _print_message(self, row, account_name, calculated_balance, reported_balance):
        main_message_body = '<{}> {} at H{} has balance {}'.format(
            row['date'],
            account_name,
            row['height'],
            calculated_balance)

        if calculated_balance == reported_balance:
            log.info('[+] {}'.format(main_message_body))
        else:
            difference_balance = round(calculated_balance - reported_balance, 6)
            log.error('[-] {} but network reported {} ({})'.format(main_message_body, reported_balance, difference_balance))
            self.num_errors += 1


def main():
    parser = argparse.ArgumentParser(description='reconciles an account balance table with a network')
    parser.add_argument('--input', help='input account balance table', required=True)
    parser.add_argument('--resources', help='input resources file', required=True)
    parser.add_argument('--mode', help='reconciliation mode', choices=('spot', 'all'), required=True)

    args = parser.parse_args()

    reconciler = Reconciler(args.resources, args.mode)
    reconciler.load(args.input)
    reconciler.verify()

    sys.exit(reconciler.num_errors)


if '__main__' == __name__:
    main()
