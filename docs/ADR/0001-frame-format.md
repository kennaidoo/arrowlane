# ADR 0001: the wire frame

Status: accepted.

## Context

A frame must be readable by a process that has never seen the producer. A reader
must reject bad input before it trusts a length or allocates for a payload.

## Decision

The prefix is 38 bytes, little endian:

| Field | Size | Meaning |
|---|---|---|
| magic | 4 | `ALN1` |
| version | 1 | 1 |
| lane id | 1 | 1 json, 2 ipc, 3 ipc-zstd, 4 shm |
| flags | 2 | reserved, must be 0 |
| payload length | 8 | bytes on the wire |
| uncompressed length | 8 | bytes before compression |
| rows | 8 | row count |
| CRC32 | 4 | over the payload only |
| header length | 2 | 0 to 65535 |

The header is UTF-8 JSON and carries the base64 Arrow schema. The payload is
opaque to the frame layer.

Every length is checked against a cap before the payload is copied. The CRC is
checked before the copy. A bad frame yields one typed error and no partial table.
CRC32 is not a MAC; terminate TLS off host.

## Consequences

The header length field bounds the header at 65,535 bytes. The schema is
duplicated for IPC lanes, because the IPC stream also carries it; the decoder
checks that the two agree. `flags` is reserved for a future version and is not
read.
