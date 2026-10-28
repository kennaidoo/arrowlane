"""Chunk stream contract."""

from __future__ import annotations

import io

import pyarrow as pa
import pytest

import arrowlane
import arrowlane.chunks as chunks
import arrowlane.frame as frame_module
from arrowlane.errors import ChunkError
from arrowlane.frame import ChunkInfo, decode_frame, encode_frame
from arrowlane.lanes import get_lane


def build(rows: int) -> pa.Table:
    return pa.table(
        {"id": list(range(rows)), "name": [f"n-{index % 100}" for index in range(rows)]}
    )


@pytest.mark.parametrize("lane", ["json", "ipc", "ipc-zstd"])
def test_roundtrip(lane: str) -> None:
    table = build(1_000)
    frames = list(arrowlane.pack_chunks(table, lane=lane, rows_per_chunk=250))
    assert len(frames) == 4
    assert arrowlane.assemble_chunks(frames).equals(table)


def test_chunk_metadata_is_ordered() -> None:
    frames = list(arrowlane.pack_chunks(build(300), lane="ipc", rows_per_chunk=100))
    infos = [decode_frame(wire).chunk for wire in frames]
    assert all(isinstance(info, ChunkInfo) for info in infos)
    assert [info.index for info in infos if info is not None] == [0, 1, 2]
    assert [info.last for info in infos if info is not None] == [False, False, True]
    assert len({info.id for info in infos if info is not None}) == 1


def test_single_chunk_is_last() -> None:
    frames = list(arrowlane.pack_chunks(build(10), lane="ipc", rows_per_chunk=100))
    assert len(frames) == 1
    info = decode_frame(frames[0]).chunk
    assert info is not None
    assert info.index == 0
    assert info.last


def test_empty_table_is_one_chunk() -> None:
    table = build(0)
    frames = list(arrowlane.pack_chunks(table, lane="ipc", rows_per_chunk=100))
    assert len(frames) == 1
    assert arrowlane.assemble_chunks(frames).equals(table)


def test_splits_when_a_chunk_exceeds_the_payload_cap() -> None:
    table = build(1_000)
    frames = list(arrowlane.pack_chunks(table, lane="ipc", rows_per_chunk=500, max_payload=1_500))
    assert len(frames) > 2
    assert all(len(decode_frame(wire).payload) <= 1_500 for wire in frames)
    assert arrowlane.assemble_chunks(frames).equals(table)


def test_write_and_read_chunks() -> None:
    table = build(1_000)
    buffer = io.BytesIO()
    count, size = arrowlane.write_chunks(buffer, table, lane="ipc", rows_per_chunk=250)
    assert count == 4
    assert size == len(buffer.getvalue())
    buffer.seek(0)
    batches = list(arrowlane.read_chunks(buffer))
    assert len(batches) == 4
    assert pa.Table.from_batches(batches).equals(table)


def test_pack_chunks_is_lazy(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    original = frame_module.encode_frame

    def counted(frame: object, **kwargs: object) -> bytes:
        calls.append(1)
        return original(frame, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr("arrowlane.chunks.encode_frame", counted)
    stream = chunks.pack_chunks(build(300), lane="ipc", rows_per_chunk=100)
    assert calls == []
    next(stream)
    assert len(calls) == 1


def test_gap_is_rejected() -> None:
    frames = list(arrowlane.pack_chunks(build(300), lane="ipc", rows_per_chunk=100))
    with pytest.raises(ChunkError, match="index"):
        list(arrowlane.unpack_chunks([frames[0], frames[2]]))


def test_duplicate_is_rejected() -> None:
    frames = list(arrowlane.pack_chunks(build(300), lane="ipc", rows_per_chunk=100))
    with pytest.raises(ChunkError, match="index"):
        list(arrowlane.unpack_chunks([frames[0], frames[0], frames[1]]))


def test_missing_last_is_rejected() -> None:
    frames = list(arrowlane.pack_chunks(build(300), lane="ipc", rows_per_chunk=100))
    with pytest.raises(ChunkError, match="ended"):
        list(arrowlane.unpack_chunks(frames[:-1]))


def test_chunk_after_last_is_rejected() -> None:
    frames = list(arrowlane.pack_chunks(build(200), lane="ipc", rows_per_chunk=100))
    with pytest.raises(ChunkError, match="after"):
        list(arrowlane.unpack_chunks([frames[0], frames[1], frames[0]]))


def test_mixed_id_is_rejected() -> None:
    first = list(arrowlane.pack_chunks(build(200), lane="ipc", rows_per_chunk=100))
    second = list(arrowlane.pack_chunks(build(200), lane="ipc", rows_per_chunk=100))
    with pytest.raises(ChunkError, match="id"):
        list(arrowlane.unpack_chunks([first[0], second[1]]))


def test_frame_without_chunk_metadata_is_rejected() -> None:
    wire = encode_frame(get_lane("ipc").encode(build(10)))
    with pytest.raises(ChunkError, match="metadata"):
        list(arrowlane.unpack_chunks([wire]))


def test_empty_stream_is_rejected() -> None:
    with pytest.raises(ChunkError, match="ended"):
        arrowlane.assemble_chunks([])


def test_rows_per_chunk_is_validated() -> None:
    with pytest.raises(ChunkError):
        arrowlane.pack_chunks(build(1), lane="ipc", rows_per_chunk=0)
    with pytest.raises(ChunkError):
        arrowlane.pack_chunks(build(1), lane="ipc", max_payload=0)


def test_transit_chunks_returns_a_decision() -> None:
    table = build(1_000)
    stream, decision = arrowlane.transit_chunks(table, topology="same_network")
    assert decision.lane in {"json", "ipc", "ipc-zstd"}
    assert arrowlane.assemble_chunks(stream).equals(table)
