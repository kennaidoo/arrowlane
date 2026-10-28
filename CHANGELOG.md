# Changelog

All notable changes to this project are recorded here. The format follows
Keep a Changelog, and the project uses semantic versioning.

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
