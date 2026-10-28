# ADR 0005: the data plane language

Status: accepted.

## Context

The measured model separates the lanes:

| Lane | Encode ms/MB | Decode ms/MB |
|---|---|---|
| json | 197.33 | 152.26 |
| ipc | 0.301 | 0.002 |
| ipc-zstd | 2.250 | 1.281 |

The JSON lane is CPython bound. It converts every row to Python objects and
calls `json.dumps` per row. The IPC lanes are already near the pyarrow buffer
floor.

## Decision

Do not port the data plane to a systems language now. A Zig or Rust JSON encoder
would improve the compatibility baseline, not the fast path. Profile before any
port, and treat a JSON encoder as a separate measured project.

## Consequences

The JSON lane remains the slow baseline and the fallback for small gains. A port
would need its own benchmark and would not change the frame format.
