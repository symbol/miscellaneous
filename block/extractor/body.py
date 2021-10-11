import struct
from binascii import hexlify, unhexlify
from block.extractor.format import (
    HEADER_FORMAT,
    FOOTER_LEN,
    FOOTER_FORMAT,
    IMPORTANCE_FOOTER_LEN,
    IMPORTANCE_FOOTER_FORMAT,
    TX_H_LEN,
    TX_H_FORMAT,
    EMBED_TX_H_LEN,
    EMBED_TX_H_FORMAT)
from block.extractor.util import fmt_unpack, encode_address, public_key_to_address


def deserialize_header(header_data):
    """Produce a python dict from a raw xym header blob

    Parameters
    ----------
    header_data: bytes
        Byte array containing serialized header

    Returns
    -------
    header: dict
        Dict containing block header field keys and primitive or bytes values

    """

    header = fmt_unpack(header_data, HEADER_FORMAT)
    for key, val in HEADER_FORMAT.items():
        if key == 'type':
            header[key] = hexlify(header[key][::-1])
        elif key == 'beneficiary_address':
            header[key] = encode_address(header[key])
        elif val[-1] == 's':
            header[key] = hexlify(header[key])
    header['harvester'] = public_key_to_address(unhexlify(header['signer_public_key']))
    return header


def deserialize_footer(footer_data, header):
    """Produce a nested python dict from a raw xym footer blob

    Parameters
    ----------
    footer_data: bytes
        Byte array containing serialized footer
    header: dict
        Deserialized header dict as produced by:func:`deserialize_header`

    Returns
    -------
    footer: dict
        Dict containing block footer field keys and primitive or bytes values
        as well as a list of deserialized transaction dicts

    """

    # parse static footer fields
    if header['type'] == b'8043':  # nemesis
        footer = fmt_unpack(footer_data[:IMPORTANCE_FOOTER_LEN], IMPORTANCE_FOOTER_FORMAT)
        i = IMPORTANCE_FOOTER_LEN
    elif header['type'] == b'8143':  # normal
        footer = fmt_unpack(footer_data[:FOOTER_LEN], FOOTER_FORMAT)
        i = FOOTER_LEN
    elif header['type'] == b'8243':  # importance
        footer = fmt_unpack(footer_data[:IMPORTANCE_FOOTER_LEN], IMPORTANCE_FOOTER_FORMAT)
        i = IMPORTANCE_FOOTER_LEN
    else:
        raise ValueError(f'Unknown Block Type Encountered: {header["type"]}')

    # parse transactions
    tx_data = []
    tx_count = 0
    statement_count = 0
    total_fee = 0
    while i < len(footer_data):
        tx_header = fmt_unpack(footer_data[i:i+TX_H_LEN], TX_H_FORMAT)
        tx_header['id'] = statement_count + 1  # tx ids are 1-based
        tx_header['signature'] = hexlify(tx_header['signature'])
        tx_header['signer_public_key'] = hexlify(tx_header['signer_public_key'])
        tx_header['type'] = hexlify(tx_header['type'][::-1])
        tx_header['payload'] = deserialize_tx_payload(footer_data[i+TX_H_LEN:i+tx_header['size']], tx_header['type'])
        tx_data.append(tx_header)

        total_fee += min(tx_header['max_fee'], tx_header['size'] * header['fee_multiplier'])
        tx_count += (1+tx_header['payload']['embedded_tx_count']) if 'embedded_tx_count' in tx_header['payload'] else 1
        statement_count += 1
        i += tx_header['size'] + (8 - tx_header['size']) % 8

    footer['total_fee'] = total_fee
    footer['statement_count'] = statement_count
    footer['tx_count'] = tx_count
    footer['transactions'] = tx_data

    return footer


def deserialize_tx_payload(payload_data, payload_type):
    """Produce a nested python dict from a raw xym statemet payload

    Parameters
    ----------
    payload_data: bytes
        Byte array containing serialized tx payload
    payload_type: bytes
        Byte array containing the hex representation of the type field from
        the transaction header associated with payload

    Returns
    -------
    payload: dict
        Dict containing tx payload field keys and primitive or bytes values. In
        the case of aggregate transactions, will include a list containing dict
        representations of deserialized embedded transactions.

    """

    # Account Link
    if payload_type == b'414c':  # AccountKeyLinkTransaction
        schema = {
            'linked_public_key': '32s',
            'link_action': 'B'
        }
        payload = fmt_unpack(payload_data, schema)

    elif payload_type == b'424c':  # NodeKeyLinkTransaction
        schema = {
            'linked_public_key': '32s',
            'link_action': 'B'
        }
        payload = fmt_unpack(payload_data, schema)

    # Aggregate
    elif payload_type == b'4141':  # AggregateCompleteTransaction
        schema = {
            'transactions_hash': '32s',
            'payload_size': 'I',
            'aggregate_complete_transaction_reserved_1': 'I'
        }
        i = 40
        payload = fmt_unpack(payload_data[:i], schema)
        e_tx_count = 0
        e_tx_data = []
        while i < 8 + payload['payload_size']:
            e_tx_header = fmt_unpack(payload_data[i:i+EMBED_TX_H_LEN], EMBED_TX_H_FORMAT)
            e_tx_header['id'] = e_tx_count + 1  # tx ids are 1-based
            e_tx_header['signer_public_key'] = hexlify(e_tx_header['signer_public_key'])
            e_tx_header['type'] = hexlify(e_tx_header['type'][::-1])
            e_tx_header['payload'] = deserialize_tx_payload(payload_data[i+EMBED_TX_H_LEN:i+e_tx_header['size']], e_tx_header['type'])
            e_tx_data.append(e_tx_header)
            e_tx_count += 1
            i += e_tx_header['size'] + (8 - e_tx_header['size']) % 8

        payload['embedded_tx_count'] = e_tx_count
        payload['embedded_transactions'] = e_tx_data
        payload['cosignatures'] = payload_data[i:]

    elif payload_type == b'4241':  # AggregateBondedTransaction
        schema = {
            'transactions_hash': '32s',
            'payload_size': 'I',
            'aggregate_complete_transaction_reserved_1': 'I'
        }
        i = 40
        payload = fmt_unpack(payload_data[:i], schema)
        e_tx_count = 0
        e_tx_data = []
        while i < 8 + payload['payload_size']:
            e_tx_header = fmt_unpack(payload_data[i:i+EMBED_TX_H_LEN], EMBED_TX_H_FORMAT)
            e_tx_header['id'] = e_tx_count + 1  # tx ids are 1-based
            e_tx_header['signer_public_key'] = hexlify(e_tx_header['signer_public_key'])
            e_tx_header['type'] = hexlify(e_tx_header['type'][::-1])
            e_tx_header['payload'] = deserialize_tx_payload(payload_data[i+EMBED_TX_H_LEN:i+e_tx_header['size']], e_tx_header['type'])
            e_tx_data.append(e_tx_header)
            e_tx_count += 1
            i += e_tx_header['size'] + (8 - e_tx_header['size']) % 8

        payload['embedded_tx_count'] = e_tx_count
        payload['embedded_transactions'] = e_tx_data
        payload['cosignatures'] = payload_data[i:]

    # Core
    elif payload_type == b'4143':  # VotingKeyLinkTransaction
        schema = {
            'linked_public_key': '32s',
            'start_point': 'I',
            'end_point': 'I',
            'link_action': 'B'
        }
        payload = fmt_unpack(payload_data, schema)

    elif payload_type == b'4243':  # VrfKeyLinkTransaction
        schema = {
            'linked_public_key': '32s',
            'link_action': 'B'
        }
        payload = fmt_unpack(payload_data, schema)

    # Mosaic
    elif payload_type == b'414d':  # MosaicDefinitionTransaction
        schema = {
            'id': 'Q',
            'duration': 'Q',
            'nonce': 'I',
            'flags': 'B',
            'divisibility': 'B'
        }
        payload = fmt_unpack(payload_data, schema)

    elif payload_type == b'424d':  # MosaicSupplyChangeTransaction
        schema = {
            'mosaic_id': 'Q',
            'delta': 'Q',
            'action': 'B',
        }
        payload = fmt_unpack(payload_data, schema)

    # Namespace
    elif payload_type == b'414e':  # NamespaceRegistrationTransaction
        schema = {
            'identifier': 'Q',
            'id': 'Q',
            'registration_type': 'B',
            'name_size': 'B',
        }
        payload = fmt_unpack(payload_data[:18], schema)
        payload['name'] = payload_data[18:]
        if payload['registration_type'] == 0:
            payload['duration'] = payload['identifier']
        elif payload['registration_type'] == 1:
            payload['parent_id'] = payload['identifier']
        else:
            raise ValueError(f'Unknown registration type for Namespace RegistrationTransaction: {payload["registration_type"]}')
        del payload['identifier']

    elif payload_type == b'424e':  # AddressAliasTransaction
        schema = {
            'namespace_id': 'Q',
            'address': '24s',
            'alias_action': 'B'
        }
        payload = fmt_unpack(payload_data, schema)

    elif payload_type == b'434e':  # MosaicAliasTransaction
        schema = {
            'namespace_id': 'Q',
            'mosaid_id': 'Q',
            'alias_action': 'B'
        }
        payload = fmt_unpack(payload_data, schema)

    # Metadata
    elif payload_type == b'4144':  # AccountMetadataTransaction
        schema = {
            'target_address': '24s',
            'scoped_metadata_key': 'Q',
            'value_size_delta': 'H',
            'value_size': 'H',
        }
        payload = fmt_unpack(payload_data[:36], schema)
        payload['target_address'] = encode_address(payload['target_address'])
        payload['value'] = payload_data[36:]

    elif payload_type == b'4244':  # MosaicMetadataTransaction
        schema = {
            'target_address': '24s',
            'scoped_metadata_key': 'Q',
            'target_mosaic_id': 'Q',
            'value_size_delta': 'H',
            'value_size': 'H',
        }
        payload = fmt_unpack(payload_data[:44], schema)
        payload['target_address'] = encode_address(payload['target_address'])
        payload['value'] = payload_data[44:]

    elif payload_type == b'4344':  # NamespaceMetadataTransaction
        schema = {
            'target_address': '24s',
            'scoped_metadata_key': 'Q',
            'target_namespace_id': 'Q',
            'value_size_delta': 'H',
            'value_size': 'H',
        }
        payload = fmt_unpack(payload_data[:44], schema)
        payload['target_address'] = encode_address(payload['target_address'])
        payload['value'] = payload_data[44:]

    # Multisignature
    elif payload_type == b'4155':  # MultisigAccountModificationTransaction
        schema = {
            'min_removal_delta': 'B',
            'min_approval_delta': 'b',
            'address_additions_count': 'B',
            'address_deletions_count': 'B',
            'multisig_account_modificaion_transacion_body_reserved_1': 'I'
        }
        payload = fmt_unpack(payload_data[:8], schema)
        i = 8
        if payload['address_additions_count'] > 0:
            payload['address_additions'] = struct.unpack(
                '<' + '24s'*payload['address_additions_count'], payload_data[i:i+payload['address_additions_count']*24])
            i += payload['address_additions_count']*24
        else:
            payload['address_additions'] = []

        if payload['address_deletions_count'] > 0:
            payload['address_deletions'] = struct.unpack(
                '<' + '24s'*payload['address_deletions_count'], payload_data[i:i+payload['address_deletions_count']*24])
        else:
            payload['address_deletions'] = []

    # Hash Lock
    elif payload_type == b'4148':  # HashLockTransaction
        schema = {
            'reserved_1': '8s',  # NOT in the schema but shows up in the data ?!?
            'mosaic': 'Q',
            'duration': 'Q',
            'hash': '32s'
        }
        payload = fmt_unpack(payload_data, schema)

    # Secret Lock
    elif payload_type == b'4152':  # SecretLockTransaction
        schema = {
            'recipient_address': '24s',
            'secret': '32s',
            'mosaic_id': 'Q',
            'amount': 'Q',
            'duration': 'Q',
            'hash_algorithm': 'B'
        }
        payload = fmt_unpack(payload_data, schema)
        payload['recipient_address'] = encode_address(payload['recipient_address'])

    elif payload_type == b'4252':  # SecretProofTransaction
        schema = {
            'recipient_address': '24s',
            'secret': '32s',
            'proof_size': 'H',
            'hash_algorithm': 'B',
        }
        payload = fmt_unpack(payload_data[:59], schema)
        payload['recipient_address'] = encode_address(payload['recipient_address'])
        payload['proof'] = payload_data[59:]

    # Account restriction
    elif payload_type == b'4150':  # AccountAddressRestrictionTransaction
        schema = {
            'restriction_type': 'H',
            'restriction_additions_count': 'B',
            'restriction_deletions_count': 'B',
            'account_restriction_transaction_body_reserved_1': 'I',
        }
        payload = fmt_unpack(payload_data[:8], schema)
        i = 8
        if payload['restriction_additions_count'] > 0:
            payload['restriction_additions'] = struct.unpack(
                '<' + '24s'*payload['restriction_additions_count'], payload_data[i:i+payload['restriction_additions_count']*24])
            i += payload['restriction_additions_count']*24
        else:
            payload['restriction_additions'] = []

        if payload['restriction_deletions_count'] > 0:
            payload['restriction_deletions'] = struct.unpack(
                '<' + '24s'*payload['restriction_deletions_count'], payload_data[i:i+payload['restriction_deletions_count']*24])
        else:
            payload['restriction_deletions'] = []

    elif payload_type == b'4250':  # AccountMosaicRestrictionTransaction
        schema = {
            'restriction_type': 'H',
            'restriction_additions_count': 'B',
            'restriction_deletions_count': 'B',
            'account_restriction_transaction_body_reserved_1': 'I',
        }
        payload = fmt_unpack(payload_data[:8], schema)
        i = 8
        if payload['restriction_additions_count'] > 0:
            payload['restriction_additions'] = struct.unpack(
                '<' + 'Q'*payload['restriction_additions_count'], payload_data[i:i+payload['restriction_additions_count']*8])
            i += payload['restriction_additions_count']*8
        else:
            payload['restriction_additions'] = []

        if payload['restriction_deletions_count'] > 0:
            payload['restriction_deletions'] = struct.unpack(
                '<' + 'Q'*payload['restriction_deletions_count'], payload_data[i:i+payload['restriction_deletions_count']*8])
        else:
            payload['restriction_deletions'] = []

    elif payload_type == b'4350':  # AccountOperationRestrictionTransaction
        schema = {
            'restriction_type': 'H',
            'restriction_additions_count': 'B',
            'restriction_deletions_count': 'B',
            'account_restriction_transaction_body_reserved_1': 'I',
        }
        payload = fmt_unpack(payload_data[:8], schema)
        i = 8
        if payload['restriction_additions_count'] > 0:
            payload['restriction_additions'] = struct.unpack(
                '<' + '2s'*payload['restriction_additions_count'], payload_data[i:i+payload['restriction_additions_count']*2])
            i += payload['restriction_additions_count']*2
        else:
            payload['restriction_additions'] = []

        if payload['restriction_deletions_count'] > 0:
            payload['restriction_deletions'] = struct.unpack(
                '<' + '2s'*payload['restriction_deletions_count'], payload_data[i:i+payload['restriction_deletions_count']*24])
        else:
            payload['restriction_deletions'] = []

    # Mosaic restriction
    elif payload_type == b'4151':  # MosaicGlobalRestrictionTransaction
        schema = {
            'mosaic_id': 'Q',
            'reference_mosaic_id': 'Q',
            'restriction_key': 'Q',
            'previous_restriction_value': 'Q',
            'new_restriction_value': 'Q',
            'previous_restriction_type': 'B',
            'new_restriction_type': 'B'
        }
        payload = fmt_unpack(payload_data, schema)

    elif payload_type == b'4251':  # MosaicAddressRestrictionTransaction
        schema = {
            'mosaic_id': 'Q',
            'restriction_key': 'Q',
            'previous_restriction_value': 'Q',
            'new_restriction_value': 'Q',
            'target_address': '24s'
        }
        payload = fmt_unpack(payload_data, schema)
        payload['target_address'] = encode_address(payload['target_address'])

    # Transfer
    elif payload_type == b'4154':  # TransferTransaction
        schema = {
            'recipient_address': '24s',
            'message_size': 'H',
            'mosaics_count': 'B',
            'transfer_transaction_body_reserved_1': 'I',
            'transfer_transaction_body_reserved_2': 'B',
        }
        payload = fmt_unpack(payload_data[:32], schema)
        i = 32
        payload['mosaics'] = []
        for _ in range(payload['mosaics_count']):
            mosaic = {}
            mosaic['mosaic_id'] = struct.unpack('<Q', payload_data[i:i+8])[0]
            mosaic['amount'] = struct.unpack('<Q', payload_data[i+8:i+16])[0]
            payload['mosaics'].append(mosaic)
            i += 16
        payload['message'] = payload_data[-payload['message_size']:]
        payload['recipient_address'] = encode_address(payload['recipient_address'])

    else:
        raise ValueError(f'Unknown Tx payload type encountered: {payload_type}')

    return payload


def get_block_stats(block):
    """Extract summary data from a block and flatten for tabular manipulation"""
    data = block['header'].copy()
    data['statement_count'] = block['footer']['statement_count']
    data['tx_count'] = block['footer']['tx_count']
    data['total_fee'] = block['footer']['total_fee']
    return data
