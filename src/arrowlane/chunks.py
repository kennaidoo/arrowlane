"""Chunked frames for large tables.

Each chunk is a complete frame with `id`, `index` and `last` metadata. The
producer is a lazy iterator, so it encodes chunk n+1 only when the consumer
asks for it. A blocking write or a bounded queue therefore applies backpressure
to the producer.
"""

from __future__ import annotations

import uuid
from collections import deque
from collections.abc import Iterable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any, BinaryIO

import pyarrow as pa

from .costmodel import CostModel
from .errors import ChunkError, OversizeFrame, SegmentError
from .frame import (
    MAX_CHUNKS,
    MAX_PAYLOAD_BYTES,
    MAX_UNCOMPRESSED_BYTES,
    ChunkInfo,
    Frame,
    decode_frame,
    encode_frame,
    read_frame,
    write_frame,
)
from .lanes.base import Lane
from .select import Decision, Policy, Topology
from .table import to_table
from .transit import _lane, plan

DEFAULT_CHUNK_ROWS = 50_000
MAX_CHUNK_ROWS = 10_000_000


def _validate(rows_per_chunk: int, max_payload: int) -> None:
    if (
        not isinstance(rows_per_chunk, int)
        or isinstance(rows_per_chunk, bool)
        or not 1 <= rows_per_chunk <= MAX_CHUNK_ROWS
    ):
        raise ChunkError(f"rows_per_chunk must be 1..{MAX_CHUNK_ROWS}")
    if (
        not isinstance(max_payload, int)
        or isinstance(max_payload, bool)
        or not 0 < max_payload <= MAX_PAYLOAD_BYTES
    ):
        raise ChunkError(f"max_payload must be 1..{MAX_PAYLOAD_BYTES}")


def _empty_batch(schema: pa.Schema) -> pa.RecordBatch:
    arrays = [pa.array([], type=field.type) for field in schema]
    return pa.RecordBatch.from_arrays(arrays, schema=schema)


def _split(batches: deque[pa.RecordBatch], batch: pa.RecordBatch) -> None:
    middle = batch.num_rows // 2
    batches.appendleft(batch.slice(middle))
    batches.appendleft(batch.slice(0, middle))


def _release(chosen: Lane, frame: Frame) -> None:
    release = getattr(chosen, "release", None)
    if release is None:
        return
    try:
        release(frame)
    except OSError, SegmentError:
        return


def _chunk_frames(
    chosen: Lane,
    table: pa.Table,
    *,
    level: int | None,
    rows_per_chunk: int,
    max_payload: int,
) -> Iterator[Frame]:
    stream_id = uuid.uuid4().hex
    batches: deque[pa.RecordBatch] = deque(table.to_batches(max_chunksize=rows_per_chunk))
    if not batches:
        batches.append(_empty_batch(table.schema))
    index = 0
    while batches:
        batch = batches.popleft()
        chunk = pa.Table.from_batches([batch], schema=table.schema)
        try:
            frame = chosen.encode(chunk, level=level)
        except OversizeFrame, SegmentError:
            if batch.num_rows <= 1:
                raise
            _split(batches, batch)
            continue
        if len(frame.payload) > max_payload:
            _release(chosen, frame)
            if batch.num_rows <= 1:
                raise OversizeFrame(
                    f"one row encodes to {len(frame.payload)} bytes, over {max_payload}"
                )
            _split(batches, batch)
            continue
        if index >= MAX_CHUNKS:
            _release(chosen, frame)
            raise ChunkError(f"stream exceeds {MAX_CHUNKS} chunks")
        yield replace(frame, chunk=ChunkInfo(stream_id, index, not batches))
        index += 1


def _pack(chosen: Lane, frames: Iterable[Frame], max_payload: int) -> Iterator[bytes]:
    for frame in frames:
        try:
            yield encode_frame(frame, max_payload=max_payload)
        except OversizeFrame:
            _release(chosen, frame)
            raise


def pack_chunks(
    table: pa.Table,
    *,
    lane: str,
    token: str | None = None,
    directory: Path | None = None,
    level: int | None = None,
    rows_per_chunk: int = DEFAULT_CHUNK_ROWS,
    max_payload: int = MAX_PAYLOAD_BYTES,
) -> Iterator[bytes]:
    """Yield one wire frame per chunk. The iterator is the backpressure signal."""
    _validate(rows_per_chunk, max_payload)
    chosen = _lane(lane, token=token, directory=directory)
    frames = _chunk_frames(
        chosen,
        table,
        level=level,
        rows_per_chunk=rows_per_chunk,
        max_payload=max_payload,
    )
    return _pack(chosen, frames, max_payload)


def _decode_chunks(
    frames: Iterable[Frame],
    *,
    token: str | None,
    directory: Path | None,
    max_uncompressed: int,
) -> Iterator[pa.RecordBatch]:
    stream_id: str | None = None
    last_seen = False
    for expected, frame in enumerate(frames):
        info = frame.chunk
        if info is None:
            raise ChunkError("frame carries no chunk metadata")
        if stream_id is None:
            stream_id = info.id
        elif info.id != stream_id:
            raise ChunkError("chunk id changed mid stream")
        if last_seen:
            raise ChunkError("chunk after the last chunk")
        if info.index != expected:
            raise ChunkError(f"chunk index {info.index}, expected {expected}")
        chosen = _lane(frame.lane, token=token, directory=directory)
        try:
            table = chosen.decode(frame, max_uncompressed=max_uncompressed)
            batches = table.to_batches()
        finally:
            _release(chosen, frame)
        if batches:
            yield batches[0]
        else:
            yield _empty_batch(table.schema)
        last_seen = info.last
    if not last_seen:
        raise ChunkError("stream ended before the last chunk")


def unpack_chunks(
    frames: Iterable[bytes],
    *,
    token: str | None = None,
    directory: Path | None = None,
    max_payload: int = MAX_PAYLOAD_BYTES,
    max_uncompressed: int = MAX_UNCOMPRESSED_BYTES,
) -> Iterator[pa.RecordBatch]:
    """Decode a chunk stream and yield one batch per chunk."""
    decoded = (
        decode_frame(wire, max_payload=max_payload, max_uncompressed=max_uncompressed)
        for wire in frames
    )
    return _decode_chunks(
        decoded,
        token=token,
        directory=directory,
        max_uncompressed=max_uncompressed,
    )


def assemble_chunks(
    frames: Iterable[bytes],
    *,
    token: str | None = None,
    directory: Path | None = None,
    max_payload: int = MAX_PAYLOAD_BYTES,
    max_uncompressed: int = MAX_UNCOMPRESSED_BYTES,
) -> pa.Table:
    """Decode a chunk stream into one table."""
    batches = list(
        unpack_chunks(
            frames,
            token=token,
            directory=directory,
            max_payload=max_payload,
            max_uncompressed=max_uncompressed,
        )
    )
    if not batches:
        raise ChunkError("chunk stream is empty")
    return pa.Table.from_batches(batches, schema=batches[0].schema)


def write_chunks(
    stream: BinaryIO,
    table: pa.Table,
    *,
    lane: str,
    token: str | None = None,
    directory: Path | None = None,
    level: int | None = None,
    rows_per_chunk: int = DEFAULT_CHUNK_ROWS,
    max_payload: int = MAX_PAYLOAD_BYTES,
) -> tuple[int, int]:
    """Write a chunk stream to a binary stream. Returns (chunks, bytes)."""
    _validate(rows_per_chunk, max_payload)
    chosen = _lane(lane, token=token, directory=directory)
    frames = _chunk_frames(
        chosen,
        table,
        level=level,
        rows_per_chunk=rows_per_chunk,
        max_payload=max_payload,
    )
    chunks = 0
    total = 0
    for frame in frames:
        try:
            total += write_frame(stream, frame, max_payload=max_payload)
        except OSError, OversizeFrame:
            _release(chosen, frame)
            raise
        chunks += 1
    return chunks, total


def read_chunks(
    stream: BinaryIO,
    *,
    token: str | None = None,
    directory: Path | None = None,
    max_payload: int = MAX_PAYLOAD_BYTES,
    max_uncompressed: int = MAX_UNCOMPRESSED_BYTES,
) -> Iterator[pa.RecordBatch]:
    """Read a chunk stream from a binary stream and yield one batch per chunk."""

    def frames() -> Iterator[Frame]:
        while True:
            frame = read_frame(
                stream,
                max_payload=max_payload,
                max_uncompressed=max_uncompressed,
            )
            if frame is None:
                return
            yield frame

    return _decode_chunks(
        frames(),
        token=token,
        directory=directory,
        max_uncompressed=max_uncompressed,
    )


def transit_chunks(
    obj: Any,
    *,
    topology: Topology | str = Topology.SAME_NETWORK,
    policy: Policy | str = Policy.LATENCY,
    model: CostModel | None = None,
    allowed: tuple[str, ...] | None = None,
    token: str | None = None,
    directory: Path | None = None,
    level: int | None = None,
    rows_per_chunk: int = DEFAULT_CHUNK_ROWS,
    max_payload: int = MAX_PAYLOAD_BYTES,
) -> tuple[Iterator[bytes], Decision]:
    """Plan a lane and return a lazy chunk iterator with the decision."""
    table = to_table(obj)
    decision = plan(
        table,
        topology=topology,
        policy=policy,
        model=model,
        allowed=allowed,
        shm=token is not None,
    )
    frames = pack_chunks(
        table,
        lane=decision.lane,
        token=token,
        directory=directory,
        level=level,
        rows_per_chunk=rows_per_chunk,
        max_payload=max_payload,
    )
    return frames, decision
