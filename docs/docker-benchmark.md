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
| Python | json | 42,505,756 | 0 | 2572.575 | 1886.219 |
| Python | ipc | 12,670,845 | 0 | 5.166 | 3.917 |
| Python | ipc-zstd | 1,680,124 | 0 | 24.078 | 15.165 |
| Rust | json | 42,505,812 | +56 | 212.330 | 1047.205 |
| Rust | ipc | 12,671,117 | +272 | 1.393 | 2.409 |
| Rust | ipc-zstd | 1,625,309 | -54,815 | 25.095 | 10.273 |
| Zig | json | 42,372,426 | -133,330 | 172.880 | 311.182 |
| Zig | ipc | 12,670,849 | +4 | 41.087 | 24.640 |
| Zig | ipc-zstd | 1,620,045 | -60,079 | 55.157 | 19.526 |

Measured at `2026-10-29T08:41:33+00:00`.

## Images

| Image | Size | Runtime |
|---|---:|---|
| Python | 412,695,390 bytes | `python:3.15-slim-bookworm` |
| Rust | 42,430,357 bytes | `gcr.io/distroless/cc-debian12` |
| Zig | 2,102,909 bytes | `scratch` |

The Python and Rust size targets were missed. The Python Alpine image reached
349,582,071 bytes, but its PyArrow musl build regressed Python IPC from about
5.2 ms to 20.6 ms, so it was rejected. The final Python image therefore keeps
the glibc runtime and installs the compatible CPython 3.15 `orjson` wheel
explicitly. The Rust static musl image was also rejected after IPC decode
regressed from about 2.4 ms to 13.8 ms. The final Rust image uses a dynamic
glibc binary in distroless and keeps the speed.

## Verdicts

- JSON is the clear Zig win. Zig encode is 14.88x faster than Python and 1.23x
  faster than Rust. Zig decode is 6.06x faster than Python and 3.37x faster
  than Rust.
- IPC is led by Rust. Rust encode is 1.39 ms against Python 5.17 ms and Zig
  41.09 ms. Rust decode is 2.41 ms against Python 3.92 ms and Zig 24.64 ms.
- ipc-zstd decode is led by Rust at 10.27 ms. Python is 15.17 ms and Zig is
  19.53 ms. Zig decode improved from 179.18 ms to 19.53 ms after switching to
  libzstd. Zig is now 1.29x slower than Python, not 11.2x.
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
