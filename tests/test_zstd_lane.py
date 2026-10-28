"""Zstd lane, including the decompression bound."""

from __future__ import annotations

import compression.zstd as zstd

import pyarrow as pa
import pytest

from arrowlane.errors import FrameError, OversizeFrame
from arrowlane.frame import header_for
from arrowlane.lanes.ipc_lane import encode_ipc
from arrowlane.lanes.zstd_lane import ZstdLane, bounded_decompress


@pytest.fixture
def table() -> pa.Table:
    return pa.table({"a": pa.array(range(5000), type=pa.int64()), "b": ["x" * 20] * 5000})


def test_roundtrip_and_compression(table: pa.Table) -> None:
    lane = ZstdLane()
    plain = encode_ipc(table)
    frame = lane.encode(table, level=3)
    assert frame.header["codec"] == "zstd"
    assert frame.header["zstd_level"] == 3
    assert frame.uncompressed_len == len(plain)
    assert len(frame.payload) < len(plain)
    assert lane.decode(frame).equals(table)


def test_default_level_is_three(table: pa.Table) -> None:
    assert ZstdLane().encode(table).header["zstd_level"] == 3


def test_declared_size_over_cap_is_rejected(table: pa.Table) -> None:
    frame = ZstdLane().encode(table)
    with pytest.raises(OversizeFrame):
        ZstdLane().decode(frame, max_uncompressed=100)


def test_actual_size_over_cap_is_rejected() -> None:
    payload = zstd.compress(b"x" * 1_000_000)
    with pytest.raises(OversizeFrame):
        bounded_decompress(payload, cap=1000)


def test_corrupt_payload_raises_frame_error(table: pa.Table) -> None:
    frame = ZstdLane().encode(table)
    broken = type(frame)(
        frame.lane_id, frame.payload[:-8], frame.rows, frame.uncompressed_len, frame.header
    )
    with pytest.raises(FrameError):
        ZstdLane().decode(broken)


def test_level_out_of_range_is_rejected(table: pa.Table) -> None:
    with pytest.raises(ValueError, match="level"):
        ZstdLane().encode(table, level=99)


def test_length_mismatch_is_rejected(table: pa.Table) -> None:
    frame = ZstdLane().encode(table)
    wrong = type(frame)(
        frame.lane_id, frame.payload, frame.rows, frame.uncompressed_len + 1, frame.header
    )
    with pytest.raises(FrameError, match="length"):
        ZstdLane().decode(wrong)


def test_header_schema_mismatch_is_rejected(table: pa.Table) -> None:
    other = pa.table({"b": ["x"] * table.num_rows})
    frame = ZstdLane().encode(other)
    wrong = type(frame)(
        frame.lane_id,
        frame.payload,
        frame.rows,
        frame.uncompressed_len,
        header_for(table),
    )
    with pytest.raises(FrameError, match="schema"):
        ZstdLane().decode(wrong)
