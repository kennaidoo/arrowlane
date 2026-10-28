"""POSIX shared memory segments for the shm lane.

The descriptor is small and travels in the frame. The payload stays in a file
under a shared directory, usually /dev/shm or a memory backed volume. The
reader maps it, verifies the CRC, unlinks the name, and returns an Arrow buffer
that owns the mapping.

Linux and macOS allow unlink while a mapping is open. Windows does not, and
this module reports not ready there.
"""

from __future__ import annotations

import hmac
import json
import mmap
import os
import secrets
import tempfile
import time
import uuid
import zlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import pyarrow as pa

from .errors import AuthError, ChecksumMismatch, SegmentError, SegmentGone

NAME_PREFIX: Final = "al-"
DEFAULT_TTL_S: Final = 60.0
MAX_SEGMENT_BYTES: Final = 536_870_912
_DESCRIPTOR_KEYS: Final = {"name", "length", "crc32", "token", "offset"}


@dataclass(frozen=True, slots=True)
class Descriptor:
    """Where the payload is and how to prove it arrived intact."""

    name: str
    length: int
    crc32: int
    token: str
    offset: int = 0

    def to_bytes(self) -> bytes:
        """Serialise the descriptor for the frame payload."""
        payload = {
            "name": self.name,
            "length": self.length,
            "crc32": self.crc32,
            "token": self.token,
            "offset": self.offset,
        }
        return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    @classmethod
    def from_bytes(cls, raw: bytes) -> Descriptor:
        """Parse and validate a descriptor. Every field is untrusted."""
        try:
            data: Any = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SegmentError("descriptor is not UTF-8 JSON") from exc
        if not isinstance(data, dict):
            raise SegmentError("descriptor is not an object")
        if set(data) - _DESCRIPTOR_KEYS:
            raise SegmentError("descriptor has unknown keys")
        name = data.get("name")
        if not isinstance(name, str) or not name.startswith(NAME_PREFIX) or "/" in name:
            raise SegmentError("descriptor name is invalid")
        length = data.get("length")
        if (
            not isinstance(length, int)
            or isinstance(length, bool)
            or not 0 < length <= MAX_SEGMENT_BYTES
        ):
            raise SegmentError("descriptor length is invalid")
        offset = data.get("offset", 0)
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise SegmentError("descriptor offset is invalid")
        crc32 = data.get("crc32")
        if not isinstance(crc32, int) or isinstance(crc32, bool) or not 0 <= crc32 <= 0xFFFFFFFF:
            raise SegmentError("descriptor crc32 is invalid")
        token = data.get("token")
        if not isinstance(token, str) or len(token) < 16:
            raise SegmentError("descriptor token is invalid")
        return cls(name=name, length=length, crc32=crc32, token=token, offset=offset)


def segment_dir(env: Mapping[str, str] | None = None) -> Path:
    """Directory that holds the segments."""
    source = os.environ if env is None else env
    override = source.get("ARROWLAND_SHM_DIR")
    if override:
        return Path(override)
    if Path("/dev/shm").is_dir():  # noqa: S108 - the POSIX shared memory mount
        return Path("/dev/shm")  # noqa: S108 - the POSIX shared memory mount
    return Path(tempfile.gettempdir())


def is_ready(directory: Path | None = None) -> bool:
    """True when this platform and directory can serve the shm lane."""
    if os.name != "posix":
        return False
    target = directory or segment_dir()
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / f"{NAME_PREFIX}probe-{uuid.uuid4().hex}"
        probe.write_bytes(b"x")
        probe.unlink()
        return True
    except OSError:
        return False


def write_segment(
    data: bytes,
    *,
    directory: Path | None = None,
    token: str | None = None,
) -> Descriptor:
    """Write data to a new segment with mode 0600 and return its descriptor."""
    if not data:
        raise SegmentError("refusing to write an empty segment")
    if len(data) > MAX_SEGMENT_BYTES:
        raise SegmentError(f"segment {len(data)} exceeds {MAX_SEGMENT_BYTES}")
    target = directory or segment_dir()
    target.mkdir(parents=True, exist_ok=True)
    name = f"{NAME_PREFIX}{uuid.uuid7().hex}"
    path = target / name
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
    try:
        view = memoryview(data)
        written = 0
        while written < len(view):
            written += os.write(fd, view[written:])
    finally:
        os.close(fd)
    return Descriptor(
        name=name,
        length=len(data),
        crc32=zlib.crc32(data) & 0xFFFFFFFF,
        token=token or secrets.token_urlsafe(32),
    )


def read_segment(
    descriptor: Descriptor,
    *,
    directory: Path | None = None,
    token: str,
    verify: bool = True,
) -> tuple[pa.Buffer, mmap.mmap]:
    """Map a segment, verify it, unlink the name, and return a buffer plus the mapping.

    The returned buffer holds a reference to the mapping, so the table built from
    it stays valid after the local name is deleted. The mapping must outlive the
    buffer: close it only after the buffer and every table built from it are
    dropped, otherwise `mmap.close()` raises BufferError.
    """
    if not hmac.compare_digest(descriptor.token, token):
        raise AuthError("segment token does not match")
    path = (directory or segment_dir()) / descriptor.name
    try:
        fd = os.open(path, os.O_RDONLY)
    except FileNotFoundError as exc:
        raise SegmentGone(f"segment {descriptor.name} is gone") from exc
    try:
        size = os.fstat(fd).st_size
        if size != descriptor.offset + descriptor.length:
            raise SegmentError(f"segment is {size} bytes, descriptor claims {descriptor.length}")
        mapping = mmap.mmap(fd, 0, access=mmap.ACCESS_READ)
    finally:
        os.close(fd)
    view = memoryview(mapping)[descriptor.offset : descriptor.offset + descriptor.length]
    if verify and (zlib.crc32(view) & 0xFFFFFFFF) != descriptor.crc32:
        mapping.close()
        _unlink(path)
        raise ChecksumMismatch("segment payload does not match its CRC")
    _unlink(path)
    return pa.py_buffer(mapping).slice(descriptor.offset, descriptor.length), mapping


def _unlink(path: Path) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        return


def sweep(
    *, directory: Path | None = None, ttl_s: float = DEFAULT_TTL_S, now: float | None = None
) -> int:
    """Remove segments older than ttl_s. Returns the count removed."""
    target = directory or segment_dir()
    if not target.is_dir():
        return 0
    cutoff = (time.time() if now is None else now) - ttl_s
    removed = 0
    for path in target.glob(f"{NAME_PREFIX}*"):
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except FileNotFoundError:
            continue
    return removed
