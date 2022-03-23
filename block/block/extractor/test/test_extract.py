import os
from block.extractor.extract import main, main_stream, parse_args


def test_main(fixture_extract_args):
    main(fixture_extract_args)

    block_data = open(os.path.join(fixture_extract_args.output, fixture_extract_args.block_save_path), 'rb').read()
    fixture_block_data = open('./fixture_data/block_data.msgpack', 'rb').read()
    assert block_data == fixture_block_data

    stmt_data = open(os.path.join(fixture_extract_args.output, fixture_extract_args.statement_save_path), 'rb').read()
    fixture_stmt_data = open('./fixture_data/stmt_data.msgpack', 'rb').read()
    assert stmt_data == fixture_stmt_data


def test_main_stream(fixture_extract_args):
    fixture_extract_args.stream = True
    main_stream(fixture_extract_args)

    block_data = open(os.path.join(fixture_extract_args.output, fixture_extract_args.block_save_path), 'rb').read()
    fixture_block_data = open('./fixture_data/block_data.msgpack', 'rb').read()
    assert block_data == fixture_block_data

    stmt_data = open(os.path.join(fixture_extract_args.output, fixture_extract_args.statement_save_path), 'rb').read()
    fixture_stmt_data = open('./fixture_data/stmt_data.msgpack', 'rb').read()
    assert stmt_data == fixture_stmt_data


def test_parse_args(fixture_extract_args):
    test_args = vars(fixture_extract_args)
    args = parse_args(' '.join([f'--{k}' if isinstance(v, bool) and v else f'--{k} {v}' for k, v in test_args.items()]))
    for key, value in test_args.items():
        assert getattr(args, key) == value
