"""A deterministic table with the types the lanes must carry."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pyarrow as pa


def table(rows: int) -> pa.Table:
    """Build a table with integers, strings, decimals, booleans and timestamps."""
    stamp = dt.datetime(2026, 10, 28, 12, 0, tzinfo=dt.UTC)
    return pa.table(
        {
            "id": pa.array(range(rows), type=pa.int64()),
            "name": pa.array([f"name-{i % 1000:04d}" for i in range(rows)]),
            "amount": pa.array([Decimal("12.34")] * rows, type=pa.decimal128(9, 2)),
            "ok": pa.array([i % 2 == 0 for i in range(rows)]),
            "ts": pa.repeat(pa.scalar(stamp, type=pa.timestamp("us", tz="UTC")), rows),
        }
    )
