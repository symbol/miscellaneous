import argparse

from .utils.facade_utils import BasePreparer, main_loop, save_transaction


class TransferPreparer(BasePreparer):
    def save(self, transaction_dict):
        key_pair_repository = self.load_key_pair_repository(transaction_dict)

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
        if self._is_symbol_multisig(transaction_dict):
            return self._prepare_aggregate_transfer(key_pair_repository, amount, transaction_dict)

        signer_public_key = key_pair_repository.signer_key_pair.public_key
        properties = self._to_transfer_properties(signer_public_key, amount, transaction_dict)
        transfer_transaction = self.facade.transaction_factory.create(properties)

        if 0 == transfer_transaction.fee:  # calculate symbol fee
            transfer_transaction.fee = transfer_transaction.get_size() * transaction_dict['fee_multiplier']

        return transfer_transaction

    def _prepare_aggregate_transfer(self, key_pair_repository, amount, transaction_dict):
        main_public_key = key_pair_repository.main_public_key
        signer_public_key = key_pair_repository.signer_key_pair.public_key
        properties = self._to_transfer_properties(main_public_key, amount, transaction_dict)

        deadline = properties['deadline']
        del properties['deadline']

        aggregate_builder = key_pair_repository.create_symbol_aggregate_builder()

        # transfer the fee amount from the multisig account to the (co)signer account
        aggregate_builder.add_embedded_transaction({
            'type': 'transfer',
            'signer_public_key': main_public_key,
            'recipient_address': self.facade.network.public_key_to_address(signer_public_key),
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


def main():
    parser = argparse.ArgumentParser(description='prepares transactions for sending tokens from one account to another in two phases')
    parser.add_argument('--input', help='input file with information about transfers to prepare', required=True)
    args = parser.parse_args()

    main_loop(args, TransferPreparer, 'transfers')


if '__main__' == __name__:
    main()
