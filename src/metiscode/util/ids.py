"""Identifier helpers."""

from __future__ import annotations

import os
import time

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode_base32(data: bytes) -> str:
    bits = 0
    value = 0
    output: list[str] = []
    for byte in data:
        value = (value << 8) | byte
        bits += 8
        while bits >= 5:
            bits -= 5
            output.append(_CROCKFORD[(value >> bits) & 0b11111])
    if bits:
        output.append(_CROCKFORD[(value << (5 - bits)) & 0b11111])
    return "".join(output)


def ulid_str() -> str:
    """Generate a 26-char ULID-like identifier (time + randomness)."""
    timestamp_ms = int(time.time() * 1000)
    ts_bytes = timestamp_ms.to_bytes(6, byteorder="big", signed=False)
    random_bytes = os.urandom(10)
    encoded = _encode_base32(ts_bytes + random_bytes)
    return encoded[:26]

