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

pack_chunks(table, *, lane, token=None, directory=None, level=None,
            rows_per_chunk=50_000,
            max_payload=MAX_PAYLOAD_BYTES) -> Iterator[bytes]

unpack_chunks(frames, *, token=None, directory=None,
              max_payload=MAX_PAYLOAD_BYTES,
              max_uncompressed=MAX_UNCOMPRESSED_BYTES) -> Iterator[pa.RecordBatch]

assemble_chunks(frames, *, token=None, directory=None,
                max_payload=MAX_PAYLOAD_BYTES,
                max_uncompressed=MAX_UNCOMPRESSED_BYTES) -> pa.Table

transit_chunks(obj, *, topology="same_network", policy="latency", model=None,
               allowed=None, token=None, directory=None, level=None,
               rows_per_chunk=50_000,
               max_payload=MAX_PAYLOAD_BYTES) -> tuple[Iterator[bytes], Decision]

write_chunks(stream, table, *, lane, token=None, directory=None, level=None,
             rows_per_chunk=50_000,
             max_payload=MAX_PAYLOAD_BYTES) -> tuple[int, int]

read_chunks(stream, *, token=None, directory=None,
            max_payload=MAX_PAYLOAD_BYTES,
            max_uncompressed=MAX_UNCOMPRESSED_BYTES) -> Iterator[pa.RecordBatch]

write_frame(stream, frame, *, max_payload=MAX_PAYLOAD_BYTES) -> int

read_frame(stream, *, max_payload=MAX_PAYLOAD_BYTES,
           max_uncompressed=MAX_UNCOMPRESSED_BYTES) -> Frame | None
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

## Chunk metadata

| Field | Meaning |
|---|---|
| `id` | 32 lowercase hex characters, one per stream |
| `index` | Zero based position, contiguous from 0 |
| `last` | True on the final chunk |

## Large tables

`pack_chunks` yields one complete frame per chunk. The producer is lazy: it
encodes chunk n+1 only when the consumer asks. A blocking write or a bounded
queue therefore applies backpressure. One chunk is in flight.

- All chunks use one lane and one stream id.
- A chunk over `max_payload` is split in half until it fits.
- Each chunk has its own CRC and schema.
- `unpack_chunks` rejects a gap, a duplicate, a mixed id, a chunk after the
  last chunk, and a stream that ends before the last chunk.
- `unpack_chunks` yields one batch per chunk for streaming consumers.
  `assemble_chunks` buffers all batches and returns one table.
- `write_chunks` and `read_chunks` use `write_frame` and `read_frame`, so the
  payload is never joined into one buffer.
- For the `shm` lane, every chunk is a separate segment. Call `sweep` to remove
  segments left by an abandoned stream.

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
| `ChunkError` | A chunk stream is malformed, incomplete or out of order |
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
| Chunk rows | 1 to 10,000,000 |
| Chunks per stream | 1,000,000 |

## Semantics

- `transit` never plans `shm` without a token.
- `unpack` applies both caps before the lane decodes.
- `pack` and `unpack` are symmetric. The frame carries its lane id and schema.
- The CRC32 detects corruption. It is not a MAC. Use TLS off host.
- The selector falls back to `json` when the predicted gain is below 10 percent.
- `pack_chunks` is lazy. The next chunk is encoded only on `next()`.
- `read_frame` returns `None` at a clean end of stream.

## CLI

```bash
arrowlane select --rows 200000 --bytes 13380000 --topology same_network --json
arrowlane describe --indent 0
```

`select` exits 0 for any decision. `describe` exits 0. A config or usage error
exits 2 and prints one `error:` line to stderr.
