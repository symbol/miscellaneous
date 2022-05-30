#!/usr/bin/env python3
"""Symbol block data processing script"""

import argparse
import csv
import functools
import os
import sys
from binascii import hexlify

import msgpack
import pandas as pd
from tqdm import tqdm

from block.extractor.util import public_key_to_address

HEADER_KEYS = [
    'timestamp',
    'size',
    'reserved_1',
    'signature',
    'signer_public_key',
    'reserved_2',
    'version',
    'network',
    'type',
    'height',
    'difficulty',
    'generation_hash_proof',
    'previous_block_hash',
    'transactions_hash',
    'receipts_hash',
    'state_hash',
    'beneficiary_address',
    'fee_multiplier',
    'harvester',
    'statement_count',
    'tx_count',
    'total_fee']


TX_KEYS = [
    'timestamp',
    'size',
    'signature',
    'signer_public_key',
    'type',
    'max_fee',
    'deadline',
    'id',
    'height',
    'recipient_address',
    'message_size',
    'mosaics',
    'message',
    'linked_public_key',
    'link_action',
    'mosaic',
    'duration',
    'hash',
    'secret',
    'mosaic_id',
    'amount',
    'hash_algorithm',
    'restriction_type',
    'restriction_additions',
    'restriction_deletions',
    'nonce',
    'flags',
    'divisibility',
    'delta',
    'action',
    'source_address',
    'min_removal_delta',
    'min_approval_delta',
    'address_additions',
    'address_deletions',
    'registration_type',
    'name_size',
    'name',
    'parent_id',
    'namespace_id',
    'alias_action',
    'proof_size',
    'proof',
    'target_address',
    'scoped_metadata_key',
    'value_size_delta',
    'value_size',
    'value',
    'address',
    'target_mosaic_id',
    'start_point',
    'end_point',
    'target_namespace_id',
]

ADDR_FIELDS = [
    'recipient_address',
    'source_address',
    'address_additions',
    'address_deletions',
    'target_address',
    'address',
]


PUBKEY_FIELDS = [
    'signer_public_key',
    'linked_public_key',
]


TX_KEYS_TO_DROP = [
    'payload',
    'version',
    'network',
    'reserved_1',
    'reserved_2',
    'transfer_transaction_body_reserved_2',
    'transfer_transaction_body_reserved_1',
    'multisig_account_modificaion_transacion_body_reserved_1',
    'account_restriction_transaction_body_reserved_1',
    'mosaics_count',
    'address_additions_count',
    'address_deletions_count',
    'restriction_additions_count',
    'restriction_deletions_count'
]


def get_block_stats(block):
    """Extract summary data from a block and flatten for tabular manipulation"""
    data = block['header'].copy()
    data['statement_count'] = block['footer']['statement_count']
    data['tx_count'] = block['footer']['tx_count']
    data['total_fee'] = block['footer']['total_fee']
    for key, value in data.items():
        if isinstance(value, bytes):
            data[key] = value.decode('utf-8')
    return data


def get_tx_stats(block):
    """Extract transaction data from a block and flatten for tabular manipulation"""
    data = []
    header = block['header']

    # handle transactions
    for transaction in block['footer']['transactions']:
        if transaction['type'] in [b'4141', b'4241']:  # aggregate transaction, append subtx instead
            for sub_transaction in transaction['payload']['embedded_transactions']:
                data.append(sub_transaction.copy())
        else:
            data.append(transaction.copy())

    # determine whether IDs are being handled appropriately; have some entry for headers of aggregate transactions?
    for transaction in data:
        transaction['height'] = header['height']
        transaction['timestamp'] = header['timestamp']
        transaction.update(transaction['payload'])
        for key, value in list(transaction.items()):
            if key in TX_KEYS_TO_DROP:
                del transaction[key]
            elif isinstance(value, bytes):
                try:
                    transaction[key] = value.decode('utf-8')
                except UnicodeDecodeError:
                    transaction[key] = hexlify(value).decode('utf-8')
            elif isinstance(value, list):
                transaction[key] = str(value)

    return data


def guarded_convert(pubkey_string):
    """Convert address conditional on a check to ensure valid public key format"""
    if isinstance(pubkey_string, str) and len(pubkey_string) == 64:
        return public_key_to_address(bytes.fromhex(pubkey_string))
    return pubkey_string


def filter_transactions(transaction_df, address=None, transaction_types=None, start_datetime='1900-01-01', end_datetime='2200-01-01'):
    """Filter processed transactions based on dates, tx types, and address"""

    start_datetime = pd.to_datetime(start_datetime)
    end_datetime = pd.to_datetime(end_datetime)

    transaction_df = transaction_df.loc[start_datetime:end_datetime]
    if transaction_df.empty:
        return transaction_df

    filter_key = None

    # filter based on all address/public key fields for completeness
    if address is not None:
        filter_key = pd.Series(False, index=transaction_df.index)
        for field in PUBKEY_FIELDS:
            filter_key = filter_key | transaction_df[field].apply(lambda x: guarded_convert(x) == address)
        for field in ADDR_FIELDS:
            filter_key = filter_key | (transaction_df[field] == address)

    if transaction_types is not None:
        if filter_key is None:
            filter_key = pd.Series(True, index=transaction_df.index)
        filter_key = filter_key & transaction_df['type'].isin(transaction_types)

    return transaction_df[filter_key]


def process_tx_file(transaction_file, address=None, transaction_types=None, start_datetime='1900-01-01', end_datetime='2200-01-01'):
    """Read a processed transaction file, then stream chunks through filter"""
    transaction_chunks = pd.read_csv(transaction_file, index_col=0, parse_dates=True, chunksize=10000)
    filtered = []
    for chunk in transaction_chunks:
        filtered.append(filter_transactions(chunk, address, transaction_types, start_datetime, end_datetime))
    return pd.concat(filtered, axis=0)


def decode_msgpack(packed_data):
    """Recursively parse msgpack data to decode dict keys"""
    decoded_data = packed_data
    if isinstance(packed_data, dict):
        decoded_data = {}
        for key, value in packed_data.items():
            decoded_data[key.decode('utf-8')] = decode_msgpack(value)
    elif isinstance(packed_data, list):
        decoded_data = []
        for value in packed_data:
            decoded_data.append(decode_msgpack(value))
    return decoded_data


def main(args):
    # pylint: disable=too-many-locals, consider-using-with

    header_writer = csv.DictWriter(
        open(os.path.join(args.output, args.header_save_path), 'a' if args.append else 'w', encoding='utf8'),
        HEADER_KEYS,
        extrasaction='ignore',
        escapechar='\\',
        quoting=csv.QUOTE_MINIMAL)

    transaction_writer = csv.DictWriter(
        open(os.path.join(args.output, args.tx_save_path), 'a' if args.append else 'w', encoding='utf8'),
        TX_KEYS,
        extrasaction='ignore',
        escapechar='\\',
        quoting=csv.QUOTE_MINIMAL)

    # build a raw bytes unpacker; unicode errors ignored as tx serialization is not always valid unicode text
    unpacker = msgpack.Unpacker(open(args.input, 'rb'), unicode_errors=None, raw=True)

    final_height = 0
    if args.append:
        old_headers = pd.read_csv(os.path.join(args.output, args.header_save_path), chunksize=1024)
        while True:
            try:
                chunk = next(old_headers)
            except StopIteration:  # we have found the end of the file
                final_height = chunk.iloc[-1]['height']
                break
        for _ in range(final_height):
            unpacker.skip()
    else:
        header_writer.writeheader()
        transaction_writer.writeheader()

    for block in tqdm(unpacker, total=args.total-final_height):
        block = decode_msgpack(block)

        header = get_block_stats(block)
        header['timestamp'] = pd.to_datetime(header['timestamp'], origin=pd.to_datetime('2021-03-16 00:06:25'), unit='ms')
        header_writer.writerow(header)

        transactions = get_tx_stats(block)
        for transaction in transactions:
            transaction['timestamp'] = pd.to_datetime(transaction['timestamp'], origin=pd.to_datetime('2021-03-16 00:06:25'), unit='ms')
        transaction_writer.writerows(transactions)


def parse_args(argv):
    parser = argparse.ArgumentParser(argv)
    parser.add_argument('--input', type=str, default='resources/block_data.msgpack', help='file containing extracted block data')
    parser.add_argument('--output', type=str, default='resources', help='directory to dump output')
    parser.add_argument('--append', action='store_true', help='add to existing data instead of rebuilding files from scratch')
    parser.add_argument('--header_save_path', type=str, default='block_headers.csv', help='file to write the header table to')
    parser.add_argument('--tx_save_path', type=str, default='transactions.csv', help='file to write the transaction table to')
    parser.add_argument('--total', type=float, default=float('inf'), help='total number of blocks if known (gives accurate progress stats)')
    parser.add_argument('--quiet', action='store_true', help='do not show progress bars')

    return parser.parse_args()


if __name__ == '__main__':
    parsed_args = parse_args(sys.argv)
    if parsed_args.quiet:
        tqdm = functools.partial(tqdm, disable=True)
    main(parsed_args)
