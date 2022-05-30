import glob
import os
import re
import struct

from tqdm import tqdm

from block.extractor.format import (ADDRESS_RESOLUTION_FORMAT, ADDRESS_RESOLUTION_LEN, DB_OFFSET_BYTES, MOSAIC_RESOLUTION_FORMAT,
                                    MOSAIC_RESOLUTION_LEN, RECEIPT_FORMAT, RECEIPT_LEN, RECEIPT_SOURCE_FORMAT, RECEIPT_SOURCE_LEN)
from block.extractor.util import encode_address, fmt_unpack


def deserialize_receipt_payload(receipt_data, receipt_type):
    # pylint: disable=too-many-statements, too-many-branches

    """Produce a nested python dict from a raw receipt payload

    Parameters
    ----------
    receipt_data : bytes
        Byte array containing serialized receipt payload
    receipt_type: bytes
        Byte array containing the hex representation of the type field from the receipt header

    Returns
    -------
    receipt: dict
        Dict containing receipt payload field keys and primitive or bytes values

    """

    # Reserved
    if receipt_type == 0x0000:  # reserved receipt
        payload = None

    # Balance Transfer
    elif receipt_type == 0x124D:  # mosaic rental fee receipt
        schema = {
            'mosaic_id': 'Q',
            'amount': 'Q',
            'sender_address': '24s',
            'recipient_address': '24s'
        }
        payload = fmt_unpack(receipt_data, schema)
        payload['sender_address'] = encode_address(payload['sender_address'])
        payload['recipient_address'] = encode_address(payload['recipient_address'])

    elif receipt_type == 0x134E:  # namespace rental fee receipt
        schema = {
            'mosaic_id': 'Q',
            'amount': 'Q',
            'sender_address': '24s',
            'recipient_address': '24s'
        }
        payload = fmt_unpack(receipt_data, schema)
        payload['sender_address'] = encode_address(payload['sender_address'])
        payload['recipient_address'] = encode_address(payload['recipient_address'])

    # Balance Change (Credit)
    elif receipt_type == 0x2143:  # harvest fee receipt
        schema = {
            'mosaic_id': 'Q',
            'amount': 'Q',
            'target_address': '24s',
        }
        payload = fmt_unpack(receipt_data, schema)
        payload['target_address'] = encode_address(payload['target_address'])

    elif receipt_type == 0x2248:  # lock hash completed receipt
        schema = {
            'mosaic_id': 'Q',
            'amount': 'Q',
            'target_address': '24s',
        }
        payload = fmt_unpack(receipt_data, schema)
        payload['target_address'] = encode_address(payload['target_address'])

    elif receipt_type == 0x2348:  # lock hash expired receipt
        schema = {
            'mosaic_id': 'Q',
            'amount': 'Q',
            'target_address': '24s',
        }
        payload = fmt_unpack(receipt_data, schema)
        payload['target_address'] = encode_address(payload['target_address'])

    elif receipt_type == 0x2252:  # lock secret completed receipt
        schema = {
            'mosaic_id': 'Q',
            'amount': 'Q',
            'target_address': '24s',
        }
        payload = fmt_unpack(receipt_data, schema)
        payload['target_address'] = encode_address(payload['target_address'])

    elif receipt_type == 0x2352:  # lock secret expired receipt
        schema = {
            'mosaic_id': 'Q',
            'amount': 'Q',
            'target_address': '24s',
        }
        payload = fmt_unpack(receipt_data, schema)
        payload['target_address'] = encode_address(payload['target_address'])

    # Balance Change (Debit)
    elif receipt_type == 0x3148:  # lock hash created receipt
        schema = {
            'mosaic_id': 'Q',
            'amount': 'Q',
            'target_address': '24s',
        }
        payload = fmt_unpack(receipt_data, schema)
        payload['target_address'] = encode_address(payload['target_address'])

    elif receipt_type == 0x3152:  # lock secret created receipt
        schema = {
            'mosaic_id': 'Q',
            'amount': 'Q',
            'target_address': '24s',
        }
        payload = fmt_unpack(receipt_data, schema)
        payload['target_address'] = encode_address(payload['target_address'])

    # Artifact Expiry
    elif receipt_type == 0x414D:  # mosaic expired receipt
        schema = {
            'mosaic_id': 'Q'
        }
        payload = fmt_unpack(receipt_data, schema)

    elif receipt_type == 0x414E:  # namespace expired receipt
        schema = {
            'mosaic_id': 'Q'
        }
        payload = fmt_unpack(receipt_data, schema)

    elif receipt_type == 0x424E:  # namespace deleted receipt
        schema = {
            'mosaic_id': 'Q'
        }
        payload = fmt_unpack(receipt_data, schema)

    # Inflation
    elif receipt_type == 0x5143:  # inflation receipt
        schema = {
            'mosaic_id': 'Q',
            'amount': 'Q',
        }
        payload = fmt_unpack(receipt_data, schema)

    # Transaction Statement
    elif receipt_type == 0xE143:  # transaction group receipt
        receipt_source = fmt_unpack(receipt_data[:RECEIPT_SOURCE_LEN], RECEIPT_SOURCE_FORMAT)
        i = RECEIPT_SOURCE_LEN

        receipt_count = struct.unpack('<I', receipt_data[i:i+4])[0]
        i += 4

        payload = {'receipt_source': receipt_source, 'receipts': []}
        for _ in range(receipt_count):
            receipt = fmt_unpack(receipt_data[i:i + RECEIPT_LEN], RECEIPT_FORMAT)
            receipt['payload'] = deserialize_receipt_payload(receipt_data[i + RECEIPT_LEN:i + receipt['size']], receipt['type'])
            i += receipt['size']

            payload['receipts'].append(receipt)

    else:
        raise ValueError(f'Unknown receipt payload type encountered: {hex(receipt_type)}')

    return payload


def deserialize_txn_statements(stmt_data, i):
    """Produce a list of statements from a buffer of transaction statement data

    Parameters
    ----------
    stmt_data : bytes
        Byte array containing serialized transaction statements
    i: int
        Starting index into byte array

    Returns
    -------
    i: int
        Final index value after deserializing transaction statements
    statements: list
        List of dicts containing deserialized transaction statements
    """

    count = struct.unpack('<I', stmt_data[i:i+4])
    i += 4

    statements = []
    for _ in range(count[0]):
        receipt_source = fmt_unpack(stmt_data[i:i + RECEIPT_SOURCE_LEN], RECEIPT_SOURCE_FORMAT)
        i += RECEIPT_SOURCE_LEN

        receipt_count = struct.unpack('<I', stmt_data[i:i+4])[0]
        i += 4

        statement = {'receipt_source': receipt_source, 'receipts': []}
        for _ in range(receipt_count):
            receipt = fmt_unpack(stmt_data[i:i + RECEIPT_LEN], RECEIPT_FORMAT)
            receipt['payload'] = deserialize_receipt_payload(stmt_data[i + RECEIPT_LEN:i + receipt['size']], receipt['type'])
            i += receipt['size']

            statement['receipts'].append(receipt)

        statements.append(statement)

    return i, statements


def deserialize_addr_statements(stmt_data, i):
    """Produce a list of statements from a buffer of address resolution data

    Parameters
    ----------
    stmt_data : bytes
        Byte array containing serialized address resolution statements
    i: int
        Starting index into byte array

    Returns
    -------
    i: int
        Final index value after deserializing address resolution statements
    statements: list
        List of dicts containing deserialized address resolution statements
    """

    count = struct.unpack('<I', stmt_data[i:i+4])
    i += 4

    statements = []
    for _ in range(count[0]):
        key = struct.unpack('24s', stmt_data[i:i+24])[0]
        i += 24

        resolution_count = struct.unpack('<I', stmt_data[i:i+4])[0]
        i += 4

        statement = {'key': key, 'resolutions': []}
        for _ in range(resolution_count):
            address_resolution = fmt_unpack(stmt_data[i:i + ADDRESS_RESOLUTION_LEN], ADDRESS_RESOLUTION_FORMAT)
            i += ADDRESS_RESOLUTION_LEN
            statement['resolutions'].append(address_resolution)

        statements.append(statement)

    return i, statements


def deserialize_mosaic_statements(stmt_data, i):
    """Produce a list of statements from a buffer of mosaic resolution data

    Parameters
    ----------
    stmt_data : bytes
        Byte array containing serialized mosaic resolution statements
    i: int
        Starting index into byte array

    Returns
    -------
    i: int
        Final index value after deserializing mosaic resolution statements
    statements: list
        List of dicts containing deserialized mosaic resolution statements
    """

    count = struct.unpack('<I', stmt_data[i:i+4])
    i += 4

    statements = []
    for _ in range(count[0]):
        key = struct.unpack('<Q', stmt_data[i:i+8])[0]
        i += 8

        resolution_count = struct.unpack('<I', stmt_data[i:i+4])[0]
        i += 4

        statement = {'key': key, 'resolutions': []}
        for _ in range(resolution_count):
            mosaic_resolution = fmt_unpack(stmt_data[i:i + MOSAIC_RESOLUTION_LEN], MOSAIC_RESOLUTION_FORMAT)
            i += MOSAIC_RESOLUTION_LEN
            statement['resolutions'].append(mosaic_resolution)

        statements.append(statement)

    return i, statements


def get_statement_paths(statement_extension='.stmt', block_dir='./data'):
    """Collect a list of valid statement paths for analysis"""
    statement_paths = glob.glob(os.path.join(block_dir, '**', '*'+statement_extension), recursive=True)
    statement_format_pattern = re.compile('[0-9]{5}'+statement_extension)
    statement_paths = sorted(list(filter(lambda x: statement_format_pattern.match(os.path.basename(x)), statement_paths)))
    return statement_paths


def deserialize_statements(statement_paths, db_offset_bytes=DB_OFFSET_BYTES):
    """Generator accepting statement paths and yielding deserialization results

    Parameters
    ----------
    statement_paths: list[str]
        List of files containing statements to be deserialized
    db_offset_bytes: int, optional
        Number of pad bytes to be ignored at the head of each serialized statement file

    Yields
    ------
    stmt_height: int
        Block height of yielded statements
    statements: dict
        Data for transaction, address resolution, and mosaic resolution statements
    path: str
        File from which statements were deserialized

    """
    stmt_height = 0
    statement_paths_ = tqdm(statement_paths)
    for path in statement_paths_:
        statements = {
            'transaction_statements': {},
            'address_resolution_statements': {},
            'mosaic_resolution_statements': {}
            }

        statement_paths_.set_description(f'processing statement file: {path}')

        with open(path, mode='rb') as file:
            stmt_data = file.read()

        i = db_offset_bytes

        while i < len(stmt_data):
            # statement deserialization can probably be inlined efficiently or at least aggregated into one function
            i, transaction_statements = deserialize_txn_statements(stmt_data, i)
            i, address_resolution_statements = deserialize_addr_statements(stmt_data, i)
            i, mosaic_resolution_statements = deserialize_mosaic_statements(stmt_data, i)

            stmt_height += 1
            statements['transaction_statements'] = transaction_statements
            statements['address_resolution_statements'] = address_resolution_statements
            statements['mosaic_resolution_statements'] = mosaic_resolution_statements
            yield stmt_height, statements, path
