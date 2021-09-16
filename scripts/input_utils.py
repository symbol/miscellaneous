from collections import namedtuple

from symbolchain.core.Bip32 import Bip32
from symbolchain.core.CryptoTypes import PublicKey
from symbolchain.core.facade.NemFacade import NemFacade
from symbolchain.core.facade.SymbolFacade import SymbolFacade

BlockchainDescriptor = namedtuple('BlockchainDescriptor', ['name', 'network'])
MnemonicDescriptor = namedtuple('MnemonicDescriptor', ['phrase', 'passphrase'])


def create_blockchain_facade(blockchain_descriptor):
    return (NemFacade if 'nem' == blockchain_descriptor.name else SymbolFacade)(blockchain_descriptor.network)


def extract_expected_address(account_dict, facade):
    if ('public_key' in account_dict) == ('address' in account_dict):
        raise KeyError('exactly one of { "public_key", "address" } must be used to specify expected account')

    if 'public_key' in account_dict:
        return facade.network.public_key_to_address(PublicKey(account_dict['public_key']))

    return facade.Address(account_dict['address'])


class MnemonicRepository:
    def __init__(self, mnemonics_dict):
        self.mnemonic_descriptors = {}
        for mnemonic_dict in mnemonics_dict:
            self.mnemonic_descriptors[mnemonic_dict['name']] = MnemonicDescriptor(
                mnemonic_dict['mnemonic'],
                mnemonic_dict['mnemonic_passphrase'])

    def derive_child_key_pair(self, facade, mnemonic_name, identifier):
        mnemonic_descriptor = self.mnemonic_descriptors[mnemonic_name]
        bip32_root_node = Bip32(facade.BIP32_CURVE_NAME).from_mnemonic(mnemonic_descriptor.phrase, mnemonic_descriptor.passphrase)

        coin_id = 1 if 'testnet' == facade.network.name else facade.BIP32_COIN_ID
        child_node = bip32_root_node.derive_path([44, coin_id, identifier, 0, 0])
        return facade.bip32_node_to_key_pair(child_node)
