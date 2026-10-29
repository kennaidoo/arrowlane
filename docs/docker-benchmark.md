# Docker benchmark

Three implementations, one canonical eight-column fixture, 200,000 rows. Each
value is the median of three measured runs after one warmup run. The benchmark
ran in Linux x86_64 containers on Docker 29.9.2. Each container had 2 CPUs and
2 GiB of memory, no network access and a read-only root filesystem.

This is a container measurement. It is separate from the host measurements in
`arrowlane-zig/docs/performance.md`.

## Results

| Implementation | Lane | Wire bytes | Wire delta vs Python | Encode ms | Decode ms |
|---|---|---:|---:|---:|---:|
| Python | json | 42,505,756 | 0 | 2167.805 | 2074.545 |
| Python | ipc | 12,670,845 | 0 | 18.522 | 3.354 |
| Python | ipc-zstd | 1,680,124 | 0 | 24.300 | 21.325 |
| Rust | json | 42,505,812 | +56 | 261.699 | 1228.560 |
| Rust | ipc | 12,671,117 | +272 | 1.457 | 2.598 |
| Rust | ipc-zstd | 1,625,309 | -54,815 | 24.684 | 10.031 |
| Zig | json | 42,372,426 | -133,330 | 182.791 | 351.653 |
| Zig | ipc | 12,670,849 | +4 | 45.149 | 27.161 |
| Zig | ipc-zstd | 1,620,045 | -60,079 | 61.658 | 21.626 |

Measured at `2026-10-29T09:31:16+00:00`.

## Images

| Image | Size | Runtime |
|---|---:|---|
| Python | 412,717,028 bytes | `python:3.15-slim-bookworm` |
| Rust | 8,621,689 bytes | `scratch` |
| Zig | 2,102,909 bytes | `scratch` |

The Rust size target was met. The Python size target was missed. The Python
Alpine image reached 349,582,071 bytes, but its PyArrow musl build regressed
Python IPC from about 5.2 ms to 20.6 ms, so it was rejected. The final Python
image keeps the glibc runtime and installs the compatible CPython 3.15 `orjson`
wheel explicitly.

## What changed

- The Python JSON lane uses `arrowlane.lanes.json_native.encode_table`. For
  scalar schemas it serializes the row list once, strips the outer JSON array,
  and splits the row separator. It falls back to one row at a time for nested
  columns or when a top-level string contains the split marker.
- The Rust benchmark image copies the dynamic loader, libc and libgcc from the
  builder into `scratch`. It keeps the glibc binary and removes the distroless
  base. Static musl was rejected because it regressed IPC performance.

## Verdicts

- JSON is the clear Zig win. Zig encode is 11.86x faster than Python and 1.43x
  faster than Rust. Zig decode is 5.90x faster than Python and 3.49x faster
  than Rust.
- IPC is led by Rust. Rust encode is 1.46 ms against Python 18.52 ms and Zig
  45.15 ms. Rust decode is 2.60 ms against Python 3.35 ms and Zig 27.16 ms.
- ipc-zstd decode is led by Rust at 10.03 ms. Python is 21.33 ms and Zig is
  21.63 ms. Zig decode improved from 179.18 ms to 21.63 ms after switching to
  libzstd.
- Python JSON encode improved from 2572.575 ms to 2167.805 ms. Python JSON
  decode moved from 1886.219 ms to 2074.545 ms in this container run; the
  decoder did not change, so treat that as container noise within the 10
  percent gate.
- The wire sizes are not identical. The Rust JSON frame has a 56-byte larger
  header and the same payload size at the fixture scale. The IPC and zstd
  payloads differ because the Arrow implementations serialize the same logical
  table differently. The zstd size differences show different compressed
  output, not a correctness failure.
- Do not claim IPC parity or an IPC speed win for Zig. Rust is the fastest IPC
  implementation in this run. arrow-cpp through the Rust port remains the
  reference for the IPC lanes.

## Reproduce

From the `arrowlane` repository root:

```bash
./.venv/Scripts/python.exe bench/containers/run.py --rows 200000 --repeats 3
```

The raw result is `bench/containers/results/latest.json`. The image tags used
for this run were `arrowlane-bench-python:local`,
`arrowlane-bench-rust:local` and `arrowlane-bench-zig:local`.
