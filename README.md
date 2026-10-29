# arrowlane

Move PyArrow tables between processes as validated frames, with automatic lane
selection and lazy chunk streams.

> Status: Alpha source preview. No release artifacts yet. The API may change.
> Python 3.14 or newer.

Coverage is enforced on Linux, where the POSIX shared-memory tests run.

## Why arrowlane

- One frame carries its lane id, row count, uncompressed length, CRC32 and Arrow schema.
- `transit` chooses JSON, IPC, IPC with zstd, or POSIX shared memory from table shape and topology.
- Chunk streams keep one chunk in flight, so a slow reader applies backpressure.
- The frame is readable by the Rust implementation of the same format.

## Quick start

```python
import pyarrow as pa

import arrowlane

table = pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]})
wire, decision = arrowlane.transit(table, topology="same_network")
rows = arrowlane.unpack(wire).num_rows
print(decision.lane, len(wire), rows)
```

## Install

There is no PyPI release yet. Use a source checkout:

```bash
git clone https://github.com/kennaidoo/arrowlane.git
cd arrowlane
uv sync --frozen --extra dev --extra server
```

## Lanes

| Lane | Media type | Availability | Tradeoff |
|---|---|---|---|
| `json` | `application/x-ndjson` | Every platform | Easiest to inspect, largest and slowest |
| `ipc` | `application/vnd.apache.arrow.stream` | Every platform | Fast, no compression |
| `ipc-zstd` | `application/vnd.apache.arrow.stream` | Every platform | Small wire, fixed decode cost |
| `shm` | `application/vnd.arrowlane.shm` | POSIX only | Descriptor on the wire, payload in a segment |

`transit` never chooses `shm` without a token.

## Large tables

Use `transit_chunks`, `pack_chunks`, `write_chunks` or `read_chunks` for tables
that should not be encoded as one buffer. A chunk is a complete frame with
`id`, `index` and `last` metadata.

The integration patterns are in [docs/ai/recipes.md](docs/ai/recipes.md).

## Limits

- This is a transport frame, not a server. It is not a replacement for Arrow Flight or an RPC framework.
- CRC32 detects truncation and bit flips. It is not a MAC.
- The `shm` lane is POSIX only. macOS needs `ARROWLAND_SHM_DIR` pointing at a memory-backed directory.
- Python 3.15 on glibc Linux needs glibc 2.39 or newer for the `orjson` wheel.
- Windows ARM64 and FreeBSD ARM64 are not supported by the Python package because PyArrow has no compatible wheel.

## Platforms

Linux x86_64, Linux aarch64, macOS arm64 and Windows x86_64 are supported. The
full matrix and live check commands are in [docs/platforms.md](docs/platforms.md).

## Performance

The maintained cross-language record is
[docs/docker-benchmark.md](docs/docker-benchmark.md). Run `python bench/verify.py`
locally before quoting a performance claim.

## Documentation

- [docs/ai/quickstart.md](docs/ai/quickstart.md): install and first call.
- [docs/ai/api.md](docs/ai/api.md): signatures, return shapes and errors.
- [docs/ai/operating-guide.md](docs/ai/operating-guide.md): development rules and invariants.
- [docs/platforms.md](docs/platforms.md): platform and lane matrix.
- [docs/docker-benchmark.md](docs/docker-benchmark.md): current cross-language benchmark.
- [docs/ADR](docs/ADR): design decisions.
- [llms.txt](llms.txt): short entry point for retrieval tools.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) for the process and [AGENTS.md](AGENTS.md)
for the coding-agent commands.

## Security

Report vulnerabilities privately through the repository Security tab. Do not
open a public issue. See [SECURITY.md](SECURITY.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).
