# Changelog

All notable changes to this project are recorded here. The format follows
Keep a Changelog, and the project uses semantic versioning.

## 0.1.0 - 2026-10-28

### Added

- Frame format with a 38 byte prefix, a JSON header and a CRC32 payload check.
- Lanes: typed NDJSON, Arrow IPC, Arrow IPC with zstd, and POSIX shared memory.
- Lane selector with a measured cost model and a JSON fallback for small gains.
- Command line interface: `arrowlane select`.
