from collections import namedtuple

from symbolchain.core.Bip32 import Bip32
from symbolchain.core.CryptoTypes import PublicKey

MnemonicDescriptor = namedtuple('MnemonicDescriptor', ['phrase', 'passphrase'])


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

    def load_key_pair(self, facade, account_dict):
        expected_address = self.extract_expected_address(facade, account_dict)

        identifier = int(account_dict['identifier'])
        child_key_pair = self.derive_child_key_pair(facade, account_dict['mnemonic'], identifier)

        actual_address = facade.network.public_key_to_address(child_key_pair.public_key)

        if expected_address != actual_address:
            raise Exception('{}: EXPECTED {} ACTUAL {}'.format(identifier, expected_address, actual_address))

        return child_key_pair

    @staticmethod
    def extract_expected_address(facade, account_dict):
        if ('public_key' in account_dict) == ('address' in account_dict):
            raise KeyError('exactly one of { "public_key", "address" } must be used to specify expected account')

        if 'public_key' in account_dict:
            return facade.network.public_key_to_address(PublicKey(account_dict['public_key']))

        return facade.Address(account_dict['address'])
