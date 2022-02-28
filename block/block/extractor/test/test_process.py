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


def test_decode_msgpack(fixture_parsed_footer,fixture_packed_footer):
    decoded = decode_msgpack(fixture_packed_footer)
    for key, value in decoded:
        # should recurse for transactions list?
        # if key == 'transactions':
        #     for txn, fix_txn in zip(value, fixture_parsed_footer[key]):
        #         pass
        assert fixture_parsed_footer[key] == value


# def test_main():
#     return False


# def test_parse_args():
#     return False
