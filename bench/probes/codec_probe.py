"""Measure encode and decode cost for every portable lane."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import shutil
import statistics
import subprocess
import sys
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path

import numpy as np
import pyarrow as pa

from arrowlane.lanes import available_names, get_lane
from arrowlane.table import estimate_bytes

SHAPES = (1_000, 10_000, 100_000, 500_000)
REPEATS = 3
SEED = 20261028
GIT = shutil.which("git") or "git"


def build(rows: int) -> pa.Table:
    """A deterministic table with eight column types."""
    rng = np.random.default_rng(SEED)
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


def main(argv: list[str] | None = None) -> int:
    """Run the probe and write one JSON result file."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=REPEATS)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    lanes = [name for name in available_names() if name != "shm"]
    records = []
    for rows in SHAPES:
        table = build(rows)
        arrow_bytes = estimate_bytes(table)
        for name in lanes:
            lane = get_lane(name)
            frame = lane.encode(table)
            if not lane.decode(frame).equals(table):
                raise SystemExit(f"{name}: roundtrip failed")
            enc_ms = median_ms(partial(lane.encode, table), args.repeats)
            dec_ms = median_ms(partial(lane.decode, frame), args.repeats)
            records.append(
                {
                    "rows": rows,
                    "lane": name,
                    "arrow_bytes": arrow_bytes,
                    "wire_bytes": len(frame.payload),
                    "enc_ms": enc_ms,
                    "dec_ms": dec_ms,
                }
            )
            print(
                f"rows={rows} lane={name} enc={enc_ms:.3f} dec={dec_ms:.3f}",
                file=sys.stderr,
            )
    now = dt.datetime.now(dt.UTC)
    payload = {
        "schema_version": 1,
        "provenance": {
            "platform": sys.platform,
            "python": platform.python_version(),
            "pyarrow": pa.__version__,
            "commit": subprocess.check_output([GIT, "rev-parse", "HEAD"], text=True).strip(),
            "measured_at": now.isoformat(timespec="seconds"),
            "command": "python bench/probes/codec_probe.py",
            "shapes": list(SHAPES),
            "repeats": args.repeats,
        },
        "records": records,
    }
    out = args.out or Path("bench/results") / f"codec-{now:%Y%m%dT%H%M%SZ}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
