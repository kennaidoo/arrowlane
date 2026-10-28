"""Arrow IPC lane."""

from __future__ import annotations

from decimal import Decimal

import pyarrow as pa
import pytest

from arrowlane.errors import FrameError
from arrowlane.lanes.ipc_lane import IpcLane, decode_ipc, encode_ipc


@pytest.fixture
def table() -> pa.Table:
    return pa.table(
        {
            "id": pa.array(range(1000), type=pa.int64()),
            "name": pa.array([f"n{i}" for i in range(1000)]),
            "flag": pa.array([i % 2 == 0 for i in range(1000)]),
        }
    )


def test_roundtrip(table: pa.Table) -> None:
    lane = IpcLane()
    frame = lane.encode(table)
    assert frame.rows == 1000
    assert frame.uncompressed_len == len(frame.payload)
    assert frame.header["media_type"] == "application/vnd.apache.arrow.stream"
    out = lane.decode(frame)
    assert out.equals(table)


def test_helpers(table: pa.Table) -> None:
    assert decode_ipc(encode_ipc(table)).equals(table)


def test_truncated_payload_raises(table: pa.Table) -> None:
    frame = IpcLane().encode(table)
    broken = type(frame)(frame.lane_id, frame.payload[:100], 1000, 1000, frame.header)
    with pytest.raises(FrameError):
        IpcLane().decode(broken)


def test_null_and_decimal_roundtrip() -> None:
    schema = pa.schema([("a", pa.int64()), ("d", pa.decimal128(9, 2))])
    columns = [
        pa.array([1, None], type=pa.int64()),
        pa.array([Decimal("1.25"), None], type=pa.decimal128(9, 2)),
    ]
    table = pa.Table.from_arrays(columns, schema=schema)
    assert decode_ipc(encode_ipc(table)).equals(table)
