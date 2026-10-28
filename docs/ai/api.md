# API reference

## Functions

```text
plan(table, *, topology, policy="latency", model=None, allowed=None,
     shm=None, min_gain=0.10) -> Decision

pack(table, *, lane, token=None, directory=None, level=None,
     max_payload=MAX_PAYLOAD_BYTES) -> bytes

unpack(data, *, token=None, directory=None,
       max_payload=MAX_PAYLOAD_BYTES,
       max_uncompressed=MAX_UNCOMPRESSED_BYTES) -> pa.Table

transit(obj, *, topology="same_network", policy="latency", model=None,
        allowed=None, token=None, directory=None,
        level=None) -> tuple[bytes, Decision]
```

`obj` is any table-like object that `to_table` accepts: a `pyarrow.Table`, a
`RecordBatch`, a dict of columns, a list of rows, a pandas frame, a polars frame
or an object with `__arrow_c_stream__`.

## Decision

| Field | Meaning |
|---|---|
| `lane` | Chosen lane name |
| `reason` | `BEST`, `GAIN_TOO_SMALL`, `EMPTY`, `NON_TABULAR`, `NO_CANDIDATE` |
| `predicted_ms` | Predicted end to end milliseconds |
| `predicted_bytes` | Predicted wire bytes |
| `scores` | Tuple of `(lane, milliseconds)` |
| `rejected` | Tuple of `(lane, reason)` |

## Errors

All errors derive from `arrowlane.errors.ArrowLaneError`.

| Error | Raised when |
|---|---|
| `ConfigError` | The cost model is missing or invalid |
| `FrameError` | The frame cannot be trusted or decoded |
| `BadMagic` | The frame does not start with `ALN1` |
| `UnsupportedVersion` | The frame version is not 1 |
| `TruncatedFrame` | The declared length does not match the bytes |
| `OversizeFrame` | A length exceeds a cap |
| `ChecksumMismatch` | The payload CRC does not match |
| `UnknownLane` | The lane id or name is not registered |
| `BadHeader` | The header is not JSON or carries no schema |
| `LaneUnavailable` | The lane cannot run here, or the shm token is missing |
| `SegmentError` | A segment is missing, malformed or the wrong size |
| `SegmentGone` | The segment was already consumed |
| `AuthError` | The segment token does not match |
| `LimitExceeded` | A runtime limit was hit |
| `UpstreamError` | An upstream application failed |

## Lanes and limits

| Lane | Id | Requires | Media type |
|---|---|---|---|
| `json` | 1 | any | `application/x-ndjson` |
| `ipc` | 2 | any | `application/vnd.apache.arrow.stream` |
| `ipc-zstd` | 3 | any | `application/vnd.apache.arrow.stream` |
| `shm` | 4 | posix | `application/vnd.arrowlane.shm` |

| Limit | Bytes |
|---|---|
| Header | 65,535 |
| Payload | 536,870,912 |
| Uncompressed | 1,073,741,824 |
| Segment | 536,870,912 |

## Semantics

- `transit` never plans `shm` without a token.
- `unpack` applies both caps before the lane decodes.
- `pack` and `unpack` are symmetric. The frame carries its lane id and schema.
- The CRC32 detects corruption. It is not a MAC. Use TLS off host.
- The selector falls back to `json` when the predicted gain is below 10 percent.

## CLI

```bash
arrowlane select --rows 200000 --bytes 13380000 --topology same_network --json
arrowlane describe --indent 0
```

`select` exits 0 for any decision. `describe` exits 0. A config or usage error
exits 2 and prints one `error:` line to stderr.
