import argparse

import yaml
from zenlog import log

from .utils.facade_utils import BlockchainDescriptor, create_blockchain_facade, save_transaction
from .utils.MnemonicRepository import MnemonicRepository
from .utils.SymbolAggregateBuilder import SymbolAggregateBuilder


class MultisigPreparer:
    def __init__(self, facade, output_directory, mnemonic_repository):
        (self.facade, self.output_directory, self.mnemonic_repository) = (facade, output_directory, mnemonic_repository)

    def save(self, transaction_dict):
        signer_key_pair = self.mnemonic_repository.load_key_pair(self.facade, transaction_dict['multisig_account'])
        cosignatory_key_pairs = [
            self.mnemonic_repository.load_key_pair(self.facade, account_descriptor)
            for account_descriptor in transaction_dict['cosigner_accounts']
        ]

        aggregate_builder = SymbolAggregateBuilder(self.facade, signer_key_pair, cosignatory_key_pairs)

        aggregate_builder.add_embedded_transaction({
            'type': 'multisigAccountModification',
            'signer_public_key': signer_key_pair.public_key,
            'min_approval_delta': int(transaction_dict['min_approval_delta']),
            'min_removal_delta': int(transaction_dict['min_removal_delta']),
            'address_additions': list(map(self.to_address, cosignatory_key_pairs))
        })

        aggregate_transaction = aggregate_builder.build(transaction_dict['fee_multiplier'], {
            'deadline': transaction_dict['deadline']
        })
        signature = aggregate_builder.sign(aggregate_transaction)

        save_transaction(self.facade, aggregate_transaction, signature, self.output_directory, transaction_dict['filename'])

    def to_address(self, key_pair):
        return self.facade.network.public_key_to_address(key_pair.public_key)


def prepare_multisig(output_directory, mnemonic_repository, transaction_dict):
    facade = create_blockchain_facade(BlockchainDescriptor('symbol', transaction_dict['network']))
    preparer = MultisigPreparer(facade, output_directory, mnemonic_repository)
    preparer.save(transaction_dict)


def main():
    parser = argparse.ArgumentParser(description='prepares transactions for creating symbol multisig accounts')
    parser.add_argument('--input', help='input file with information about multisigs to prepare', required=True)
    args = parser.parse_args()

    with open(args.input, 'rt') as infile:
        input_dict = yaml.load(infile, Loader=yaml.SafeLoader)

        mnemonic_repository = MnemonicRepository(input_dict['mnemonics'])

        for transaction_dict in input_dict['multisigs']:
            prepare_multisig(input_dict['output_directory'], mnemonic_repository, transaction_dict)

        log.info('prepared {} multisig account(s)'.format(len(input_dict['multisigs'])))


if '__main__' == __name__:
    main()
