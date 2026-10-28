"""Typed NDJSON lane."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pyarrow as pa
import pytest

from arrowlane.errors import FrameError
from arrowlane.lanes.json_lane import JsonLane


@pytest.fixture
def rich() -> pa.Table:
    schema = pa.schema(
        [
            ("id", pa.int64()),
            ("name", pa.string()),
            ("ts", pa.timestamp("us", tz="UTC")),
            ("day", pa.date32()),
            ("at", pa.time64("us")),
            ("amount", pa.decimal128(9, 2)),
            ("blob", pa.binary()),
            ("ok", pa.bool_()),
        ]
    )
    row = {
        "id": 7,
        "name": "caf\u00e9",
        "ts": dt.datetime(2026, 10, 28, 12, 0, tzinfo=dt.UTC),
        "day": dt.date(2026, 10, 28),
        "at": dt.time(12, 0, 1, 500),
        "amount": Decimal("1234.50"),
        "blob": b"\x00\x01",
        "ok": True,
    }
    columns = [pa.array([row[field.name]], type=field.type) for field in schema]
    return pa.Table.from_arrays(columns, schema=schema)


def test_roundtrip_rich_types(rich: pa.Table) -> None:
    lane = JsonLane()
    frame = lane.encode(rich)
    assert frame.header["media_type"] == "application/x-ndjson"
    out = lane.decode(frame)
    assert out.equals(rich)
    assert out.to_pylist()[0]["amount"] == Decimal("1234.50")
    assert out.to_pylist()[0]["ts"].tzinfo is not None


def test_nulls_roundtrip() -> None:
    table = pa.table({"a": pa.array([1, None], type=pa.int64()), "b": [None, "x"]})
    assert JsonLane().decode(JsonLane().encode(table)).equals(table)


def test_empty_table() -> None:
    table = pa.table({"a": pa.array([], type=pa.int64())})
    frame = JsonLane().encode(table)
    assert frame.payload == b""
    assert JsonLane().decode(frame).num_rows == 0


def test_unknown_tag_is_rejected() -> None:
    table = pa.table({"a": [1]})
    frame = JsonLane().encode(table)
    payload = b'{"a":{"$":"weird","v":1}}'
    broken = type(frame)(frame.lane_id, payload, 1, len(payload), frame.header)
    with pytest.raises(FrameError, match="unknown JSON lane tag"):
        JsonLane().decode(broken)


def test_bad_json_line_raises_frame_error() -> None:
    table = pa.table({"a": [1]})
    frame = JsonLane().encode(table)
    broken = type(frame)(frame.lane_id, b"{not json", 1, 9, frame.header)
    with pytest.raises(FrameError):
        JsonLane().decode(broken)
