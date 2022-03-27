# pylint: disable=redefined-outer-name
import argparse
import pytest
import msgpack

from block.extractor.format import DB_OFFSET_BYTES


@pytest.fixture
def fixture_raw_header():
    with open('./fixture_data/raw_header.dat', 'rb') as data:
        buffer = data.read()
    return buffer


@pytest.fixture
def fixture_parsed_header():
    return {
        'size': 4730848,
        'reserved_1': 0,
        'signature': b'2910a9efbf5b984481c736b9ab242cef6905248384fe59eca2e1542e3c417fefd5268c5c5636fb4a9f814ab6dc5a272' +
        b'48672f4ae92ff3d439716f9429402a006',
        'signer_public_key': b'be0b4cf546b7b4f4bbfcff9f574fda527c07a53d3fc76f8bb7db746f8e8e0a9f',
        'reserved_2': 0,
        'version': 1,
        'network': 104,
        'type': b'8043',
        'height': 1,
        'timestamp': 0,
        'difficulty': 100000000000000,
        'generation_hash_proof': b'f25bfd1f6f853b373a22153703d2a7698be31c6e6e411b35daf6d5711ca780a0e63cd2722f39b82344c' +
        b'997e3397ccfcb22b20e09ed94057e74fc3e33091cfc3070b38f924c7edf36053c7ad920018d03',
        'previous_block_hash': b'0000000000000000000000000000000000000000000000000000000000000000',
        'transactions_hash': b'2c81b8deabdb61ab8d0ccab985c6d4739b332e26b663d19227b3b9502a5c881f',
        'receipts_hash': b'b882f8a9141da5804a55b756c83ebd804ac394fb1049369d228f30c02468d7e4',
        'state_hash': b'205cae53a6f7117053add6482b91f2fa8a66fa22c24edd4d55ff83a75525e2ec',
        'beneficiary_address': 'NASYMBOLLK6FSL7GSEMQEAWN7VW55ZSZU25TBOA',
        'fee_multiplier': 0,
        'harvester': 'NASYMBOLLK6FSL7GSEMQEAWN7VW55ZSZU25TBOA'}


@pytest.fixture
def fixture_raw_footer():
    with open('./fixture_data/raw_footer.dat', 'rb') as data:
        buffer = data.read()
    return buffer


@pytest.fixture
def fixture_packed_footer():
    return msgpack.unpack(open('./fixture_data/footer.msgpack', 'rb'), raw=True)


@pytest.fixture
def fixture_parsed_footer():
    return {
        'reserved': 0,
        'total_fee': 17600,
        'statement_count': 1,
        'tx_count': 1,
        'transactions': [{
            'size': 176,
            'reserved_1': 0,
            'signature': b'c0974ffc2ac8826b61cff43d11745d70f7964bad5b790d0026c86af155c87f128c862843ebaba38932f0ea44acb4' +
            b'b6ec0e2853240e0ffc81317e91167725b600',
            'signer_public_key': b'2880a86a59630954d664a180038983fdbdf66e3937633439880624ed99a050a5',
            'reserved_2': 0,
            'version': 1,
            'network': 104,
            'type': b'4154',
            'max_fee': 17600,
            'deadline': 98014886,
            'id': 1,
            'payload': {
                'recipient_address': 'NAOTO55CLDBWQ4UG47RLCFMTKDZHUX2LGFZVJ7A',
                'message_size': 0,
                'mosaics_count': 1,
                'transfer_transaction_body_reserved_1': 0,
                'transfer_transaction_body_reserved_2': 0,
                'mosaics': [{
                    'mosaic_id': 7777031834025731064,
                    'amount': 99780000}],
                'message': b'h\x1d7w\xa2X\xc3hr\x86\xe7\xe2\xb1\x15\x93P\xf2z_K1sT\xfc\x00\x00\x01\x00\x00\x00\x00\x00' +
                b'\xf8#\x02\xa2?\x91\xedk\xa0\x85\xf2\x05\x00\x00\x00\x00'
                }
            }]
        }


@pytest.fixture
def fixture_parsed_payload(fixture_parsed_footer):
    return fixture_parsed_footer['transactions'][0]['payload']


@pytest.fixture
def fixture_block(fixture_parsed_header, fixture_parsed_footer):
    return {
        'header': fixture_parsed_header,
        'footer': fixture_parsed_footer
    }


@pytest.fixture
def fixture_block_stats():
    return {
        'size': 4730848,
        'reserved_1': 0,
        'signature': '2910a9efbf5b984481c736b9ab242cef6905248384fe59eca2e1542e3c417fefd5268c5c5636fb4a9f814ab6dc5a27248' +
        '672f4ae92ff3d439716f9429402a006',
        'signer_public_key': 'be0b4cf546b7b4f4bbfcff9f574fda527c07a53d3fc76f8bb7db746f8e8e0a9f',
        'reserved_2': 0,
        'version': 1,
        'network': 104,
        'type': '8043',
        'height': 1,
        'timestamp': 0,
        'difficulty': 100000000000000,
        'generation_hash_proof': 'f25bfd1f6f853b373a22153703d2a7698be31c6e6e411b35daf6d5711ca780a0e63cd2722f39b82344c99' +
        '7e3397ccfcb22b20e09ed94057e74fc3e33091cfc3070b38f924c7edf36053c7ad920018d03',
        'previous_block_hash': '0000000000000000000000000000000000000000000000000000000000000000',
        'transactions_hash': '2c81b8deabdb61ab8d0ccab985c6d4739b332e26b663d19227b3b9502a5c881f',
        'receipts_hash': 'b882f8a9141da5804a55b756c83ebd804ac394fb1049369d228f30c02468d7e4',
        'state_hash': '205cae53a6f7117053add6482b91f2fa8a66fa22c24edd4d55ff83a75525e2ec',
        'beneficiary_address': 'NASYMBOLLK6FSL7GSEMQEAWN7VW55ZSZU25TBOA',
        'fee_multiplier': 0,
        'harvester': 'NASYMBOLLK6FSL7GSEMQEAWN7VW55ZSZU25TBOA',
        'statement_count': 1,
        'tx_count': 1,
        'total_fee': 17600
    }


@pytest.fixture
def fixture_tx_stats():
    return [
        {
            'size': 176,
            'signature': 'c0974ffc2ac8826b61cff43d11745d70f7964bad5b790d0026c86af155c87f128c862843ebaba38932f0ea44acb4b' +
            '6ec0e2853240e0ffc81317e91167725b600',
            'signer_public_key': '2880a86a59630954d664a180038983fdbdf66e3937633439880624ed99a050a5',
            'type': '4154',
            'max_fee': 17600,
            'deadline': 98014886,
            'id': 1,
            'height': 1,
            'timestamp': 0,
            'recipient_address': 'NAOTO55CLDBWQ4UG47RLCFMTKDZHUX2LGFZVJ7A',
            'message_size': 0,
            'mosaics': '[{"mosaic_id": 7777031834025731064, "amount": 99780000}]',
            'message': '681d3777a258c3687286e7e2b1159350f27a5f4b317354fc0000010000000000f82302a23f91ed6ba085f20500000000'
        }
    ]


@pytest.fixture
def fixture_extract_args():
    args = argparse.Namespace()
    args.input = './fixture_data'
    args.output = './fixture_data/test_output'
    args.block_save_path = 'block_data.msgpack'
    args.statement_save_path = 'stmt_data.msgpack'
    args.state_save_path = 'state_map.msgpack'
    args.block_extension = '.dat'
    args.statement_extension = '.stmt'
    args.db_offset_bytes = DB_OFFSET_BYTES
    args.save_tx_hashes = True
    args.save_subcache_merkle_roots = True
    args.quiet = False
    args.stream = False
    return args


@pytest.fixture
def fixture_process_args():
    args = argparse.Namespace()
    args.input = './fixture_data/block_data.msgpack'
    args.output = './fixture_data/test_output'
    args.header_save_path = 'block_headers.csv'
    args.tx_save_path = 'transactions.csv'
    args.total = 100.0
    args.append = False
    args.quiet = False
    return args
