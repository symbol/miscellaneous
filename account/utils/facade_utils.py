from collections import namedtuple
from pathlib import Path

import yaml
from symbolchain.core.facade.NemFacade import NemFacade
from symbolchain.core.facade.SymbolFacade import SymbolFacade
from zenlog import log

from .KeyPairRepository import KeyPairRepository
from .MnemonicRepository import MnemonicRepository

BlockchainDescriptor = namedtuple('BlockchainDescriptor', ['name', 'network'])


def create_blockchain_facade(blockchain_descriptor):
    return (NemFacade if 'nem' == blockchain_descriptor.name else SymbolFacade)(blockchain_descriptor.network)


def save_transaction(facade, transaction, signature, output_directory, name):
    prepared_transaction_payload = facade.transaction_factory.attach_signature(transaction, signature)

    log.info('*** {} ***'.format(name))
    log.debug(transaction)

    log.info('     hash: {}'.format(facade.hash_transaction(transaction)))
    log.info('signature: {}'.format(signature))

    output_filepath = Path(output_directory) / '{}.dat'.format(name)
    log.info('saving "{}" to "{}"'.format(name, output_filepath))

    with open(output_filepath, 'wb') as outfile:
        outfile.write(prepared_transaction_payload)


def main_loop(args, preparer_class, property_name):
    with open(args.input, 'rt') as infile:
        input_dict = yaml.load(infile, Loader=yaml.SafeLoader)

        mnemonic_repository = MnemonicRepository(input_dict['mnemonics'])

        for transaction_dict in input_dict[property_name]:
            facade = create_blockchain_facade(BlockchainDescriptor(**transaction_dict['blockchain']))
            preparer = preparer_class(facade, input_dict['output_directory'], mnemonic_repository)
            preparer.save(transaction_dict)

    log.info('prepared {} {}'.format(len(input_dict[property_name]), property_name))


class BasePreparer:
    def __init__(self, facade, output_directory, mnemonic_repository):
        (self.facade, self.output_directory, self.mnemonic_repository) = (facade, output_directory, mnemonic_repository)
        self.counter = 0

    def load_key_pair_repository(self, transaction_dict):
        key_pair_repository = KeyPairRepository(self.facade, self.mnemonic_repository)
        key_pair_repository.load(transaction_dict)
        return key_pair_repository
