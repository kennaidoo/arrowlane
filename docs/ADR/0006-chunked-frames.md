# ADR 0006: chunked frames and backpressure

Status: accepted.

## Context

A whole frame holds the encoded payload and the joined frame at once. At
calibration time, the JSON lane peaked at 277.72 MB of Python allocation for a
500,000 row table whose wire size was 34.96 MB. The IPC lane peaked at 26.13 MB
for a 13.06 MB wire. A single frame also has a 512 MiB payload cap, so a large
table cannot always use the simple path.

## Decision

A large table travels as an ordered stream of chunks. Each chunk is a complete
frame. The frame header carries a `chunk` object with three fields:

| Field | Meaning |
|---|---|
| `id` | 32 lowercase hex characters, one per stream |
| `index` | Zero based position, contiguous from 0 |
| `last` | True on the final chunk |

The producer is a lazy iterator. It encodes chunk n+1 only when the consumer
asks for it. A blocking socket write or a bounded queue therefore applies
backpressure to the producer. One chunk is in flight.

One lane serves the whole stream. A chunk that exceeds `max_payload` is split in
half until it fits. The split is bounded by the row count: a single row that
cannot fit raises `OversizeFrame`.

The consumer validates one stream id, contiguous indexes, and exactly one last
chunk. It rejects a gap, a duplicate, a mixed id, a chunk after the last chunk,
and a stream that ends before the last chunk.

`write_frame` writes the prefix, header and payload in order, so a file or socket
path never joins the payload into one buffer. `read_frame` reads the same parts
and returns `None` at a clean end of stream.

## Consequences

- Peak allocation follows the chunk size, not the table size. Measured with
  25,000 row chunks: JSON 17.43 MB, IPC 1.97 MB, ipc-zstd 1.95 MB.
- The receiver pays one of two costs. `unpack_chunks` yields batches and keeps
  chunk sized memory. `assemble_chunks` buffers every batch and returns one
  table, so its memory follows the table.
- A chunk stream has no total count. `last` terminates it. This keeps the
  producer streaming when a chunk is split adaptively.
- `shm` creates one segment per chunk. An abandoned stream can leave segments;
  `sweep` removes them after the TTL.
- A mixed lane stream is not supported. The selector plans once for the whole
  table, so the receiver knows the lane before the first chunk.
