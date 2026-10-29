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
| Python | json | 42,505,756 | 0 | 3111.630 | 2624.323 |
| Python | ipc | 12,670,845 | 0 | 5.283 | 3.331 |
| Python | ipc-zstd | 1,680,124 | 0 | 23.082 | 15.948 |
| Rust | json | 42,505,812 | +56 | 228.862 | 1034.057 |
| Rust | ipc | 12,671,117 | +272 | 1.812 | 2.613 |
| Rust | ipc-zstd | 1,625,309 | -54,815 | 24.052 | 10.075 |
| Zig | json | 42,372,426 | -133,330 | 173.382 | 323.423 |
| Zig | ipc | 12,670,849 | +4 | 43.122 | 24.621 |
| Zig | ipc-zstd | 1,620,045 | -60,079 | 55.257 | 179.177 |

Measured at `2026-10-29T08:04:13+00:00`.

## Verdicts

- JSON is the clear Zig win. Zig encode is 17.95x faster than Python and 1.32x
  faster than Rust. Zig decode is 8.11x faster than Python and 3.20x faster
  than Rust.
- IPC is led by Rust. Rust encode is 1.81 ms against Python 5.28 ms and Zig
  43.12 ms. Rust decode is 2.61 ms against Python 3.33 ms and Zig 24.62 ms.
  Zig is about 8.2x slower than Python on encode and 7.4x slower on decode.
- ipc-zstd decode is led by Rust at 10.08 ms. Python is 15.95 ms and Zig is
  179.18 ms. Zig decode is 11.2x slower than Python and 17.8x slower than
  Rust. Zig encode is also slower than both.
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
