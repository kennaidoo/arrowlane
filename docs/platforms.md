# Platforms

arrowlane requires Python 3.14 or newer. The portable lanes run on Linux, macOS
and Windows. The `shm` lane is a POSIX shared memory accelerator and is not
available everywhere.

## Tested matrix

| Python | Linux | macOS | Windows |
|---|---|---|---|
| 3.14 | CI, unit tests | not run | not run |
| 3.15 | CI, coverage, benchmark | CI, unit tests | CI, unit tests |

The CI matrix is in `.github/workflows/ci.yml`. Linux runs the full suite with
coverage and the benchmark gate. macOS and Windows run the portable suite. The
`shm` read tests run on Linux only.

## Lanes by platform

| Lane | Linux | macOS | Windows | Notes |
|---|---|---|---|---|
| `json` | yes | yes | yes | Portable |
| `ipc` | yes | yes | yes | Portable |
| `ipc-zstd` | yes | yes | yes | `compression.zstd`, Python 3.14 or newer |
| `shm` | yes | conditional | no | POSIX only; see below |

### Linux

`/dev/shm` is used by default. The lane is ready when the directory exists and
is writable.

### macOS

macOS has POSIX shared memory but no `/dev/shm`. Set `ARROWLAND_SHM_DIR` to a
memory backed directory to enable the lane. A disk backed directory is a file
lane, not shared memory. `available_names()` omits `shm` until the directory is
configured and ready.

### Windows

The `shm` lane is not available. Windows cannot unlink a file name while a
mapping is open, which the zero copy read path requires. `available_names()`
omits the lane. The portable lanes work.

## Architectures

The package depends on pyarrow wheels. CI covers x86_64 Linux, x86_64 Windows
and the macOS runner image that GitHub provides. Other architectures work only
when pyarrow publishes a wheel for them.

## How to check the live platform

```bash
arrowlane describe --indent 0
python -c "from arrowlane.lanes import available_names; print(available_names())"
```

`describe()` lists every registered lane and its requirement. `available_names()`
lists the lanes that this host can serve now.

## Limits

The Python floor is 3.14 because the package uses `compression.zstd` and
`uuid.uuid7()` from the standard library. Lowering the floor would add a zstd
dependency and a UUIDv7 shim. That is a separate decision.
