# Container benchmark

This directory builds one Linux container per implementation and runs the same
canonical eight-column fixture through each one.

## Requirements

- Docker Desktop with the Linux engine running.
- Docker Compose v2.
- At least 2 CPUs and 2 GiB of memory available to Linux containers.

## Run

From the `arrowlane` repository root:

```bash
./.venv/Scripts/python.exe bench/containers/run.py --rows 200000 --repeats 3
```

The runner builds all three images, runs one warmup pass per implementation,
then runs three measured repetitions. It writes:

- `bench/containers/results/bench-<timestamp>.json`
- `bench/containers/results/latest.json`
- `bench/containers/results/latest.md`

## What the runner checks

- Every implementation prints one line per lane.
- Every line has the lane name, wire bytes, encode milliseconds and decode
  milliseconds.
- All three portable lanes are present.
- Wire size differences against Python are recorded, not treated as a failure.
  The frame headers carry different producer and schema encodings, and the IPC
  and zstd payloads are not byte-identical. Performance is measured separately
  from wire equality.

## Images

| Service | Image | Source |
|---|---|---|
| `python` | `arrowlane-bench-python:local` | `arrowlane` |
| `rust` | `arrowlane-bench-rust:local` | `arrowlane-rust` |
| `zig` | `arrowlane-bench-zig:local` | `arrowlane-zig` |

Each image runs as uid 65532 with a read-only root filesystem, no network and
all Linux capabilities dropped.

## Results

The committed result is in `docs/docker-benchmark.md`. It is a container
measurement on Linux x86_64. Do not compare it directly with the host
measurements in `docs/performance.md`.
