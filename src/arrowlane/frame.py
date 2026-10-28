"""The wire frame: a 38 byte prefix, a JSON header, and an opaque payload.

The prefix is fixed width so a reader can validate lengths and the checksum
before it trusts, allocates for, or parses the payload.
"""

from __future__ import annotations

import base64
import json
import struct
import zlib
from dataclasses import dataclass
from typing import Any, Final

import pyarrow as pa

from .errors import (
    BadHeader,
    BadMagic,
    ChecksumMismatch,
    OversizeFrame,
    TruncatedFrame,
    UnknownLane,
    UnsupportedVersion,
)
from .version import __version__

MAGIC: Final = b"ALN1"
VERSION: Final = 1
FRAME_MEDIA_TYPE: Final = "application/vnd.arrowlane.frame"
MAX_HEADER_BYTES: Final = 65_535
MAX_PAYLOAD_BYTES: Final = 536_870_912
MAX_UNCOMPRESSED_BYTES: Final = 1_073_741_824

_FIXED = struct.Struct("<4sBBHQQQ")
_CRC = struct.Struct("<I")
_HLEN = struct.Struct("<H")
HEADER_SIZE: Final = _FIXED.size + _CRC.size + _HLEN.size

LANE_IDS: Final[dict[str, int]] = {"json": 1, "ipc": 2, "ipc-zstd": 3, "shm": 4}
ID_LANES: Final[dict[int, str]] = {value: key for key, value in LANE_IDS.items()}


@dataclass(frozen=True, slots=True)
class Frame:
    """One encoded payload with the metadata needed to decode it."""

    lane_id: int
    payload: bytes
    rows: int
    uncompressed_len: int
    header: dict[str, Any]
    flags: int = 0

    @property
    def lane(self) -> str:
        """Lane name for this frame."""
        try:
            return ID_LANES[self.lane_id]
        except KeyError as exc:
            raise UnknownLane(f"lane id {self.lane_id} is not registered") from exc


def header_for(table: pa.Table, **extra: Any) -> dict[str, Any]:
    """Build a frame header that carries the Arrow schema and a producer mark."""
    schema = base64.b64encode(table.schema.serialize().to_pybytes()).decode("ascii")
    return {
        "schema": schema,
        "ncols": table.num_columns,
        "producer": f"arrowlane/{__version__}",
        **extra,
    }


def schema_of(header: dict[str, Any]) -> pa.Schema:
    """Read the Arrow schema out of a frame header."""
    raw = header.get("schema")
    if not isinstance(raw, str):
        raise BadHeader("header carries no schema")
    try:
        decoded = base64.b64decode(raw, validate=True)
        return pa.ipc.read_schema(pa.BufferReader(decoded))
    except (ValueError, TypeError, pa.ArrowInvalid, pa.ArrowTypeError) as exc:
        raise BadHeader("schema is not a valid Arrow schema") from exc


def encode_frame(frame: Frame, *, max_payload: int = MAX_PAYLOAD_BYTES) -> bytes:
    """Serialise a frame. Rejects an oversize payload or header."""
    if max_payload > MAX_PAYLOAD_BYTES:
        raise OversizeFrame(f"max_payload {max_payload} exceeds {MAX_PAYLOAD_BYTES}")
    if len(frame.payload) > max_payload:
        raise OversizeFrame(f"payload {len(frame.payload)} exceeds {max_payload}")
    header = json.dumps(frame.header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(header) > MAX_HEADER_BYTES:
        raise OversizeFrame(f"header {len(header)} exceeds {MAX_HEADER_BYTES}")
    crc = zlib.crc32(frame.payload) & 0xFFFFFFFF
    return b"".join(
        (
            _FIXED.pack(
                MAGIC,
                VERSION,
                frame.lane_id,
                frame.flags,
                len(frame.payload),
                frame.uncompressed_len,
                frame.rows,
            ),
            _CRC.pack(crc),
            _HLEN.pack(len(header)),
            header,
            frame.payload,
        )
    )


def decode_frame(
    data: bytes | bytearray | memoryview,
    *,
    max_payload: int = MAX_PAYLOAD_BYTES,
    max_uncompressed: int = MAX_UNCOMPRESSED_BYTES,
) -> Frame:
    """Parse and validate a frame. Every check runs before the payload is copied."""
    view = memoryview(data)
    if view.nbytes < HEADER_SIZE:
        raise TruncatedFrame(f"{view.nbytes} bytes is shorter than {HEADER_SIZE}")
    magic, version, lane_id, flags, payload_len, uncompressed_len, rows = _FIXED.unpack_from(
        view, 0
    )
    if magic != MAGIC:
        raise BadMagic(f"expected {MAGIC!r}, got {magic!r}")
    if version != VERSION:
        raise UnsupportedVersion(f"frame version {version}, expected {VERSION}")
    if lane_id not in ID_LANES:
        raise UnknownLane(f"lane id {lane_id} is not registered")
    (crc,) = _CRC.unpack_from(view, _FIXED.size)
    (header_len,) = _HLEN.unpack_from(view, _FIXED.size + _CRC.size)
    if header_len > MAX_HEADER_BYTES:
        raise OversizeFrame(f"header {header_len} exceeds {MAX_HEADER_BYTES}")
    if payload_len > max_payload:
        raise OversizeFrame(f"payload {payload_len} exceeds {max_payload}")
    if uncompressed_len > max_uncompressed:
        raise OversizeFrame(f"uncompressed length {uncompressed_len} exceeds {max_uncompressed}")
    body_start = HEADER_SIZE + header_len
    if body_start + payload_len != view.nbytes:
        raise TruncatedFrame(
            f"frame declares {body_start + payload_len} bytes, carries {view.nbytes}"
        )
    try:
        header = json.loads(bytes(view[HEADER_SIZE:body_start]))
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
        raise BadHeader("header is not UTF-8 JSON") from exc
    if not isinstance(header, dict):
        raise BadHeader("header is not a JSON object")
    body = view[body_start:]
    if (zlib.crc32(body) & 0xFFFFFFFF) != crc:
        raise ChecksumMismatch("payload does not match the frame CRC")
    payload = bytes(body)
    return Frame(lane_id, payload, rows, uncompressed_len, header, flags)
