# Changelog

All notable changes to this project are recorded here. The format follows
Keep a Changelog, and the project uses semantic versioning.

## Unreleased

### Added

- Containerized three-way benchmark for Python, Rust and Zig on the canonical
  eight-column fixture at 200,000 rows.
- Docker images, Compose services and a result driver under
  `bench/containers/`.

### Changed

- The JSON lane uses a column-oriented encoder. Scalar tables serialize once
  and split into NDJSON. Nested columns and strings containing the split
  marker use the row fallback.
- The benchmark Python image uses a glibc runtime and an explicit compatible
  `orjson` wheel. The Alpine image was rejected because PyArrow on musl made
  the IPC lanes much slower.

## 0.3.1 - 2026-10-29

### Changed

- Relaxed `SECURITY.md` response targets to 30-day acknowledgement and 120-day
  fix or documented decision, marked as best-effort targets rather than an SLA.

## 0.3.0 - 2026-10-28

### Added

- Chunked frames with `id`, `index` and `last` metadata.
- `pack_chunks`, `unpack_chunks`, `assemble_chunks` and `transit_chunks`.
- `write_chunks` and `read_chunks` for binary streams.
- `write_frame` and `read_frame` for frame streams without a join copy.
- `ChunkInfo`, `ChunkError` and adaptive chunk splitting.
- `bench/memory_probe.py` and `docs/platforms.md`.

### Changed

- Large tables stream in bounded chunks. The producer encodes one chunk at a
  time, so peak allocation follows the chunk size, not the table size.

## 0.2.0 - 2026-10-28

### Added

- Public facade: `plan`, `pack`, `unpack` and `transit`.
- Container demo: ASGI service, load client, results console and compose stack.
- Benchmark harness: codec probe, calibration and a gate with a negative control.
- Architecture decision records.
- Fuzz tests for the frame and descriptor parsers.

### Changed

- The shipped cost model is measured, with every residual recorded in provenance.
- Starlette moved to the patched line with `httpx2`.
- The package is Alpha and declares Linux, macOS and Windows.

### Fixed

- Windows segment writes use binary mode.
- The frame CRC is checked before the payload is copied.
- The header cap matches the 16-bit wire field.
- Every lane honours `max_uncompressed`.
- The JSON lane rejects schema drift instead of null filling.
- The CLI returns a typed error contract.

## 0.1.0 - 2026-10-28

### Added

- Frame format with a 38 byte prefix, a JSON header and a CRC32 payload check.
- Lanes: typed NDJSON, Arrow IPC, Arrow IPC with zstd, and POSIX shared memory.
- Lane selector with a measured cost model and a JSON fallback for small gains.
- Command line interface: `arrowlane select`.
