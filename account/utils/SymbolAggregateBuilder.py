from symbolchain import sc


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
			'type': 'aggregate_complete_transaction_v2',
			'signer_public_key': self.signer_key_pair.public_key,
			'transactions': self.embedded_transactions
		})

		aggregate_transaction_size = aggregate_transaction.size + len(self.cosignatory_key_pairs) * sc.Cosignature().size
		aggregate_transaction.fee = sc.Amount(aggregate_transaction_size * fee_multiplier)
		return aggregate_transaction

	def sign(self, aggregate_transaction):
		# some of the account scripts directly modify embedded transactions, so always recalculate the transactions_hash before signing
		transactions_hash = self.facade.hash_embedded_transactions(aggregate_transaction.transactions)
		aggregate_transaction.transactions_hash = sc.Hash256(transactions_hash.bytes)

		# note: it's important to SIGN the transaction BEFORE adding cosignatures
		signature = self.facade.sign_transaction(self.signer_key_pair, aggregate_transaction)
		self.facade.transaction_factory.attach_signature(aggregate_transaction, signature)

		self._add_cosignatures(aggregate_transaction)
		return signature

	def _add_cosignatures(self, aggregate_transaction):
		aggregate_transaction.cosignatures.extend([
			self.facade.cosign_transaction(key_pair, aggregate_transaction) for key_pair in self.cosignatory_key_pairs
		])
