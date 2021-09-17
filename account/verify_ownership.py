import argparse
import sys

import yaml

from .utils.facade_utils import BlockchainDescriptor, create_blockchain_facade
from .utils.MnemonicRepository import MnemonicRepository


def print_conditional_message(message, is_success):
    color_codes = {'green': 32, 'red': 31}
    print('\033[{}m{}\033[39m'.format(color_codes['green' if is_success else 'red'], message))


def process_group(mnemonic_repository, group_dict):
    facade = create_blockchain_facade(BlockchainDescriptor(**group_dict['blockchain']))

    num_matches = 0
    num_failures = 0
    for account_dict in group_dict['accounts']:
        expected_address = MnemonicRepository.extract_expected_address(facade, account_dict)

        identifier = int(account_dict['identifier'])
        child_key_pair = mnemonic_repository.derive_child_key_pair(facade, group_dict['mnemonic'], identifier)
        actual_address = facade.network.public_key_to_address(child_key_pair.public_key)

        is_match = expected_address == actual_address
        if is_match:
            num_matches += 1
        else:
            num_failures += 1

        print_conditional_message(
            'EXPECTED {} {} ACTUAL {}'.format(expected_address, '==' if is_match else '!=', actual_address),
            is_match)

    return (num_matches, num_failures)


def main():
    parser = argparse.ArgumentParser(description='verifies account derivations from a BIP32 seed and passphrase')
    parser.add_argument('--input', help='input file with information about accounts to verify', required=True)
    args = parser.parse_args()

    num_total_matches = 0
    num_total_failures = 0
    with open(args.input, 'rt') as infile:
        input_dict = yaml.load(infile, Loader=yaml.SafeLoader)

        mnemonic_repository = MnemonicRepository(input_dict['mnemonics'])

        for group_dict in input_dict['tests']:
            print(group_dict['blockchain'])

            num_matches, num_failures = process_group(mnemonic_repository, group_dict)

            message_prefix = 'SUCCESS' if 0 == num_failures else 'FAILURE'
            print_conditional_message('{} {}/{}'.format(message_prefix, num_matches, num_matches + num_failures), 0 == num_failures)
            print()

            num_total_matches += num_matches
            num_total_failures += num_failures

    print_conditional_message('{} MATCHES, {} FAILURES'.format(num_total_matches, num_total_failures), 0 == num_total_failures)
    sys.exit(num_total_failures)


if '__main__' == __name__:
    main()
