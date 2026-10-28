# Operating guide for agents

Read this first. It is the shortest path to a correct change in this repository.

## What this is

arrowlane moves a `pyarrow.Table` between processes as one validated frame. The
lanes are `json`, `ipc`, `ipc-zstd` and POSIX `shm`. Python 3.14 or newer.

## One command

```bash
bash scripts/gate.sh
```

It runs ruff, format, mypy, pytest, the benchmark gate and pip-audit, and prints
one `CHECK` line per step. A change is done only when it prints `RESULT: PASS`.

## Setup

```bash
uv venv --python 3.15
uv pip install -e ".[dev,server]"
```

## Map

| Path | What |
|---|---|
| `src/arrowlane/frame.py` | Wire frame, caps, CRC, schema, frame streams |
| `src/arrowlane/chunks.py` | Chunked frames, lazy producer, ordered consumer |
| `src/arrowlane/transit.py` | `plan`, `pack`, `unpack`, `transit` |
| `src/arrowlane/lanes/` | One module per physical lane |
| `src/arrowlane/select.py` | Lane choice from the cost model |
| `src/arrowlane/costmodel.json` | Measured coefficients and provenance |
| `src/arrowlane/shm.py` | Segments, descriptors, sweep |
| `src/arrowlane/describe.py` | Machine-readable manifest |
| `tests/` | One file per module, plus fuzz and repo hygiene |
| `bench/` | Probe, calibration, gate |
| `demo/` | Compose stack with app, client and console |
| `docs/ADR/` | Design decisions |

## Invariants

- Check every length cap before allocating.
- Check the CRC before copying the payload.
- Compare the header schema with the payload schema.
- A chunk stream keeps one id, contiguous indexes and exactly one last chunk.
- `pack_chunks` is lazy. One chunk is in flight.
- Never plan the `shm` lane without a token.
- Never print from `src` except `cli.py`.
- Never renumber a lane id. Add a new id.
- Keep the header at or below 65,535 bytes.
- No em dash in any file.

## Common tasks

### Add a lane

1. Add a `LaneInfo` with a new unused id in `src/arrowlane/lanes/`.
2. Implement `encode` and `decode`, and register the lane in `lanes/__init__.py`.
3. Add a roundtrip test and a negative test in `tests/`.
4. Add the lane id to `frame.LANE_IDS`.
5. Run `bash scripts/gate.sh`.

### Change the frame

1. Bump `frame.VERSION`.
2. Update `docs/ADR/0001-frame-format.md`.
3. Add a decode test for the old and the new version.
4. Run `bash scripts/gate.sh`.

### Recalibrate the cost model

```bash
python bench/probes/codec_probe.py
python bench/calibrate.py --write
python bench/verify.py
```

Commit the model, `bench/baseline.json` and any test changes together.

## Agent surface

- `arrowlane describe --indent 0` prints the capability manifest.
- `docs/ai/manifest.json` is generated from `describe()` and tested for equality.
- `docs/ai/quickstart.md`, `docs/ai/api.md` and `docs/ai/recipes.md` are the
  integration references. Their Python blocks are compiled by the test suite.
- `pack_chunks` and `read_chunks` are the large table path. `write_chunks` and
  `read_chunks` avoid the join copy for binary streams.
- `docs/platforms.md` lists the tested matrix and lane availability.
- `llms.txt` lists the same entry points for retrieval tools.

## Watermarks

- Every frame header carries `producer: arrowlane/<version>`.
- The manifest carries `package_version` and `schema_version`.
- The console page carries `<meta name="generator" content="arrowlane">`.
- The AI docs ship inside the wheel under `arrowlane/ai/`.

## Definition of done

1. `bash scripts/gate.sh` prints `RESULT: PASS`.
2. The change has a test, or the pull request states the waiver and the reason.
3. Docs change with the behaviour they describe.
4. The commit message is `type(scope): description`.
