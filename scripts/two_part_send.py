import argparse
import os

import yaml
from zenlog import log

from .input_utils import BlockchainDescriptor, MnemonicRepository, create_blockchain_facade, extract_expected_address


class TransferPreparer:
    def __init__(self, facade, output_directory, mnemonic_repository):
        self.facade = facade
        self.output_directory = output_directory
        self.mnemonic_repository = mnemonic_repository

        self.counter = 0

    def load_key_pair(self, account_dict):
        expected_address = extract_expected_address(account_dict, self.facade)

        identifier = int(account_dict['identifier'])
        child_key_pair = self.mnemonic_repository.derive_child_key_pair(self.facade, account_dict['mnemonic'], identifier)
        actual_address = self.facade.network.public_key_to_address(child_key_pair.public_key)

        if expected_address != actual_address:
            raise Exception('{}: EXPECTED {} ACTUAL {}'.format(identifier, expected_address, actual_address))

        return child_key_pair

    @staticmethod
    def _is_symbol_transfer(transfer_dict):
        return 'mosaic_id' in transfer_dict

    def save(self, signer_key_pair, transfer_dict):
        seed_amount = int(transfer_dict['seed_amount'])
        sweep_amount = int(transfer_dict['sweep_amount'])

        signer_public_key = signer_key_pair.public_key
        transfer_seed = self._prepare_transfer(signer_public_key, seed_amount, transfer_dict)
        transfer_sweep = self._prepare_transfer(signer_public_key, sweep_amount - seed_amount, transfer_dict)

        total_fee = transfer_seed.fee + transfer_sweep.fee
        if self._is_symbol_transfer(transfer_dict):
            currency_mosaic = transfer_sweep.mosaics[0]
            transfer_sweep.mosaics[0] = (currency_mosaic[0], currency_mosaic[1] - total_fee)
        else:
            transfer_sweep.amount -= total_fee

        self._save_transaction(signer_key_pair, transfer_seed, transfer_dict['filename_pattern'].format('seed'))
        self._save_transaction(signer_key_pair, transfer_sweep, transfer_dict['filename_pattern'].format('sweep'))

    def _prepare_transfer(self, signer_public_key, amount, transfer_dict):
        properties = self._to_transfer_properties(signer_public_key, amount, transfer_dict)
        transfer = self.facade.transaction_factory.create(properties)

        if 0 == transfer.fee:  # calculate symbol fee
            transfer.fee = transfer.get_size() * transfer_dict['fee_multiplier']

        return transfer

    def _to_transfer_properties(self, signer_public_key, amount, transfer_dict):
        deadline = int(transfer_dict['deadline']) + self.counter
        self.counter += 1

        properties = {
            'type': 'transfer',
            'signer_public_key': signer_public_key,
            'deadline': deadline,

            'recipient_address': self.facade.Address(transfer_dict['recipient_address'])
        }

        if 'message' in transfer_dict:
            properties['message'] = transfer_dict['message']

        if self._is_symbol_transfer(transfer_dict):
            properties['mosaics'] = [(transfer_dict['mosaic_id'], amount)]
        else:
            properties['amount'] = amount

        return properties

    def _save_transaction(self, signer_key_pair, transaction, name):
        log.info('*** {} ***'.format(name))
        log.debug(transaction)

        signature = self.facade.sign_transaction(signer_key_pair, transaction)
        prepared_transaction_payload = self.facade.transaction_factory.attach_signature(transaction, signature)
        log.info('     hash: {}'.format(self.facade.hash_transaction(transaction)))
        log.info('signature: {}'.format(signature))

        output_filepath = os.path.join(self.output_directory, '{}.dat'.format(name))
        log.info('saving {} to {}'.format(name, output_filepath))

        with open(output_filepath, 'wb') as outfile:
            outfile.write(prepared_transaction_payload)


def prepare_transfer(output_directory, mnemonic_repository, transfer_dict):
    facade = create_blockchain_facade(BlockchainDescriptor(**transfer_dict['blockchain']))
    preparer = TransferPreparer(facade, output_directory, mnemonic_repository)

    signer_key_pair = preparer.load_key_pair(transfer_dict['signer_account'])
    preparer.save(signer_key_pair, transfer_dict)


def main():
    parser = argparse.ArgumentParser(description='verifies ownership of a set of accounts')
    parser.add_argument('--input', help='input file with information about transfers to prepare', required=True)
    args = parser.parse_args()

    with open(args.input, 'rt') as infile:
        input_dict = yaml.load(infile, Loader=yaml.SafeLoader)

        mnemonic_repository = MnemonicRepository(input_dict['mnemonics'])

        for transfer_dict in input_dict['transfers']:
            prepare_transfer(input_dict['output_directory'], mnemonic_repository, transfer_dict)

        log.info('prepared {} transfers'.format(len(input_dict['transfers'])))


if '__main__' == __name__:
    main()
