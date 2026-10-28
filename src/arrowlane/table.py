"""One place where Python objects become Arrow tables."""

from __future__ import annotations

import hashlib
from typing import Any

import pyarrow as pa


def to_table(obj: Any) -> pa.Table:
    """Convert a table-like object to Arrow. Never copies an Arrow table."""
    if isinstance(obj, pa.Table):
        return obj
    if isinstance(obj, pa.RecordBatch):
        return pa.Table.from_batches([obj])
    if isinstance(obj, dict):
        return pa.table(obj)
    if isinstance(obj, (list, tuple)):
        return pa.Table.from_pylist(list(obj))
    module = type(obj).__module__.split(".")[0]
    if module == "pandas":
        return pa.Table.from_pandas(obj, preserve_index=False)
    if module == "polars":
        return pa.table(obj)
    if hasattr(obj, "__arrow_c_stream__"):
        return pa.table(obj)
    raise TypeError(f"cannot convert {type(obj).__name__} to an Arrow table")


def schema_digest(table: pa.Table) -> str:
    """Stable 32 character digest of the schema, independent of the data."""
    raw = table.schema.serialize().to_pybytes()
    return hashlib.sha256(raw).hexdigest()[:32]


def estimate_bytes(table: pa.Table) -> int:
    """Logical size of the table buffers in bytes."""
    return int(table.nbytes)
