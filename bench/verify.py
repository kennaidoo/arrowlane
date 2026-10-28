"""Gate the transit claim with ratios and a negative control."""

from __future__ import annotations

import argparse
import datetime as dt
import statistics
import time
from collections.abc import Callable
from functools import partial

import numpy as np
import pyarrow as pa

from arrowlane.costmodel import load_default
from arrowlane.lanes import get_lane
from arrowlane.table import estimate_bytes

ROWS = 100_000
REPEATS = 3
MAX_MODEL_ERROR = 0.25


def build(rows: int) -> pa.Table:
    """The same eight-column shape used by the calibration probe."""
    rng = np.random.default_rng(20261028)
    stamp = dt.datetime(2026, 10, 28, 12, 0, tzinfo=dt.UTC)
    return pa.table(
        {
            "id": pa.array(np.arange(rows, dtype=np.int64)),
            "value": pa.array(rng.normal(100.0, 25.0, rows)),
            "count": pa.array(rng.integers(0, 10_000, rows, dtype=np.int64)),
            "flag": pa.array(rng.integers(0, 2, rows).astype(bool)),
            "name": pa.array([f"name-{i % 1000:04d}" for i in range(rows)]),
            "code": pa.array([f"C{i % 100:03d}" for i in range(rows)]),
            "label": pa.array(["alpha"] * rows),
            "ts": pa.repeat(pa.scalar(stamp, type=pa.timestamp("us", tz="UTC")), rows),
        }
    )


def median_ms(fn: Callable[[], object], repeats: int) -> float:
    """Median wall time in milliseconds."""
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000.0)
    return statistics.median(samples)


def measure(name: str, table: pa.Table) -> dict[str, float]:
    """Encode, decode and time one lane."""
    lane = get_lane(name)
    frame = lane.encode(table)
    if not lane.decode(frame).equals(table):
        raise SystemExit(f"{name}: roundtrip failed")
    enc_ms = median_ms(partial(lane.encode, table), REPEATS)
    dec_ms = median_ms(partial(lane.decode, frame), REPEATS)
    return {"bytes": float(len(frame.payload)), "ms": enc_ms + dec_ms}


def main(argv: list[str] | None = None) -> int:
    """Run every check and return a process exit code."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-json", action="store_true")
    args = parser.parse_args(argv)
    table = build(ROWS)
    arrow_bytes = estimate_bytes(table)
    measured = {name: measure(name, table) for name in ("json", "ipc", "ipc-zstd")}
    model = load_default()
    mb = arrow_bytes / 1e6
    fast = "json" if args.force_json else "ipc"
    checks = [
        ("ipc-bytes-smaller-than-json", measured["ipc"]["bytes"] < measured["json"]["bytes"]),
        ("zstd-bytes-smaller-than-ipc", measured["ipc-zstd"]["bytes"] < measured["ipc"]["bytes"]),
        (f"{fast}-faster-than-json", measured[fast]["ms"] < measured["json"]["ms"]),
    ]
    for name in ("ipc", "ipc-zstd"):
        predicted = model.predict(name, mb=mb, topology="same_network", policy="cpu")
        error = abs(predicted - measured[name]["ms"]) / measured[name]["ms"]
        checks.append((f"{name}-model-error-within-25-percent", error <= MAX_MODEL_ERROR))
    failed = 0
    for name, ok in checks:
        print(f"CHECK {name} {'PASS' if ok else 'FAIL'}")
        failed += 0 if ok else 1
    if failed:
        print("RESULT: FAIL")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
