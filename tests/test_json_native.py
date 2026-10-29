"""Tests for the column-oriented NDJSON encoder."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pyarrow as pa

from arrowlane.frame import Frame, header_for
from arrowlane.lanes.json_lane import JsonLane, _default
from arrowlane.lanes.json_native import _encode_rows, encode_table


def rich_table() -> pa.Table:
    schema = pa.schema(
        [
            ("id", pa.int64()),
            ("name", pa.string()),
            ("ts", pa.timestamp("us", tz="UTC")),
            ("day", pa.date32()),
            ("at", pa.time64("us")),
            ("elapsed", pa.duration("us")),
            ("amount", pa.decimal128(9, 2)),
            ("blob", pa.binary()),
            ("ok", pa.bool_()),
        ]
    )
    row = {
        "id": 7,
        "name": "café",
        "ts": dt.datetime(2026, 10, 28, 12, 0, tzinfo=dt.UTC),
        "day": dt.date(2026, 10, 28),
        "at": dt.time(12, 0, 1, 500),
        "elapsed": dt.timedelta(seconds=1.5),
        "amount": Decimal("1234.50"),
        "blob": b"\x00\x01",
        "ok": True,
    }
    return pa.Table.from_arrays(
        [pa.array([row[field.name]], type=field.type) for field in schema],
        schema=schema,
    )


def test_native_writer_roundtrips_rich_values() -> None:
    table = rich_table()
    payload = encode_table(table, default=_default)
    header = header_for(table, media_type="application/x-ndjson")
    frame = Frame(1, payload, table.num_rows, len(payload), header)
    out = JsonLane().decode(frame)
    assert out.equals(table)
    assert payload.startswith(b"{")
    assert payload.endswith(b"}")
    assert b'"$":"ts"' in payload
    assert b'"$":"date"' in payload
    assert b'"$":"time"' in payload
    assert b'"$":"dur"' in payload
    assert b'"$":"dec"' in payload
    assert b'"$":"bin"' in payload
    assert b"caf\xc3\xa9" in payload


def test_native_writer_handles_empty_table() -> None:
    table = pa.table({"a": pa.array([], type=pa.int64())})
    assert encode_table(table, default=_default) == b""


def test_native_writer_handles_nulls() -> None:
    table = pa.table({"a": pa.array([1, None], type=pa.int64())})
    payload = encode_table(table, default=_default)
    assert b'"a":null' in payload


def test_native_writer_matches_row_encoding_for_scalar_table() -> None:
    table = rich_table()
    assert encode_table(table, default=_default) == _encode_rows(table, default=_default)


def test_native_writer_falls_back_when_string_contains_split_marker() -> None:
    table = pa.table({"s": pa.array(["a},{b", "x"], type=pa.string())})
    payload = encode_table(table, default=_default)
    header = header_for(table, media_type="application/x-ndjson")
    frame = Frame(1, payload, table.num_rows, len(payload), header)
    assert JsonLane().decode(frame).equals(table)


def test_native_writer_roundtrips_nested_types() -> None:
    table = pa.table({"values": pa.array([["a{b", "c}"], None], type=pa.list_(pa.string()))})
    payload = encode_table(table, default=_default)
    header = header_for(table, media_type="application/x-ndjson")
    frame = Frame(1, payload, table.num_rows, len(payload), header)
    assert JsonLane().decode(frame).equals(table)
