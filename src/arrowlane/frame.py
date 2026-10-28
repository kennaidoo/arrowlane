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
from typing import Any, BinaryIO, Final, NamedTuple

import pyarrow as pa

from .errors import (
    BadHeader,
    BadMagic,
    ChecksumMismatch,
    ChunkError,
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
MAX_CHUNKS: Final = 1_000_000

_FIXED = struct.Struct("<4sBBHQQQ")
_CRC = struct.Struct("<I")
_HLEN = struct.Struct("<H")
HEADER_SIZE: Final = _FIXED.size + _CRC.size + _HLEN.size

LANE_IDS: Final[dict[str, int]] = {"json": 1, "ipc": 2, "ipc-zstd": 3, "shm": 4}
ID_LANES: Final[dict[int, str]] = {value: key for key, value in LANE_IDS.items()}


@dataclass(frozen=True, slots=True)
class ChunkInfo:
    """Where one frame sits in a chunked stream."""

    id: str
    index: int
    last: bool

    def __post_init__(self) -> None:
        if (
            not isinstance(self.id, str)
            or len(self.id) != 32
            or any(character not in "0123456789abcdef" for character in self.id)
        ):
            raise ChunkError("chunk id must be 32 lowercase hex characters")
        if (
            not isinstance(self.index, int)
            or isinstance(self.index, bool)
            or not 0 <= self.index < MAX_CHUNKS
        ):
            raise ChunkError(f"chunk index must be 0..{MAX_CHUNKS - 1}")
        if not isinstance(self.last, bool):
            raise ChunkError("chunk last must be a boolean")

    def to_header(self) -> dict[str, object]:
        """Serialise the chunk position for the frame header."""
        return {"id": self.id, "index": self.index, "last": self.last}

    @classmethod
    def from_header(cls, value: object) -> ChunkInfo:
        """Parse untrusted chunk metadata from a frame header."""
        if not isinstance(value, dict):
            raise ChunkError("chunk header is not an object")
        if set(value) != {"id", "index", "last"}:
            raise ChunkError("chunk header must carry id, index and last")
        raw_id = value["id"]
        raw_index = value["index"]
        raw_last = value["last"]
        if (
            not isinstance(raw_id, str)
            or not isinstance(raw_index, int)
            or isinstance(raw_index, bool)
            or not isinstance(raw_last, bool)
        ):
            raise ChunkError("chunk header has the wrong field types")
        return cls(id=raw_id, index=raw_index, last=raw_last)


class _Prefix(NamedTuple):
    crc: int
    header_len: int
    payload_len: int
    flags: int
    lane_id: int
    rows: int
    uncompressed_len: int


@dataclass(frozen=True, slots=True)
class Frame:
    """One encoded payload with the metadata needed to decode it."""

    lane_id: int
    payload: bytes
    rows: int
    uncompressed_len: int
    header: dict[str, Any]
    flags: int = 0
    chunk: ChunkInfo | None = None

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


def _header_bytes(frame: Frame) -> bytes:
    """Serialise the header, adding chunk metadata when the frame carries it."""
    header = frame.header
    if frame.chunk is not None:
        header = {**header, "chunk": frame.chunk.to_header()}
    raw = json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(raw) > MAX_HEADER_BYTES:
        raise OversizeFrame(f"header {len(raw)} exceeds {MAX_HEADER_BYTES}")
    return raw


def _check_prefix(
    prefix: bytes | memoryview,
    *,
    max_payload: int,
    max_uncompressed: int,
) -> _Prefix:
    """Validate the fixed prefix and return its fields."""
    if len(prefix) < HEADER_SIZE:
        raise TruncatedFrame(f"{len(prefix)} bytes is shorter than {HEADER_SIZE}")
    magic, version, lane_id, flags, payload_len, uncompressed_len, rows = _FIXED.unpack_from(
        prefix, 0
    )
    if magic != MAGIC:
        raise BadMagic(f"expected {MAGIC!r}, got {magic!r}")
    if version != VERSION:
        raise UnsupportedVersion(f"frame version {version}, expected {VERSION}")
    if lane_id not in ID_LANES:
        raise UnknownLane(f"lane id {lane_id} is not registered")
    (crc,) = _CRC.unpack_from(prefix, _FIXED.size)
    (header_len,) = _HLEN.unpack_from(prefix, _FIXED.size + _CRC.size)
    if header_len > MAX_HEADER_BYTES:
        raise OversizeFrame(f"header {header_len} exceeds {MAX_HEADER_BYTES}")
    if payload_len > max_payload:
        raise OversizeFrame(f"payload {payload_len} exceeds {max_payload}")
    if uncompressed_len > max_uncompressed:
        raise OversizeFrame(f"uncompressed length {uncompressed_len} exceeds {max_uncompressed}")
    return _Prefix(crc, header_len, payload_len, flags, lane_id, rows, uncompressed_len)


def encode_frame_parts(
    frame: Frame, *, max_payload: int = MAX_PAYLOAD_BYTES
) -> tuple[bytes, bytes, bytes]:
    """Serialise a frame into prefix, header and payload without joining them."""
    if max_payload > MAX_PAYLOAD_BYTES:
        raise OversizeFrame(f"max_payload {max_payload} exceeds {MAX_PAYLOAD_BYTES}")
    if len(frame.payload) > max_payload:
        raise OversizeFrame(f"payload {len(frame.payload)} exceeds {max_payload}")
    header = _header_bytes(frame)
    crc = zlib.crc32(frame.payload) & 0xFFFFFFFF
    prefix = b"".join(
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
        )
    )
    return prefix, header, frame.payload


def encode_frame(frame: Frame, *, max_payload: int = MAX_PAYLOAD_BYTES) -> bytes:
    """Serialise a frame. Rejects an oversize payload or header."""
    prefix, header, payload = encode_frame_parts(frame, max_payload=max_payload)
    return b"".join((prefix, header, payload))


def write_frame(stream: BinaryIO, frame: Frame, *, max_payload: int = MAX_PAYLOAD_BYTES) -> int:
    """Write one frame in parts. Avoids the join copy of encode_frame."""
    total = 0
    for part in encode_frame_parts(frame, max_payload=max_payload):
        view = memoryview(part)
        while len(view):
            written = stream.write(view)
            if written is None or written <= 0:
                raise OSError("stream.write made no progress")
            total += written
            view = view[written:]
    return total


def _read_exact(stream: BinaryIO, size: int, *, allow_eof: bool = False) -> bytes | None:
    """Read exactly size bytes, or raise TruncatedFrame. A clean EOF is None."""
    if size == 0:
        return b""
    first = stream.read(size)
    if not first:
        if allow_eof:
            return None
        raise TruncatedFrame(f"stream ended after 0 of {size} bytes")
    if len(first) == size:
        return first
    parts = [first]
    received = len(first)
    while received < size:
        part = stream.read(size - received)
        if not part:
            raise TruncatedFrame(f"stream ended after {received} of {size} bytes")
        parts.append(part)
        received += len(part)
    return b"".join(parts)


def read_frame(
    stream: BinaryIO,
    *,
    max_payload: int = MAX_PAYLOAD_BYTES,
    max_uncompressed: int = MAX_UNCOMPRESSED_BYTES,
) -> Frame | None:
    """Read one frame from a stream. Returns None at a clean end of stream."""
    prefix = _read_exact(stream, HEADER_SIZE, allow_eof=True)
    if prefix is None:
        return None
    fields = _check_prefix(prefix, max_payload=max_payload, max_uncompressed=max_uncompressed)
    header = _read_exact(stream, fields.header_len)
    payload = _read_exact(stream, fields.payload_len)
    if header is None or payload is None:
        raise TruncatedFrame("stream ended inside a frame")
    return decode_frame_parts(
        prefix,
        header,
        payload,
        max_payload=max_payload,
        max_uncompressed=max_uncompressed,
    )


def decode_frame_parts(
    prefix: bytes | memoryview,
    header: bytes | memoryview,
    payload: bytes | memoryview,
    *,
    max_payload: int = MAX_PAYLOAD_BYTES,
    max_uncompressed: int = MAX_UNCOMPRESSED_BYTES,
) -> Frame:
    """Validate prefix, header and payload that were read separately."""
    fields = _check_prefix(prefix, max_payload=max_payload, max_uncompressed=max_uncompressed)
    if len(header) != fields.header_len:
        raise TruncatedFrame(f"header declares {fields.header_len} bytes, carries {len(header)}")
    if len(payload) != fields.payload_len:
        raise TruncatedFrame(f"payload declares {fields.payload_len} bytes, carries {len(payload)}")
    try:
        parsed = json.loads(bytes(header))
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
        raise BadHeader("header is not UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise BadHeader("header is not a JSON object")
    chunk: ChunkInfo | None = None
    if "chunk" in parsed:
        try:
            chunk = ChunkInfo.from_header(parsed["chunk"])
        except ChunkError as exc:
            raise BadHeader(f"chunk metadata is invalid: {exc}") from exc
    if (zlib.crc32(payload) & 0xFFFFFFFF) != fields.crc:
        raise ChecksumMismatch("payload does not match the frame CRC")
    body = payload if isinstance(payload, bytes) else bytes(payload)
    return Frame(
        fields.lane_id,
        body,
        fields.rows,
        fields.uncompressed_len,
        parsed,
        fields.flags,
        chunk,
    )


def decode_frame(
    data: bytes | bytearray | memoryview,
    *,
    max_payload: int = MAX_PAYLOAD_BYTES,
    max_uncompressed: int = MAX_UNCOMPRESSED_BYTES,
) -> Frame:
    """Parse and validate a frame. Every check runs before the payload is copied."""
    view = memoryview(data)
    fields = _check_prefix(view, max_payload=max_payload, max_uncompressed=max_uncompressed)
    body_start = HEADER_SIZE + fields.header_len
    if body_start + fields.payload_len != view.nbytes:
        raise TruncatedFrame(
            f"frame declares {body_start + fields.payload_len} bytes, carries {view.nbytes}"
        )
    return decode_frame_parts(
        view[:HEADER_SIZE],
        view[HEADER_SIZE:body_start],
        view[body_start:],
        max_payload=max_payload,
        max_uncompressed=max_uncompressed,
    )
