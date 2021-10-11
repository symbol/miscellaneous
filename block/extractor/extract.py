#!/usr/bin/env python3
"""Symbol Block Extractor Script"""

import argparse
import functools
import glob
import os
import re
import struct
import sys
import pandas as pd
import msgpack
from tqdm import tqdm
from block.extractor.body import deserialize_header, deserialize_footer, get_block_stats
from block.extractor.format import HEADER_LEN, TX_HASH_LEN, TX_HASH_FORMAT, SUBCACHE_MERKLE_ROOT_FORMAT, DB_OFFSET_BYTES
from block.extractor.state import XYMStateMap
from block.extractor.statements import deserialize_statements, get_statement_paths
from block.extractor.util import fmt_unpack


def main(args):

    block_format_pattern = re.compile('[0-9]{5}'+args.block_extension)
    block_paths = glob.glob(os.path.join(args.input, '**', '*'+args.block_extension), recursive=True)
    block_paths = tqdm(sorted(list(filter(lambda x: block_format_pattern.match(os.path.basename(x)), block_paths))))

    blocks = []
    for path in block_paths:

        block_paths.set_description(f'processing block file: {path}')

        with open(path, mode='rb') as file:
            blk_data = file.read()

        i = args.db_offset_bytes

        while i < len(blk_data):

            # get fixed length data
            header = deserialize_header(blk_data[i:i+HEADER_LEN])
            footer = deserialize_footer(blk_data[i+HEADER_LEN:i+header['size']], header)
            i += header['size']
            block_hash, generation_hash = struct.unpack('<32s32s', blk_data[i:i+64])
            i += 64

            # get transaction hashes
            num_tx_hashes = struct.unpack('I', blk_data[i:i+4])[0]
            i += 4
            tx_hashes = None
            if args.save_tx_hashes:
                tx_hashes = []
                for _ in range(num_tx_hashes):
                    tx_hashes.append(fmt_unpack(blk_data[i:i+TX_HASH_LEN], TX_HASH_FORMAT))
                    i += TX_HASH_LEN
            else:
                i += num_tx_hashes * TX_HASH_LEN

            # get sub cache merkle roots
            root_hash_len = struct.unpack('I', blk_data[i:i+4])[0] * 32
            i += 4
            merkle_roots = None
            if args.save_subcache_merkle_roots:
                merkle_roots = fmt_unpack(blk_data[i:i+root_hash_len], SUBCACHE_MERKLE_ROOT_FORMAT)
            i += root_hash_len

            blocks.append({
                'header': header,
                'footer': footer,
                'block_hash': block_hash,
                'generation_hash': generation_hash,
                'tx_hashes': tx_hashes,
                'subcache_merkle_roots': merkle_roots
            })

    print('block data extraction complete!\n')

    with open(os.path.join(args.output, args.block_save_path), 'wb') as file:
        file.write(msgpack.packb(blocks))

    print(f'block data written to {os.path.join(args.output,args.block_save_path)}')

    statements_ = deserialize_statements(get_statement_paths(block_dir=args.input, statement_extension=args.statement_extension))
    blocks = sorted(blocks, key=lambda b: b['header']['height'])
    s_height, stmts, _ = next(statements_)

    state_map = XYMStateMap()

    with open(os.path.join(args.output, args.statement_save_path), 'wb') as file:
        for block in blocks:
            height = block['header']['height']
            state_map.insert_block(block)

            if s_height > height:
                continue

            while s_height < height:
                s_height, stmts, _ = next(statements_)

            for stmt in stmts['transaction_statements']:
                for rcpt in stmt['receipts']:
                    state_map.insert_rcpt(rcpt, height)

            file.write(msgpack.packb((s_height, stmts,)))

    assert len([*statements_]) == 0

    print('statement data extraction complete!\n')
    print(f'statement data written to {os.path.join(args.output,args.statement_save_path)}')

    # TODO: convert all fields to efficient string representations so header df can be stored as csv instead of pickle
    header_df = pd.DataFrame.from_records([get_block_stats(x) for x in blocks])
    header_df['dateTime'] = pd.to_datetime(header_df['timestamp'], origin=pd.to_datetime('2021-03-16 00:06:25'), unit='ms')
    header_df = header_df.set_index('dateTime').sort_index(axis=0)
    header_df.to_pickle(os.path.join(args.output, args.header_save_path))

    print(f'header data written to {os.path.join(args.output,args.header_save_path)}')

    state_map.to_msgpack(os.path.join(args.output, args.state_save_path))

    print(f'state data written to {os.path.join(args.output,args.state_save_path)}')

    print('exiting . . .')


def parse_args(argv):
    parser = argparse.ArgumentParser(argv)
    parser.add_argument('--input', type=str, default='data', help='Directory containing block store')
    parser.add_argument('--output', type=str, default='resources', help='directory to dump output')
    parser.add_argument('--block_save_path', type=str, default='block_data.msgpack', help='file to write the extracted block data to')
    parser.add_argument('--statement_save_path', type=str, default='stmt_data.msgpack', help='file to write extracted statement data to')
    parser.add_argument('--state_save_path', type=str, default='state_map.msgpack', help='file to write the extracted statement data to')
    parser.add_argument('--header_save_path', type=str, default='block_header_df.pkl', help='file to write the extracted data to')
    parser.add_argument('--block_extension', type=str, default='.dat', help='extension of block files; must be unique')
    parser.add_argument('--statement_extension', type=str, default='.stmt', help='extension of block files; must be unique')
    parser.add_argument('--db_offset_bytes', type=int, default=DB_OFFSET_BYTES, help='padding bytes at start of storage files')
    parser.add_argument('--save_tx_hashes', action='store_true', help='flag to keep full tx hashes')
    parser.add_argument('--save_subcache_merkle_roots', action='store_true', help='flag to keep subcache merkle roots')
    parser.add_argument('--quiet', action='store_true', help='do not show progress bars')

    args = parser.parse_args()

    return args


if __name__ == '__main__':
    args = parse_args(sys.argv)
    if args.quiet:
        tqdm = functools.partial(tqdm, disable=True)
    main(args)
