"""Uncompressed Arrow IPC stream lane. It is the base for the zstd lane."""

from __future__ import annotations

import pyarrow as pa

from ..errors import FrameError, OversizeFrame
from ..frame import MAX_UNCOMPRESSED_BYTES, Frame, header_for, schema_of
from .base import LaneInfo

INFO = LaneInfo(id=2, name="ipc", media_type="application/vnd.apache.arrow.stream")


def encode_ipc(table: pa.Table) -> bytes:
    """Serialise a table as an Arrow IPC stream."""
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    raw: bytes = sink.getvalue().to_pybytes()
    return raw


def decode_ipc_buffer(source: pa.Buffer | pa.BufferReader) -> pa.Table:
    """Read an Arrow IPC stream from a buffer, without copying the buffer."""
    try:
        with pa.ipc.open_stream(source) as reader:
            return reader.read_all()
    except (pa.ArrowInvalid, pa.ArrowNotImplementedError, OSError) as exc:
        raise FrameError("payload is not a valid Arrow IPC stream") from exc


def decode_ipc(raw: bytes) -> pa.Table:
    """Read an Arrow IPC stream from bytes."""
    return decode_ipc_buffer(pa.BufferReader(raw))


def check_header_schema(frame: Frame, table: pa.Table) -> None:
    """Require the header schema and the payload schema to agree."""
    declared = schema_of(frame.header)
    if not declared.equals(table.schema):
        raise FrameError("frame header schema does not match the payload schema")


class IpcLane:
    """Uncompressed Arrow IPC over any transport."""

    info = INFO

    def encode(self, table: pa.Table, *, level: int | None = None) -> Frame:
        """Encode without compression. `level` is ignored and kept for the protocol."""
        raw = encode_ipc(table)
        header = header_for(table, media_type=INFO.media_type)
        return Frame(INFO.id, raw, table.num_rows, len(raw), header)

    def decode(self, frame: Frame, *, max_uncompressed: int | None = None) -> pa.Table:
        """Decode an IPC stream, within the caller's cap, with a matching schema."""
        cap = MAX_UNCOMPRESSED_BYTES if max_uncompressed is None else max_uncompressed
        if frame.uncompressed_len != len(frame.payload):
            raise FrameError("frame declares a different uncompressed length")
        if len(frame.payload) > cap:
            raise OversizeFrame(f"payload {len(frame.payload)} exceeds {cap}")
        table = decode_ipc(frame.payload)
        check_header_schema(frame, table)
        return table
