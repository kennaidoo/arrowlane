"""Run the canonical fixture through the Python package and print four fields."""

from __future__ import annotations

import argparse
import statistics
import time
from collections.abc import Callable
from functools import partial

from fixture import sample_table

import arrowlane

LANES = ("json", "ipc", "ipc-zstd")


def median_ms(fn: Callable[[], object], repeats: int) -> float:
    """Return the median wall time in milliseconds."""

    samples: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000.0)
    return statistics.median(samples)


def main() -> int:
    """Measure every portable lane and print one line per lane."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=200_000)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.rows < 0:
        parser.error("--rows must be non-negative")
    if args.repeats < 1:
        parser.error("--repeats must be positive")

    table = sample_table(args.rows)
    for lane in LANES:
        frame = arrowlane.pack(table, lane=lane)
        if not arrowlane.unpack(frame).equals(table):
            raise SystemExit(f"{lane}: roundtrip failed")
        arrowlane.pack(table, lane=lane)
        arrowlane.unpack(frame)
        encode_ms = median_ms(partial(arrowlane.pack, table, lane=lane), args.repeats)
        decode_ms = median_ms(partial(arrowlane.unpack, frame), args.repeats)
        print(f"{lane} {len(frame)} {encode_ms:.3f} {decode_ms:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
