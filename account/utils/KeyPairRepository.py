from symbolchain.core.CryptoTypes import PublicKey

from .SymbolAggregateBuilder import SymbolAggregateBuilder


class KeyPairRepository:
    def __init__(self, facade, mnemonic_repository):
        (self.facade, self.mnemonic_repository) = (facade, mnemonic_repository)

        self.main_public_key = None
        self.signer_key_pair = None
        self.cosignatory_key_pairs = None

    def load(self, transaction_dict):
        if 'signer_account' in transaction_dict:
            self.signer_key_pair = self.mnemonic_repository.load_key_pair(self.facade, transaction_dict['signer_account'])
        else:
            self.main_public_key = PublicKey(transaction_dict['main_public_key'])

            cosignatory_key_pairs = [
                self.mnemonic_repository.load_key_pair(self.facade, account_descriptor)
                for account_descriptor in transaction_dict['cosigner_accounts']
            ]

            self.signer_key_pair = cosignatory_key_pairs[0]
            self.cosignatory_key_pairs = cosignatory_key_pairs[1:]

    def create_symbol_aggregate_builder(self):
        return SymbolAggregateBuilder(self.facade, self.signer_key_pair, self.cosignatory_key_pairs)
