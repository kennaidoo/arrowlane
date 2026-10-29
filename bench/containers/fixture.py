"""The canonical eight-column fixture used by every container benchmark."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pyarrow as pa


def sample_table(rows: int = 500) -> pa.Table:
    """Build the same table as the Rust and Zig fixture builders."""

    if rows < 0:
        raise ValueError("rows must be non-negative")
    schema = pa.schema(
        [
            ("id", pa.int64()),
            ("name", pa.string()),
            ("score", pa.float64()),
            ("ok", pa.bool_()),
            ("day", pa.date32()),
            ("amount", pa.decimal128(9, 2)),
            ("ts", pa.timestamp("us", tz="UTC")),
            ("blob", pa.binary()),
        ]
    )
    columns = [
        pa.array(range(rows), type=pa.int64()),
        pa.array([f"row-{index}" if index % 7 else None for index in range(rows)]),
        pa.array([index / 3.0 for index in range(rows)]),
        pa.array([index % 2 == 0 for index in range(rows)]),
        pa.array(
            [datetime.date(2026, 1, index % 28 + 1) for index in range(rows)],
            type=pa.date32(),
        ),
        pa.array([Decimal("12.34") for _ in range(rows)], type=pa.decimal128(9, 2)),
        pa.array(
            [datetime.datetime(2026, 10, 28, 12, 0, tzinfo=datetime.UTC) for _ in range(rows)],
            type=pa.timestamp("us", tz="UTC"),
        ),
        pa.array([b"\x00\x01\x02" for _ in range(rows)], type=pa.binary()),
    ]
    return pa.Table.from_arrays(columns, schema=schema)
