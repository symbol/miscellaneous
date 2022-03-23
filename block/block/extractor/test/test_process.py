import os
import pandas as pd
from block.extractor.process import decode_msgpack, get_block_stats, get_tx_stats, main, parse_args


def test_get_block_stats(fixture_block, fixture_block_stats):
    block_stats = get_block_stats(fixture_block)
    for key, value in block_stats:
        assert fixture_block_stats[key] == value


def test_get_tx_stats(fixture_block, fixture_tx_stats):
    tx_stats = get_tx_stats(fixture_block)
    for txn, fix_txn in zip(tx_stats, fixture_tx_stats):
        for key, value in txn:
            assert fix_txn[key] == value


def test_decode_msgpack(fixture_parsed_footer, fixture_packed_footer):
    decoded = decode_msgpack(fixture_packed_footer)
    for key, value in decoded:
        # should recurse for transactions list?
        # if key == 'transactions':
        #     for txn, fix_txn in zip(value, fixture_parsed_footer[key]):
        #         pass
        assert fixture_parsed_footer[key] == value


def test_main(fixture_process_args):
    main(fixture_process_args)

    header_data = pd.read_csv(os.path.join(fixture_process_args.output, fixture_process_args.header_save_path))
    fixture_header_data = open('./fixture_data/block_headers.csv', 'rb').read()
    assert header_data.equals(fixture_header_data)

    tx_data = pd.read_csv(os.path.join(fixture_process_args.output, fixture_process_args.tx_save_path))
    fixture_tx_data = open('./fixture_data/transactions.csv', 'rb').read()
    assert tx_data.equals(fixture_tx_data)


def test_parse_args(fixture_process_args):
    test_args = vars(fixture_process_args)
    args = parse_args(' '.join([f'--{k}' if isinstance(v, bool) and v else f'--{k} {v}' for k, v in test_args.items()]))
    for key, value in test_args.items():
        assert getattr(args, key) == value
