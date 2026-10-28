"""Typed NDJSON lane.

This lane exists for compatibility and for the baseline measurement. It is not
the fast path. Values that JSON cannot carry are tagged, so a roundtrip keeps
timestamps, dates, times, decimals, binary and duration intact.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
from decimal import Decimal
from typing import Any

import pyarrow as pa

from ..errors import FrameError
from ..frame import Frame, header_for, schema_of
from .base import LaneInfo

INFO = LaneInfo(id=1, name="json", media_type="application/x-ndjson")

_TAG = "$"


def _default(value: Any) -> dict[str, Any]:
    """Tag a value that JSON cannot represent natively."""
    if isinstance(value, dt.datetime):
        return {_TAG: "ts", "v": value.isoformat()}
    if isinstance(value, dt.date):
        return {_TAG: "date", "v": value.isoformat()}
    if isinstance(value, dt.time):
        return {_TAG: "time", "v": value.isoformat()}
    if isinstance(value, dt.timedelta):
        return {_TAG: "dur", "v": value.total_seconds()}
    if isinstance(value, Decimal):
        return {_TAG: "dec", "v": str(value)}
    if isinstance(value, (bytes, bytearray)):
        return {_TAG: "bin", "v": base64.b64encode(bytes(value)).decode("ascii")}
    raise TypeError(f"JSON lane cannot encode {type(value).__name__}")


def _text(value: Any) -> str:
    """Require a string payload from a tag."""
    if not isinstance(value, str):
        raise FrameError("tagged value is not text")
    return value


def _revive(value: Any) -> Any:
    """Turn a tagged value back into the Python object Arrow expects."""
    if not (isinstance(value, dict) and _TAG in value):
        return value
    tag = value[_TAG]
    raw = value.get("v")
    if tag == "ts":
        return dt.datetime.fromisoformat(_text(raw))
    if tag == "date":
        return dt.date.fromisoformat(_text(raw))
    if tag == "time":
        return dt.time.fromisoformat(_text(raw))
    if tag == "dur":
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            raise FrameError("duration tag is not a number")
        return dt.timedelta(seconds=raw)
    if tag == "dec":
        return Decimal(_text(raw))
    if tag == "bin":
        return base64.b64decode(_text(raw))
    raise FrameError(f"unknown JSON lane tag {tag!r}")


class JsonLane:
    """One JSON object per line, typed by the Arrow schema in the header."""

    info = INFO

    def encode(self, table: pa.Table, *, level: int | None = None) -> Frame:
        """Encode a table as NDJSON. `level` is ignored."""
        rows = table.to_pylist()
        payload = b"\n".join(
            json.dumps(
                row, default=_default, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
            for row in rows
        )
        header = header_for(table, media_type=INFO.media_type)
        return Frame(INFO.id, payload, table.num_rows, len(payload), header)

    def decode(self, frame: Frame, *, max_uncompressed: int | None = None) -> pa.Table:
        """Decode NDJSON using the schema in the header."""
        schema = schema_of(frame.header)
        try:
            text = frame.payload.decode("utf-8")
            rows = [json.loads(line) for line in text.splitlines() if line]
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FrameError("payload is not valid NDJSON") from exc
        columns = []
        for field in schema:
            values = [_revive(row.get(field.name)) for row in rows]
            try:
                columns.append(pa.array(values, type=field.type))
            except (pa.ArrowInvalid, pa.ArrowTypeError) as exc:
                raise FrameError(
                    f"column {field.name!r} does not match the header schema"
                ) from exc
        return pa.Table.from_arrays(columns, schema=schema)
