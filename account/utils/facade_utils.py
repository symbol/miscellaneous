from collections import namedtuple
from pathlib import Path

from symbolchain.core.facade.NemFacade import NemFacade
from symbolchain.core.facade.SymbolFacade import SymbolFacade
from zenlog import log

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
