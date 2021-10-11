"""Symbol Block Structure Processing Utilities"""

import base64
import hashlib
import struct


def fmt_unpack(buffer, struct_format):
    """Unpack buffer of bytes into dict based on format specification"""
    return dict(
        zip(
            struct_format.keys(),
            struct.unpack('<'+''.join(struct_format.values()), buffer)
        )
    )


def encode_address(address):
    """Encode address bytes into base32 with appropriate offset and pad"""
    return base64.b32encode(address + bytes(0)).decode('utf8')[0:-1]


def public_key_to_address(public_key, network=104):
    """Convert a public key to an address

    Parameters
    ----------
    public_key : bytes
        Byte array containing public key
    network: int, default=104
        Network identifier

    Returns
    -------
    address: bytes
        Address associated with input public_key
    """
    part_one_hash_builder = hashlib.sha3_256()
    part_one_hash_builder.update(public_key)
    part_one_hash = part_one_hash_builder.digest()

    part_two_hash_builder = hashlib.new('ripemd160')
    part_two_hash_builder.update(part_one_hash)
    part_two_hash = part_two_hash_builder.digest()

    base = bytes([network]) + part_two_hash

    part_three_hash_builder = hashlib.sha3_256()
    part_three_hash_builder.update(base)
    checksum = part_three_hash_builder.digest()[0:3]

    address = base + checksum

    return encode_address(address)
