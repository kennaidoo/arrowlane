# Docker benchmark

Three implementations, one canonical eight-column fixture, 200,000 rows. Each
value is the median of five measured runs after one warmup run. The benchmark
ran in Linux x86_64 containers on Docker 29.9.2. Each container had 2 CPUs and
2 GiB of memory, no network access and a read-only root filesystem.

This is a container measurement. It is separate from the host measurements in
`arrowlane-zig/docs/performance.md`.

## Results

| Implementation | Lane | Wire bytes | Wire delta vs Python | Encode ms | Decode ms |
|---|---|---:|---:|---:|---:|
| Python | json | 42,505,756 | 0 | 2128.138 | 2062.808 |
| Python | ipc | 12,670,845 | 0 | 20.367 | 3.593 |
| Python | ipc-zstd | 1,620,041 | 0 | 28.866 | 19.947 |
| Rust | json | 42,505,812 | +56 | 285.456 | 1240.968 |
| Rust | ipc | 12,671,117 | +272 | 1.867 | 3.010 |
| Rust | ipc-zstd | 1,625,309 | +5,268 | 28.816 | 11.124 |
| Zig | json | 42,372,426 | -133,330 | 181.983 | 328.907 |
| Zig | ipc | 12,670,849 | +4 | 44.976 | 25.996 |
| Zig | ipc-zstd | 1,620,045 | +4 | 60.151 | 21.330 |

Measured at `2026-10-29T11:53:24+00:00`.

## Images

| Image | Size | Runtime |
|---|---:|---|
| Python | 408,275,466 bytes | `python:3.15-slim-trixie` |
| Rust | 8,621,689 bytes | `scratch` |
| Zig | 2,102,909 bytes | `scratch` |

The Rust size target was met. The Python size target was missed. The Python
Alpine image reached 349,582,071 bytes, but its PyArrow musl build regressed
Python IPC from about 5.2 ms to 20.6 ms, so it was rejected. The final Python
images use Debian trixie, whose glibc accepts the CPython 3.15 `orjson` wheel
through normal pip resolution.

The Python 3.15 trixie image raises `ipc-zstd` encode to 28.866 ms. A bookworm
control with the same pyarrow and orjson versions measured 27.070 and 28.807 ms
on this host. The previous 24.300 ms baseline is not reproducible. Retire the
old 10 percent gate for this lane and treat the five-repeat record as the new
baseline.

## What changed

- The Python JSON lane uses `arrowlane.lanes.json_native.encode_table`. For
  scalar schemas it serializes the row list once, strips the outer JSON array,
  and splits the row separator. It falls back to one row at a time for nested
  columns or when a top-level string contains the split marker.
- The Rust benchmark image copies the dynamic loader, libc and libgcc from the
  builder into `scratch`. It keeps the glibc binary and removes the distroless
  base. Static musl was rejected because it regressed IPC performance.
- The Python 3.15 images use `python:3.15-slim-trixie`. Normal pip resolution
  installs the CPython 3.15 manylinux 2.39 `orjson` wheel. The benchmark, demo
  app and demo client images use this base.

## Verdicts

- JSON is the clear Zig win. Zig encode is 11.69x faster than Python and 1.57x
  faster than Rust. Zig decode is 6.27x faster than Python and 3.77x faster
  than Rust.
- IPC is led by Rust. Rust encode is 1.87 ms against Python 20.37 ms and Zig
  44.98 ms. Rust decode is 3.01 ms against Python 3.59 ms and Zig 26.00 ms.
- ipc-zstd decode is led by Rust at 11.12 ms. Python is 19.95 ms and Zig is
  21.33 ms.
- Python JSON encode is 2128.138 ms. Python ipc-zstd encode is 28.866 ms; the
  bookworm control measured 27.070 and 28.807 ms, so the old 24.300 ms
  baseline is not a stable target.
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
./.venv/Scripts/python.exe bench/containers/run.py --rows 200000 --repeats 5
```

The raw result is `bench/containers/results/latest.json`. The image tags used
for this run were `arrowlane-bench-python:local`,
`arrowlane-bench-rust:local` and `arrowlane-bench-zig:local`.
