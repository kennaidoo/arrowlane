"""Arrow IPC compressed with the standard library zstd.

Decompression is bounded: the reader stops at cap + 1 bytes, so a frame that
lies about its uncompressed length cannot allocate without limit.
"""

from __future__ import annotations

import compression.zstd as zstd
import io

import pyarrow as pa

from ..errors import FrameError, OversizeFrame
from ..frame import MAX_UNCOMPRESSED_BYTES, Frame, header_for
from .base import LaneInfo
from .ipc_lane import decode_ipc, encode_ipc

INFO = LaneInfo(id=3, name="ipc-zstd", media_type="application/vnd.apache.arrow.stream")
DEFAULT_LEVEL = 3
MIN_LEVEL = 1
MAX_LEVEL = 19


def bounded_decompress(payload: bytes, *, cap: int) -> bytes:
    """Decompress at most cap bytes. Raise OversizeFrame if more arrive."""
    try:
        with zstd.ZstdFile(io.BytesIO(payload)) as handle:
            out = handle.read(cap + 1)
    except (zstd.ZstdError, EOFError) as exc:
        raise FrameError("payload is not a valid zstd frame") from exc
    if len(out) > cap:
        raise OversizeFrame(f"decompressed data exceeds {cap} bytes")
    return out


class ZstdLane:
    """Arrow IPC inside one zstd frame."""

    info = INFO

    def encode(self, table: pa.Table, *, level: int | None = None) -> Frame:
        """Compress an IPC stream. Level defaults to 3."""
        chosen = DEFAULT_LEVEL if level is None else level
        if not MIN_LEVEL <= chosen <= MAX_LEVEL:
            raise ValueError(f"zstd level must be between {MIN_LEVEL} and {MAX_LEVEL}")
        raw = encode_ipc(table)
        payload = zstd.compress(raw, level=chosen)
        header = header_for(
            table, media_type=INFO.media_type, codec="zstd", zstd_level=chosen
        )
        return Frame(INFO.id, payload, table.num_rows, len(raw), header)

    def decode(self, frame: Frame, *, max_uncompressed: int | None = None) -> pa.Table:
        """Decompress with a hard cap, then read the IPC stream."""
        cap = MAX_UNCOMPRESSED_BYTES if max_uncompressed is None else max_uncompressed
        if frame.uncompressed_len > cap:
            raise OversizeFrame(f"frame declares {frame.uncompressed_len} bytes, cap is {cap}")
        raw = bounded_decompress(frame.payload, cap=cap)
        if len(raw) != frame.uncompressed_len:
            raise FrameError(
                f"length mismatch: declared {frame.uncompressed_len}, decompressed {len(raw)}"
            )
        return decode_ipc(raw)
