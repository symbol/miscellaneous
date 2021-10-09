"""Symbol Block Structure for Unpacking"""

HEADER_FORMAT = {
    'size': 'I',
    'reserved_1': 'I',
    'signature': '64s',
    'signer_public_key': '32s',
    'reserved_2': 'I',
    'version': 'B',
    'network': 'B',
    'type': '2s',
    'height': 'Q',
    'timestamp': 'Q',
    'difficulty': 'Q',
    'generation_hash_proof': '80s',
    'previous_block_hash': '32s',
    'transactions_hash': '32s',
    'receipts_hash': '32s',
    'state_hash': '32s',
    'beneficiary_address': '24s',
    'fee_multiplier': 'I'}

HEADER_LEN = 372

DB_OFFSET_BYTES = 800

FOOTER_FORMAT = {
    'reserved': 'I'}

FOOTER_LEN = 4

IMPORTANCE_FOOTER_FORMAT = {
    'voting_eligible_accounts_count': 'I',
    'harvesting_eligible_accounts_count': 'Q',
    'total_voting_balance': 'Q',
    'previous_importance_block_hash': '32s'}

IMPORTANCE_FOOTER_LEN = 52

TX_H_FORMAT = {
    'size': 'I',
    'reserved_1': 'I',
    'signature': '64s',
    'signer_public_key': '32s',
    'reserved_2': 'I',
    'version': 'B',
    'network': 'B',
    'type': '2s',
    'max_fee': 'Q',
    'deadline': 'Q',}

TX_H_LEN = 128

EMBED_TX_H_FORMAT = {
    'size': 'I',
    'reserved_1': 'I',
    'signer_public_key': '32s',
    'reserved_2': 'I',
    'version': 'B',
    'network': 'B',
    'type': '2s',}

EMBED_TX_H_LEN = 48

SUBCACHE_MERKLE_ROOT_FORMAT = {
    'account_state': '32s',
    'namespace': '32s',
    'mosaic': '32s',
    'multisig': '32s',
    'hash_lock_info': '32s',
    'secret_lock_info': '32s',
    'account_restriction': '32s',
    'mosaic_restriction': '32s',
    'metadata': '32s'}

TX_HASH_FORMAT = {
    'entity_hash': '32s',
    'merkle_component_hash': '32s'}

TX_HASH_LEN = 64

RECEIPT_SOURCE_FORMAT = {
    'primary_id': 'I',
    'secondary_id': 'I'}

RECEIPT_SOURCE_LEN = 8

RECEIPT_FORMAT = {
    'size': 'I',
    'version': 'H',
    'type': 'H'}

RECEIPT_LEN = 8

ADDRESS_RESOLUTION_FORMAT = {
    'primary_id': 'I',
    'secondary_id': 'I',
    'resolved': '24s' }

ADDRESS_RESOLUTION_LEN = 32

MOSAIC_RESOLUTION_FORMAT = {
    'primary_id': 'I',
    'secondary_id': 'I',
    'resolved': 'Q' }

MOSAIC_RESOLUTION_LEN = 16


TX_NAME_MAP = {
    b'414c': 'Account Key Link',
    b'424c': 'Node Key Link',
    b'4141': 'Aggregate Complete',
    b'4241': 'Aggregate Bonded',
    b'4143': 'Voting Key Link',
    b'4243': 'Vrf Key Link',
    b'414d': 'Mosaic Definition',
    b'424d': 'Mosaic Supply Change',
    b'414e': 'Namespace Registration',
    b'424e': 'Address Alias',
    b'434e': 'Mosaic Alias',
    b'4144': 'Account Metadata',
    b'4244': 'Mosaic Metadata',
    b'4344': 'Namespace Metadata',
    b'4155': 'Multisig Account Modification',
    b'4148': 'Hash Lock',
    b'4152': 'Secret Lock',
    b'4252': 'Secret Proof',
    b'4150': 'Account Address Restriction',
    b'4250': 'Account Mosaic Restriction',
    b'4350': 'Account Operation Restriction',
    b'4151': 'Mosaic Global Restriction',
    b'4251': 'Mosaic Address Restriction',
    b'4154': 'Transfer'}

