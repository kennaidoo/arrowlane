"""Measure peak Python allocations for whole frames and chunk streams."""

from __future__ import annotations

import argparse
import gc
import tracemalloc
from collections.abc import Callable
from typing import Any

import numpy as np
import pyarrow as pa

import arrowlane


def build(rows: int) -> pa.Table:
    rng = np.random.default_rng(1)
    return pa.table(
        {
            "id": pa.array(np.arange(rows, dtype=np.int64)),
            "value": pa.array(rng.normal(0, 1, rows)),
            "name": pa.array([f"n-{index % 1000:04d}" for index in range(rows)]),
            "flag": pa.array([index % 2 == 0 for index in range(rows)]),
        }
    )


def peak(call: Callable[[], Any]) -> tuple[Any, int]:
    gc.collect()
    tracemalloc.start()
    tracemalloc.reset_peak()
    result = call()
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, peak_bytes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=500_000)
    parser.add_argument("--chunk-rows", type=int, default=25_000)
    args = parser.parse_args()
    table = build(args.rows)
    print(f"rows={table.num_rows} chunk_rows={args.chunk_rows}")
    for lane in ("json", "ipc", "ipc-zstd"):
        wire, _ = peak(lambda lane=lane: arrowlane.pack(table, lane=lane))
        _, whole = peak(lambda lane=lane: arrowlane.pack(table, lane=lane))
        _, chunked = peak(
            lambda lane=lane: sum(
                len(part)
                for part in arrowlane.pack_chunks(
                    table,
                    lane=lane,
                    rows_per_chunk=args.chunk_rows,
                )
            )
        )
        print(
            f"{lane:9} wire={len(wire) / 1e6:8.2f}MB "
            f"whole_peak={whole / 1e6:8.2f}MB chunk_peak={chunked / 1e6:8.2f}MB"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
