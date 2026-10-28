"""Frame format contract."""

from __future__ import annotations

import struct
import zlib

import pyarrow as pa
import pytest

from arrowlane.errors import (
    BadHeader,
    BadMagic,
    ChecksumMismatch,
    OversizeFrame,
    TruncatedFrame,
    UnknownLane,
    UnsupportedVersion,
)
from arrowlane.frame import (
    HEADER_SIZE,
    MAGIC,
    VERSION,
    Frame,
    decode_frame,
    encode_frame,
    header_for,
    schema_of,
)


@pytest.fixture
def table() -> pa.Table:
    return pa.table({"a": [1, 2, 3], "b": ["x", "y", None]})


def test_roundtrip() -> None:
    frame = Frame(lane_id=2, payload=b"hello", rows=3, uncompressed_len=5, header={"k": "v"})
    out = decode_frame(encode_frame(frame))
    assert out.lane == "ipc"
    assert out.payload == b"hello"
    assert out.rows == 3
    assert out.uncompressed_len == 5
    assert out.header == {"k": "v"}


def test_prefix_size_is_stable() -> None:
    assert HEADER_SIZE == 38


def test_bad_magic() -> None:
    data = encode_frame(Frame(2, b"x", 0, 1, {}))
    with pytest.raises(BadMagic):
        decode_frame(b"XXXX" + data[4:])


def test_short_prefix() -> None:
    with pytest.raises(TruncatedFrame):
        decode_frame(b"ALN1")


def test_wrong_version() -> None:
    data = bytearray(encode_frame(Frame(2, b"x", 0, 1, {})))
    data[4] = 99
    with pytest.raises(UnsupportedVersion):
        decode_frame(bytes(data))


def test_unknown_lane() -> None:
    data = bytearray(encode_frame(Frame(2, b"x", 0, 1, {})))
    data[5] = 42
    with pytest.raises(UnknownLane):
        decode_frame(bytes(data))


def test_checksum_mismatch() -> None:
    data = bytearray(encode_frame(Frame(2, b"payload", 0, 7, {})))
    data[-1] ^= 0xFF
    with pytest.raises(ChecksumMismatch):
        decode_frame(bytes(data))


def test_trailing_bytes_are_rejected() -> None:
    data = encode_frame(Frame(2, b"x", 0, 1, {}))
    with pytest.raises(TruncatedFrame):
        decode_frame(data + b"extra")


def test_oversize_payload_is_rejected() -> None:
    with pytest.raises(OversizeFrame):
        encode_frame(Frame(2, b"0123456789", 0, 10, {}), max_payload=4)


def test_bad_header_json() -> None:
    header = b"not json"
    raw = (
        struct.pack("<4sBBHQQQ", MAGIC, VERSION, 2, 0, 1, 1, 0)
        + struct.pack("<I", zlib.crc32(b"x") & 0xFFFFFFFF)
        + struct.pack("<H", len(header))
        + header
        + b"x"
    )
    with pytest.raises(BadHeader):
        decode_frame(raw)


def test_schema_roundtrip(table: pa.Table) -> None:
    header = header_for(table, media_type="application/vnd.apache.arrow.stream")
    assert schema_of(header).equals(table.schema)
