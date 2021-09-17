import sha3
from symbolchain.core.CryptoTypes import Hash256
from symbolchain.core.symbol.MerkleHashBuilder import MerkleHashBuilder

COSIGNATURE_SIZE = 104


class SymbolAggregateBuilder:
    def __init__(self, facade, signer_key_pair, cosignatory_key_pairs):
        self.facade = facade
        self.signer_key_pair = signer_key_pair
        self.cosignatory_key_pairs = cosignatory_key_pairs

        self.embedded_transactions = []

    def add_embedded_transaction(self, properties):
        self.embedded_transactions.append(self.facade.transaction_factory.create_embedded(properties))

    def build(self, fee_multiplier, properties):
        aggregate_transaction = self.facade.transaction_factory.create({
            **properties,
            'type': 'aggregateComplete',
            'signer_public_key': self.signer_key_pair.public_key,
            'transactions_hash': self._calculate_transactions_hash(),
            'transactions': self.embedded_transactions
        })

        aggregate_transaction.fee = (aggregate_transaction.get_size() + len(self.cosignatory_key_pairs) * COSIGNATURE_SIZE) * fee_multiplier
        return aggregate_transaction

    def sign(self, aggregate_transaction):
        # note: it's important to SIGN the transaction BEFORE adding cosignatures
        signature = self.facade.sign_transaction(self.signer_key_pair, aggregate_transaction)
        self.facade.transaction_factory.attach_signature(aggregate_transaction, signature)

        self._add_cosignatures(aggregate_transaction)
        return signature

    def _calculate_transactions_hash(self):
        hash_builder = MerkleHashBuilder()
        for embedded_transaction in self.embedded_transactions:
            hash_builder.update(Hash256(sha3.sha3_256(embedded_transaction.serialize()).digest()))

        return hash_builder.final()

    def _add_cosignatures(self, aggregate_transaction):
        aggregate_transaction_hash = self.facade.hash_transaction(aggregate_transaction).bytes
        for key_pair in self.cosignatory_key_pairs:
            cosignature = (0, key_pair.public_key.bytes, key_pair.sign(aggregate_transaction_hash).bytes)
            aggregate_transaction.cosignatures.append(cosignature)
