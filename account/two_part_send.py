import argparse

import yaml
from zenlog import log

from .utils.facade_utils import BlockchainDescriptor, create_blockchain_facade, save_transaction
from .utils.MnemonicRepository import MnemonicRepository
from .utils.SymbolAggregateBuilder import SymbolAggregateBuilder


class KeyPairRepository:
    def __init__(self, facade, mnemonic_repository):
        (self.facade, self.mnemonic_repository) = (facade, mnemonic_repository)

        self.signer_key_pair = None
        self.cosignatory_key_pairs = None

    def load(self, transaction_dict):
        self.signer_key_pair = self.mnemonic_repository.load_key_pair(self.facade, transaction_dict['signer_account'])

        if 'cosigner_accounts' in transaction_dict:
            self.cosignatory_key_pairs = [
                self.mnemonic_repository.load_key_pair(self.facade, account_descriptor)
                for account_descriptor in transaction_dict['cosigner_accounts']
            ]

    def create_symbol_aggregate_builder(self):
        return SymbolAggregateBuilder(self.facade, self.cosignatory_key_pairs[0], self.cosignatory_key_pairs[1:])


class TransferPreparer:
    def __init__(self, facade, output_directory, mnemonic_repository):
        (self.facade, self.output_directory, self.mnemonic_repository) = (facade, output_directory, mnemonic_repository)
        self.counter = 0

    def save(self, transaction_dict):
        key_pair_repository = KeyPairRepository(self.facade, self.mnemonic_repository)
        key_pair_repository.load(transaction_dict)

        seed_amount = int(transaction_dict['seed_amount'])
        sweep_amount = int(transaction_dict['sweep_amount']) - seed_amount

        transfer_seed = self._prepare_transfer(key_pair_repository, seed_amount, transaction_dict)
        transfer_sweep = self._prepare_transfer(key_pair_repository, sweep_amount, transaction_dict)

        total_fee = transfer_seed.fee + transfer_sweep.fee
        if self._is_symbol_transfer(transaction_dict):
            if not self._is_symbol_multisig(transaction_dict):
                currency_mosaic = transfer_sweep.mosaics[0]
                transfer_sweep.mosaics[0] = (currency_mosaic[0], currency_mosaic[1] - total_fee)
            else:
                currency_mosaic = transfer_sweep.transactions[1].mosaics[0]
                transfer_sweep.transactions[1].mosaics[0] = (currency_mosaic[0], currency_mosaic[1] - total_fee)

        else:
            transfer_sweep.amount -= total_fee

        self._save_transaction(key_pair_repository, transfer_seed, transaction_dict['filename_pattern'].format('seed'))
        self._save_transaction(key_pair_repository, transfer_sweep, transaction_dict['filename_pattern'].format('sweep'))

    @staticmethod
    def _is_symbol_transfer(transaction_dict):
        return 'mosaic_id' in transaction_dict

    @staticmethod
    def _is_symbol_multisig(transaction_dict):
        return 'cosigner_accounts' in transaction_dict

    def _prepare_transfer(self, key_pair_repository, amount, transaction_dict):
        signer_public_key = key_pair_repository.signer_key_pair.public_key
        if self._is_symbol_multisig(transaction_dict):
            return self._prepare_aggregate_transfer(key_pair_repository, amount, transaction_dict)

        properties = self._to_transfer_properties(signer_public_key, amount, transaction_dict)
        transfer_transaction = self.facade.transaction_factory.create(properties)

        if 0 == transfer_transaction.fee:  # calculate symbol fee
            transfer_transaction.fee = transfer_transaction.get_size() * transaction_dict['fee_multiplier']

        return transfer_transaction

    def _prepare_aggregate_transfer(self, key_pair_repository, amount, transaction_dict):
        signer_public_key = key_pair_repository.signer_key_pair.public_key
        properties = self._to_transfer_properties(signer_public_key, amount, transaction_dict)

        deadline = properties['deadline']
        del properties['deadline']

        cosignatory_key_pairs = key_pair_repository.cosignatory_key_pairs
        aggregate_builder = key_pair_repository.create_symbol_aggregate_builder()

        # transfer the fee amount from the multisig account to the (co)signer account
        aggregate_builder.add_embedded_transaction({
            'type': 'transfer',
            'signer_public_key': signer_public_key,
            'recipient_address': self.facade.network.public_key_to_address(cosignatory_key_pairs[0].public_key),
            'mosaics': [(transaction_dict['mosaic_id'], 0)]
        })
        aggregate_builder.add_embedded_transaction(properties)

        aggregate_transaction = aggregate_builder.build(transaction_dict['fee_multiplier'], {'deadline': deadline})
        aggregate_transaction.transactions[0].mosaics[0] = (transaction_dict['mosaic_id'], aggregate_transaction.fee)
        return aggregate_transaction

    def _to_transfer_properties(self, signer_public_key, amount, transaction_dict):
        deadline = int(transaction_dict['deadline']) + self.counter
        self.counter += 1

        properties = {
            'type': 'transfer',
            'signer_public_key': signer_public_key,
            'deadline': deadline,

            'recipient_address': self.facade.Address(transaction_dict['recipient_address'])
        }

        if 'message' in transaction_dict:
            properties['message'] = transaction_dict['message']

        if self._is_symbol_transfer(transaction_dict):
            properties['mosaics'] = [(transaction_dict['mosaic_id'], amount)]
        else:
            properties['amount'] = amount

        return properties

    def _save_transaction(self, key_pair_repository, transaction, name):
        if key_pair_repository.cosignatory_key_pairs:
            aggregate_builder = key_pair_repository.create_symbol_aggregate_builder()
            signature = aggregate_builder.sign(transaction)
        else:
            signature = self.facade.sign_transaction(key_pair_repository.signer_key_pair, transaction)

        save_transaction(self.facade, transaction, signature, self.output_directory, name)


def prepare_transfer(output_directory, mnemonic_repository, transaction_dict):
    facade = create_blockchain_facade(BlockchainDescriptor(**transaction_dict['blockchain']))
    preparer = TransferPreparer(facade, output_directory, mnemonic_repository)
    preparer.save(transaction_dict)


def main():
    parser = argparse.ArgumentParser(description='prepares transactions for sending tokens from one account to another in two phases')
    parser.add_argument('--input', help='input file with information about transfers to prepare', required=True)
    args = parser.parse_args()

    with open(args.input, 'rt') as infile:
        input_dict = yaml.load(infile, Loader=yaml.SafeLoader)

        mnemonic_repository = MnemonicRepository(input_dict['mnemonics'])

        for transaction_dict in input_dict['transfers']:
            prepare_transfer(input_dict['output_directory'], mnemonic_repository, transaction_dict)

        log.info('prepared {} transfer pair(s)'.format(len(input_dict['transfers'])))


if '__main__' == __name__:
    main()
