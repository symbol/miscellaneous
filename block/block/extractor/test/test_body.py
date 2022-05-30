from block.extractor.body import deserialize_footer, deserialize_header, deserialize_tx_payload


def test_deserialize_header(fixture_raw_header, fixture_parsed_header):
    header = deserialize_header(fixture_raw_header)
    for key, value in header:
        assert fixture_parsed_header[key] == value


def test_deserialize_footer(fixture_raw_footer, fixture_parsed_header, fixture_parsed_footer):
    footer = deserialize_footer(fixture_raw_footer, fixture_parsed_header)
    for key, value in footer:
        if key == 'transactions':
            for txn, fix_txn in zip(value, fixture_parsed_footer[key]):
                for txn_value, fix_txn_value in zip(txn.values(), fix_txn.values()):
                    assert txn_value == fix_txn_value
        else:
            assert fixture_parsed_footer[key] == value


def test_deserialize_tx_payload(fixture_parsed_payload):
    payload_data = b'h\x1d7w\xa2X\xc3hr\x86\xe7\xe2\xb1\x15\x93P\xf2z_K1sT\xfc\x00\x00\x01\x00\x00\x00\x00\x00\xf8#\x02' + \
        b'\xa2?\x91\xedk\xa0\x85\xf2\x05\x00\x00\x00\x00'
    payload = deserialize_tx_payload(payload_data, b'4154')
    for key, value in payload:
        assert fixture_parsed_payload[key] == value
