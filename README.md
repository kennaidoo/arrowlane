# arrowlane

Columnar data lanes for ingress and egress in containerized Python apps.

Status: Alpha. The API may change. Python 3.14 or newer.

Test coverage is enforced on Linux, where the POSIX shared memory lanes run.

## Quick start

```python
import pyarrow as pa

import arrowlane

table = pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]})
wire, decision = arrowlane.transit(table, topology="same_network")
rows = arrowlane.unpack(wire).num_rows
print(decision.lane, len(wire), rows)
```

## What it does

arrowlane moves a `pyarrow.Table` between processes as one frame. It chooses a
physical lane, encodes the table, validates the frame on arrival, and returns a
table whose buffers are safe to read. The frame carries its lane id, row count,
uncompressed length, CRC32 and Arrow schema, so a reader needs no side channel.

## Lanes

| Lane | Media type | Availability | Cost shape | Does not do |
|---|---|---|---|---|
| `json` | `application/x-ndjson` | Every platform | Slowest per megabyte, simplest to inspect | Carry values without tags |
| `ipc` | `application/vnd.apache.arrow.stream` | Every platform | Fast, no compression | Reduce wire bytes |
| `ipc-zstd` | `application/vnd.apache.arrow.stream` | Every platform | Small wire, about 8 ms fixed decode cost | Help tiny payloads |
| `shm` | `application/vnd.arrowlane.shm` | POSIX only | Descriptor on the wire, payload in a segment | Work across containers without a shared `/dev/shm` mount |

## API

| Call | Purpose |
|---|---|
| `plan(table, topology=...)` | Choose a lane and return the scores |
| `pack(table, lane=...)` | Encode one table on one lane |
| `unpack(data, token=...)` | Validate and decode a frame |
| `transit(table, topology=...)` | Plan, pack and return the decision |

`transit` never plans the `shm` lane without a token, because it cannot open a
segment it did not create.

## Measured model

The shipped coefficients were measured on benchmark-host, Windows 11, Python
3.15.1 and pyarrow 26.0.0, on four shapes from 1,000 to 500,000 rows and eight
column types, median of three runs.

| Lane | Fixed ms | Encode ms/MB | Decode ms/MB | Wire ratio |
|---|---|---|---|---|
| `json` | 0.002 | 197.33 | 152.26 | 2.616 |
| `ipc` | 0.060 | 0.301 | 0.002 | 1.000 |
| `ipc-zstd` | 8.095 | 2.250 | 1.281 | 0.312 |

The fixed terms are a floor: the larger of the fitted intercept and the earlier
seed estimate. The network terms are estimates, not measurements. The model
predicts the largest shape within 0.5 percent and the middle shapes within 69
percent, because the JSON cost changes with cache residency. The selector falls
back to JSON when the predicted gain is under 10 percent. `bench/calibrate.py`
records every residual in the model provenance.

Recalibrate on a new host:

```bash
python bench/probes/codec_probe.py
python bench/calibrate.py --write
python bench/verify.py
```

## Demo

```bash
cd demo
docker compose up -d --build app console
```

Open `http://127.0.0.1:8081` for the console. Measure every lane:

```bash
docker compose run --rm client
```

Prove the whole stack, including a negative result on failure:

```bash
bash verify.sh
```

The demo binds to loopback only. The app and the console run read-only, without
capabilities, as non-root users. The client writes the shared results volume
through a one-shot `chown` init container.

## Security posture

- CRC32 detects truncation and bit flips. It is not a MAC. Terminate TLS in
  front of any off-host use.
- A shared memory token is defense in depth. It is not a boundary between
  processes that share a uid.
- Segments use mode 0600, an unguessable name, and are unlinked after attach.
- Every length is checked against a cap before allocation. Every lane honours
  the caller's `max_uncompressed`.

## Platform support

The portable lanes run on Linux, macOS and Windows. The `shm` lane needs POSIX.
Coverage is enforced on Linux, where the shared memory tests run.

## Status

Alpha. The API may change.
