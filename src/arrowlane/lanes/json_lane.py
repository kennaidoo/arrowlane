"""Typed NDJSON lane.

This lane exists for compatibility and for the baseline measurement. It is not
the fast path. Values that JSON cannot carry are tagged, so a roundtrip keeps
timestamps, dates, times, decimals, binary and duration intact.
"""

from __future__ import annotations

import base64
import datetime as dt
from decimal import Decimal
from typing import Any

import orjson
import pyarrow as pa

from ..errors import FrameError, OversizeFrame
from ..frame import MAX_UNCOMPRESSED_BYTES, Frame, header_for, schema_of
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
            orjson.dumps(
                row,
                default=_default,
                option=orjson.OPT_PASSTHROUGH_DATETIME,
            )
            for row in rows
        )
        header = header_for(table, media_type=INFO.media_type)
        return Frame(INFO.id, payload, table.num_rows, len(payload), header)

    def decode(self, frame: Frame, *, max_uncompressed: int | None = None) -> pa.Table:
        """Decode NDJSON using the schema in the header. Rows must match it."""
        cap = MAX_UNCOMPRESSED_BYTES if max_uncompressed is None else max_uncompressed
        if frame.uncompressed_len != len(frame.payload):
            raise FrameError("frame declares a different uncompressed length")
        if len(frame.payload) > cap:
            raise OversizeFrame(f"payload {len(frame.payload)} exceeds {cap}")
        schema = schema_of(frame.header)
        try:
            rows = [orjson.loads(line) for line in frame.payload.splitlines() if line]
        except (UnicodeDecodeError, orjson.JSONDecodeError, RecursionError) as exc:
            raise FrameError("payload is not valid NDJSON") from exc
        expected = {field.name for field in schema}
        for row in rows:
            if not isinstance(row, dict):
                raise FrameError("payload row is not a JSON object")
            if row.keys() != expected:
                missing = expected - row.keys()
                if missing:
                    raise FrameError(f"row is missing column {sorted(missing)[0]!r}")
                extra = row.keys() - expected
                raise FrameError(f"row carries unknown column {sorted(extra)[0]!r}")
        columns = []
        for field in schema:
            values = [_revive(row[field.name]) for row in rows]
            try:
                columns.append(pa.array(values, type=field.type))
            except (pa.ArrowInvalid, pa.ArrowTypeError) as exc:
                raise FrameError(f"column {field.name!r} does not match the header schema") from exc
        return pa.Table.from_arrays(columns, schema=schema)
