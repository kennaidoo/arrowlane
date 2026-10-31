"""NDJSON encoder for the JSON lane.

The fast path serializes the whole row list in one orjson call with
OPT_PASSTHROUGH_DATETIME, so dates, times and timestamps reach the default hook
and are tagged, then splits the outer JSON array into NDJSON. It is used only
when every field is a scalar and no top-level string contains the split marker.
Nested columns and unsafe strings use the per-row fallback.

The fast path builds one dict per row through Table.to_pylist. That call is about
sixty percent of the encode cost at 200,000 rows, so this module is row-oriented
in practice.

A column-oriented encoder was written and measured on 2026-10-31. It produced
identical bytes and took 4,475 ms against 2,338 ms for this path, because
materialising each column and joining one bytes object per field costs more than
letting orjson walk the row list. It was reverted. Do not write it again without
a vectorised formatter that avoids the per-field concatenation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import orjson
import pyarrow as pa
import pyarrow.compute as pc

_DEFAULT = Callable[[Any], Any]
_SPLIT_MARKER = "},{"


def _is_fast_scalar(type_: pa.DataType) -> bool:
    """Return True for scalar types that cannot hold a nested object."""
    return bool(
        pa.types.is_null(type_)
        or pa.types.is_boolean(type_)
        or pa.types.is_integer(type_)
        or pa.types.is_floating(type_)
        or pa.types.is_decimal(type_)
        or pa.types.is_string(type_)
        or pa.types.is_large_string(type_)
        or pa.types.is_binary(type_)
        or pa.types.is_large_binary(type_)
        or pa.types.is_fixed_size_binary(type_)
        or pa.types.is_date32(type_)
        or pa.types.is_date64(type_)
        or pa.types.is_time32(type_)
        or pa.types.is_time64(type_)
        or pa.types.is_timestamp(type_)
        or pa.types.is_duration(type_)
    )


def _has_split_marker(table: pa.Table) -> bool:
    """Return True when a top-level string could confuse the array split."""
    for field, column in zip(table.schema, table.columns, strict=True):
        type_ = field.type
        if pa.types.is_string(type_) or pa.types.is_large_string(type_):
            matches = pc.match_substring(column, pattern=_SPLIT_MARKER)
            if pc.any(matches).as_py():
                return True
    return False


def _encode_rows(table: pa.Table, *, default: _DEFAULT) -> bytes:
    """Encode one row at a time. Used for nested or unsafe string columns."""
    rows = table.to_pylist()
    return b"\n".join(
        orjson.dumps(
            row,
            default=default,
            option=orjson.OPT_PASSTHROUGH_DATETIME,
        )
        for row in rows
    )


def encode_table(table: pa.Table, *, default: _DEFAULT) -> bytes:
    """Encode a table as NDJSON in one encoder call, then split it into lines."""
    rows = table.num_rows
    if rows == 0:
        return b""

    if not all(_is_fast_scalar(field.type) for field in table.schema):
        return _encode_rows(table, default=default)
    if _has_split_marker(table):
        return _encode_rows(table, default=default)

    payload = orjson.dumps(
        table.to_pylist(),
        default=default,
        option=orjson.OPT_PASSTHROUGH_DATETIME,
    )
    return payload[1:-1].replace(b"},{", b"}\n{")
