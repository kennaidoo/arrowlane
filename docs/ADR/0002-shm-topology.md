# ADR 0002: where the shared memory lane is honest

Status: accepted.

## Context

The `shm` lane writes the Arrow IPC payload to a file under a shared directory
and puts only a descriptor on the wire. POSIX allows unlink while a mapping is
open. Windows does not, so the lane refuses to run there.

A container has its own `/dev/shm`. Two containers do not share it unless the
deployment mounts the same memory backed volume and shares the IPC namespace.
A Docker named volume is page cache, not shared memory.

## Decision

- The lane is POSIX only. Readiness requires `/dev/shm` or an explicit
  `ARROWLAND_SHM_DIR`. The temporary directory fallback is never reported as
  ready.
- The demo measures the lane between two processes in one container and labels
  the topology `same_container`.
- A segment is mode 0600, has an unguessable name, is unlinked after attach, and
  can be released if the frame is never sent.
- The token is defense in depth. It is not a uid boundary.

## Consequences

Cross-container use needs a shared `/dev/shm` mount plus a shared IPC namespace.
That is a deployment constraint, not a default. The selector only chooses the
lane when a token is present and readiness is true.
