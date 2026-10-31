# Platforms

arrowlane requires Python 3.14 or newer. The portable lanes run on Linux, macOS
and Windows. The `shm` lane is a POSIX shared memory accelerator and is not
available everywhere.

## Support matrix

| Host | Architecture | Python | Rust | Zig | Notes |
|---|---|---|---|---|---|
| Linux | x86_64 | Supported | Supported | Supported | Full `shm` lane |
| Linux | aarch64 | Supported | Supported | Supported | PyArrow `manylinux_2_28_aarch64` or `musllinux_1_2_aarch64` |
| macOS | arm64 Apple silicon | Supported | Supported | Supported | PyArrow `macosx_12_0_arm64`; `shm` needs `ARROWLAND_SHM_DIR` |
| Windows | x86_64 | Supported | Supported | Supported | `shm` unavailable |
| Windows | aarch64 | Unsupported | Build support | Build support | PyArrow has no `win_arm64` wheel |
| FreeBSD 15 | aarch64 | Unsupported | Supported | Supported | PyArrow port is 24.0.0 and Python 3.11 only |

Python support follows the PyArrow wheel matrix. The package cannot claim Windows ARM64 or FreeBSD ARM64 support while PyArrow does not publish a compatible wheel for those targets. The Rust and Zig ports do not depend on PyArrow and can be built on those targets.

The support matrix is verified by the test suite. Linux runs the full suite with
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

Python 3.15 on glibc Linux needs glibc 2.39 or newer. The CPython 3.15
`orjson` wheels are manylinux 2.39. Debian bookworm has glibc 2.36 and must
use Debian trixie or newer, or build `orjson` from source. Python 3.14 has
older manylinux wheels and does not have this floor.

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

The package depends on pyarrow wheels. Wheels are published for x86_64 Linux,
x86_64 Windows and macOS arm64. Other architectures work only when pyarrow
publishes a compatible wheel for them.

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

## The checksum on arm64

`frame.py` computes the frame checksum with `zlib.crc32`. On aarch64 the C library
maps that call onto the CRC32 instructions, so the checksum already runs at
hardware speed on Graviton and on Apple silicon, with no code in this package.

The C++ port cannot call the C library, so it carries its own kernels and needed
a separate ARMv8 path to reach the same place. That is a fact about the port, not
about this package. Do not port those kernels here.
