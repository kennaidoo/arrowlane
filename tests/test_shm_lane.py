"""Shared memory lane. POSIX only."""

from __future__ import annotations

import gc
from pathlib import Path

import pyarrow as pa
import pytest

from arrowlane.errors import AuthError, LaneUnavailable, OversizeFrame, SegmentError, SegmentGone
from arrowlane.lanes.ipc_lane import encode_ipc
from arrowlane.lanes.shm_lane import ShmLane

pytestmark = pytest.mark.linux
TOKEN = "t" * 32


@pytest.fixture
def table() -> pa.Table:
    return pa.table({"a": pa.array(range(5000), type=pa.int64()), "b": ["x" * 8] * 5000})


def test_roundtrip(tmp_path: Path, table: pa.Table) -> None:
    lane = ShmLane(directory=tmp_path, token=TOKEN)
    frame = lane.encode(table)
    assert frame.header["media_type"] == "application/vnd.arrowlane.shm"
    out = lane.decode(frame)
    assert out.equals(table)
    gc.collect()


def test_mapping_outlives_the_local_name(tmp_path: Path, table: pa.Table) -> None:
    lane = ShmLane(directory=tmp_path, token=TOKEN)
    out = lane.decode(lane.encode(table))
    gc.collect()
    assert out.column("a")[4999].as_py() == 4999


def test_segment_is_consumed_once(tmp_path: Path, table: pa.Table) -> None:
    lane = ShmLane(directory=tmp_path, token=TOKEN)
    frame = lane.encode(table)
    lane.decode(frame)
    gc.collect()
    with pytest.raises(SegmentGone):
        lane.decode(frame)


def test_wrong_token_is_rejected(tmp_path: Path, table: pa.Table) -> None:
    producer = ShmLane(directory=tmp_path, token=TOKEN)
    consumer = ShmLane(directory=tmp_path, token="w" * 32)
    with pytest.raises(AuthError):
        consumer.decode(producer.encode(table))


def test_descriptor_lives_in_the_frame_payload(tmp_path: Path, table: pa.Table) -> None:
    frame = ShmLane(directory=tmp_path, token=TOKEN).encode(table)
    assert b'"name":"al-' in frame.payload
    assert frame.uncompressed_len == len(encode_ipc(table))


def test_release_removes_an_unsent_segment(tmp_path: Path, table: pa.Table) -> None:
    lane = ShmLane(directory=tmp_path, token=TOKEN)
    frame = lane.encode(table)
    lane.release(frame)
    assert list(tmp_path.iterdir()) == []


def test_lane_reports_its_own_ready_state(tmp_path: Path) -> None:
    lane = ShmLane(directory=tmp_path, token=TOKEN)
    assert lane.ready() is True


def test_encode_requires_a_token(tmp_path: Path, table: pa.Table) -> None:
    with pytest.raises(LaneUnavailable):
        ShmLane(directory=tmp_path).encode(table)


def test_decode_requires_a_token(tmp_path: Path, table: pa.Table) -> None:
    lane = ShmLane(directory=tmp_path, token=TOKEN)
    frame = lane.encode(table)
    with pytest.raises(LaneUnavailable):
        ShmLane(directory=tmp_path).decode(frame)
    lane.release(frame)


def test_descriptor_length_mismatch_is_rejected(tmp_path: Path, table: pa.Table) -> None:
    lane = ShmLane(directory=tmp_path, token=TOKEN)
    frame = lane.encode(table)
    wrong = type(frame)(
        frame.lane_id,
        frame.payload,
        frame.rows,
        frame.uncompressed_len + 1,
        frame.header,
    )
    with pytest.raises(SegmentError, match="descriptor length"):
        lane.decode(wrong)
    lane.release(frame)


def test_oversize_segment_is_rejected(tmp_path: Path, table: pa.Table) -> None:
    lane = ShmLane(directory=tmp_path, token=TOKEN)
    frame = lane.encode(table)
    with pytest.raises(OversizeFrame):
        lane.decode(frame, max_uncompressed=1)
    lane.release(frame)
