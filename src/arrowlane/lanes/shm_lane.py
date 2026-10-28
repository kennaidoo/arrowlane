"""Shared memory lane: Arrow IPC in a POSIX segment, descriptor on the wire."""

from __future__ import annotations

import os
from pathlib import Path

import pyarrow as pa

from ..errors import LaneUnavailable, OversizeFrame, SegmentError
from ..frame import Frame, header_for
from ..shm import Descriptor, read_segment, write_segment
from .base import LaneInfo
from .ipc_lane import decode_ipc_buffer, encode_ipc

INFO = LaneInfo(id=4, name="shm", media_type="application/vnd.arrowlane.shm", requires="posix")


class ShmLane:
    """Write the table to a segment and put only the descriptor on the wire."""

    info = INFO

    def __init__(
        self,
        *,
        directory: Path | None = None,
        token: str | None = None,
        verify: bool = True,
    ) -> None:
        self._directory = directory
        self._token = token
        self._verify = verify

    def encode(self, table: pa.Table, *, level: int | None = None) -> Frame:
        """Serialise to IPC, write the segment, return a frame that carries the descriptor."""
        if os.name != "posix":
            raise LaneUnavailable("the shm lane requires a POSIX platform")
        if not self._token:
            raise LaneUnavailable("the shm lane requires a shared token")
        raw = encode_ipc(table)
        descriptor = write_segment(raw, directory=self._directory, token=self._token)
        return Frame(
            INFO.id,
            descriptor.to_bytes(),
            table.num_rows,
            len(raw),
            header_for(table, media_type=INFO.media_type, segment=descriptor.name),
        )

    def decode(self, frame: Frame, *, max_uncompressed: int | None = None) -> pa.Table:
        """Attach to the segment and return a table whose buffers own the mapping."""
        if not self._token:
            raise LaneUnavailable("the shm lane requires a shared token")
        descriptor = Descriptor.from_bytes(frame.payload)
        if descriptor.length != frame.uncompressed_len:
            raise SegmentError("descriptor length does not match the frame")
        if max_uncompressed is not None and descriptor.length > max_uncompressed:
            raise OversizeFrame("segment exceeds the uncompressed cap")
        buffer, _mapping = read_segment(
            descriptor,
            directory=self._directory,
            token=self._token,
            verify=self._verify,
        )
        return decode_ipc_buffer(buffer)
