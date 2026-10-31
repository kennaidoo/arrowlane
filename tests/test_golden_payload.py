"""The json payload is pinned byte for byte, across implementations.

The C++ test suite pins the same 606 bytes. If orjson changes how it formats a
float, this test fails in the package that owns the format, before the C++ port
reports a mismatch that looks like its own bug.
"""

from __future__ import annotations

import datetime

import pyarrow as pa

from arrowlane.lanes.json_lane import JsonLane

GOLDEN = (
    '{"id":0,"name":null,"score":0.0,"ok":true,"day":{"$":"date","v":"2026-01-01"},'
    '"amount":{"$":"dec","v":"12.34"},"ts":{"$":"ts","v":"2026-10-28T12:00:00+00:00"},'
    '"blob":{"$":"bin","v":"AAEC"}}\n'
    '{"id":1,"name":"row-1","score":0.3333333333333333,"ok":false,'
    '"day":{"$":"date","v":"2026-01-02"},"amount":{"$":"dec","v":"12.34"},'
    '"ts":{"$":"ts","v":"2026-10-28T12:00:00+00:00"},"blob":{"$":"bin","v":"AAEC"}}\n'
    '{"id":2,"name":"row-2","score":0.6666666666666666,"ok":true,'
    '"day":{"$":"date","v":"2026-01-03"},"amount":{"$":"dec","v":"12.34"},'
    '"ts":{"$":"ts","v":"2026-10-28T12:00:00+00:00"},"blob":{"$":"bin","v":"AAEC"}}'
)


def fixture_table() -> pa.Table:
    days = (datetime.date(2026, 1, 1) - datetime.date(1970, 1, 1)).days
    stamp = datetime.datetime(2026, 10, 28, 12, 0, 0, tzinfo=datetime.timezone.utc)
    micros = int(stamp.timestamp() * 1_000_000)
    return pa.table(
        {
            "id": pa.array([0, 1, 2], type=pa.int64()),
            "name": pa.array([None, "row-1", "row-2"]),
            "score": pa.array([0.0, 1.0 / 3.0, 2.0 / 3.0], type=pa.float64()),
            "ok": pa.array([True, False, True]),
            "day": pa.array([days, days + 1, days + 2], type=pa.date32()),
            "amount": pa.array(["12.34"] * 3, type=pa.string()).cast(
                pa.decimal128(9, 2)
            ),
            "ts": pa.array([micros] * 3, type=pa.timestamp("us", tz="UTC")),
            "blob": pa.array([b"\x00\x01\x02"] * 3, type=pa.binary()),
        }
    )


def test_golden_payload_is_byte_identical() -> None:
    payload = JsonLane().encode(fixture_table()).payload.decode()
    assert payload == GOLDEN
    assert len(payload) == 606


def test_golden_payload_round_trips() -> None:
    lane = JsonLane()
    table = fixture_table()
    assert lane.decode(lane.encode(table)).equals(table)
