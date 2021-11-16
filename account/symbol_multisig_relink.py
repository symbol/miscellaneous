import argparse

from symbolchain.core.CryptoTypes import PublicKey

from .utils.facade_utils import BasePreparer, main_loop, save_transaction


class RelinkPreparer(BasePreparer):
    def save(self, transaction_dict):
        key_pair_repository = self.load_key_pair_repository(transaction_dict)

        relink = self._prepare_aggregate_transfer(key_pair_repository, transaction_dict)

        self._save_transaction(key_pair_repository, relink, transaction_dict['filename'])

    def _prepare_aggregate_transfer(self, key_pair_repository, transaction_dict):
        signer_public_key = key_pair_repository.signer_key_pair.public_key

        deadline = int(transaction_dict['deadline']) + self.counter
        self.counter += 1

        aggregate_builder = key_pair_repository.create_symbol_aggregate_builder()

        # transfer the fee amount from the multisig account to the (co)signer account
        aggregate_builder.add_embedded_transaction({
            'type': 'transfer',
            'signer_public_key': key_pair_repository.main_public_key,
            'recipient_address': self.facade.network.public_key_to_address(signer_public_key),
            'mosaics': [(transaction_dict['fee_mosaic_id'], 0)]
        })

        # add link transactions
        for link_action in ['unlink', 'link']:
            if link_action in transaction_dict:
                aggregate_builder.add_embedded_transaction({
                    'signer_public_key': key_pair_repository.main_public_key,
                    'link_action': 1 if 'link' == link_action else 0,
                    **self._to_link_properties(transaction_dict[link_action])
                })

        aggregate_transaction = aggregate_builder.build(transaction_dict['fee_multiplier'], {'deadline': deadline})
        aggregate_transaction.transactions[0].mosaics[0] = (transaction_dict['fee_mosaic_id'], aggregate_transaction.fee)
        return aggregate_transaction

    @staticmethod
    def _to_link_properties(transaction_dict):
        return {
            'type': 'votingKeyLink',
            'linked_public_key': PublicKey(transaction_dict['linked_public_key']),
            'start_epoch': transaction_dict['start_epoch'],
            'end_epoch': transaction_dict['end_epoch'],
        }

    def _save_transaction(self, key_pair_repository, transaction, name):
        aggregate_builder = key_pair_repository.create_symbol_aggregate_builder()
        signature = aggregate_builder.sign(transaction)

        save_transaction(self.facade, transaction, signature, self.output_directory, name)


def main():
    parser = argparse.ArgumentParser(description='prepares transactions for relinking Symbol voting public keys')
    parser.add_argument('--input', help='input file with information about relinks to prepare', required=True)
    args = parser.parse_args()

    main_loop(args, RelinkPreparer, 'links')


if '__main__' == __name__:
    main()
