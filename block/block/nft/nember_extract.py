import argparse
import json
import pickle
from binascii import unhexlify

import msgpack
from tqdm import tqdm

from block.extractor import public_key_to_address


def extract_nft_transfer(transaction, height, nft_transaction_map):
    for mosaic in transaction[b'payload'][b'mosaics']:
        if mosaic[b'mosaic_id'] in nft_transaction_map and mosaic[b'amount'] == 1:
            nft_transaction_map[mosaic[b'mosaic_id']].append((height, transaction[b'payload'][b'recipient_address']))


def main(args):
    # pylint: disable=too-many-nested-blocks, too-many-branches

    with open(args.input, 'rb') as file:
        blocks = msgpack.unpack(file, unicode_errors=None, raw=True)

    nft_mosaics = []
    platform_transactions = []
    for block in tqdm(blocks):
        for transaction in block[b'footer'][b'transactions']:
            if transaction[b'type'] == b'4241' and transaction[b'payload'][b'embedded_tx_count'] == 4:
                flag = False
                for sub_transaction in transaction[b'payload'][b'embedded_transactions']:
                    if sub_transaction[b'type'] == b'4154':
                        if b'NEMBER.ART' in sub_transaction[b'payload'][b'message']:
                            flag = True
                if flag:
                    gen_transaction = [x for x in transaction[b'payload'][b'embedded_transactions'] if x[b'type'] == b'414d']
                    meta_transaction = [x for x in transaction[b'payload'][b'embedded_transactions'] if x[b'type'] == b'4244']
                    supply_transaction = [x for x in transaction[b'payload'][b'embedded_transactions'] if x[b'type'] == b'424d']
                    if any(len(x) != 1 for x in [gen_transaction, meta_transaction, supply_transaction]):
                        platform_transactions.append(transaction)
                        continue

                    try:
                        metadata = json.loads(meta_transaction[0][b'payload'][b'value'].decode('utf-8'))
                        name = metadata['data']['meta']['name']
                    except json.JSONDecodeError:  # some metadata is double-encoded
                        metadata = json.loads(unhexlify(meta_transaction[0][b'payload'][b'value'].decode('UTF-8')).decode('UTF-8'))
                        name = metadata['data']['meta']['name']

                    nft_mosaics.append({
                        'name': name,
                        'id': gen_transaction[0][b'payload'][b'id'],
                        'supply': supply_transaction[0][b'payload'][b'delta'],
                        'height': block[b'header'][b'height'],
                        'mint_address': public_key_to_address(unhexlify(gen_transaction[0][b'signer_public_key'])),
                        'metadata_key': meta_transaction[0][b'payload'][b'scoped_metadata_key'],
                        'metadata': metadata
                    })

    with open(args.info_save_path, 'wb') as file:
        pickle.dump(nft_mosaics, file)

    print(f'NFTs identified: {len(nft_mosaics)}')
    print(f'nember platform TX identified: {len(platform_transactions)}')

    nft_transaction_map = {nft['id']: [(nft['height'], nft['mint_address'])] for nft in nft_mosaics}
    for block in tqdm(blocks):
        for transaction in block[b'footer'][b'transactions']:
            if transaction[b'type'] in [b'4141', b'4241']:
                for sub_transaction in transaction[b'payload'][b'embedded_transactions']:
                    if sub_transaction[b'type'] == b'4154':
                        extract_nft_transfer(sub_transaction, block[b'header'][b'height'], nft_transaction_map)
            elif transaction[b'type'] == b'4154':
                extract_nft_transfer(transaction, block[b'header'][b'height'], nft_transaction_map)

    with open(args.tx_save_path, 'wb') as file:
        pickle.dump(nft_transaction_map, file)


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=str, default='resources/block_data.msgpack', help='location of parsed block data msgpack')
    parser.add_argument('--output', type=str, default='nft/output', help='directory to dump output')
    parser.add_argument('--info_save_path', type=str, default='nember_mosaic_data.pkl', help='file to write the nft information to')
    parser.add_argument('--tx_save_path', type=str, default='nember_tx_data.pkl', help='file to write nft transaction log to')

    parsed_args = parser.parse_args()

    main(parsed_args)
