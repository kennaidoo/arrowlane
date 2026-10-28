"""POSIX shared memory segments. Segment tests skip on Windows."""

from __future__ import annotations

import gc
import json
import os
import time
from pathlib import Path

import pytest

from arrowlane.errors import AuthError, ChecksumMismatch, SegmentError, SegmentGone
from arrowlane.shm import (
    Descriptor,
    is_ready,
    read_segment,
    segment_dir,
    sweep,
    write_segment,
)


def test_descriptor_roundtrip() -> None:
    desc = Descriptor(name="al-abc", length=10, crc32=123, token="t" * 32)
    assert Descriptor.from_bytes(desc.to_bytes()) == desc


def test_descriptor_rejects_bad_json() -> None:
    with pytest.raises(SegmentError):
        Descriptor.from_bytes(b"{nope")


def test_descriptor_rejects_empty_segment() -> None:
    with pytest.raises(SegmentError, match="length"):
        Descriptor.from_bytes(b'{"name":"al-x","length":0,"crc32":0,"token":"t"}')


def test_descriptor_rejects_unknown_key() -> None:
    payload = json.dumps(
        {"name": "al-x", "length": 1, "crc32": 0, "token": "t" * 32, "extra": 1}
    ).encode("utf-8")
    with pytest.raises(SegmentError, match="unknown"):
        Descriptor.from_bytes(payload)


def test_not_ready_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("arrowlane.shm.os.name", "nt")
    assert is_ready() is False


def test_segment_dir_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARROWLAND_SHM_DIR", str(tmp_path))
    assert segment_dir() == tmp_path


@pytest.mark.linux
def test_write_and_read_roundtrip(tmp_path: Path) -> None:
    desc = write_segment(b"hello world", directory=tmp_path, token="k" * 32)
    buffer, mapping = read_segment(desc, directory=tmp_path, token="k" * 32)
    assert buffer.to_pybytes() == b"hello world"
    assert not (tmp_path / desc.name).exists(), "segment must be unlinked after the attach"
    del buffer
    gc.collect()
    mapping.close()


@pytest.mark.linux
def test_wrong_token_is_rejected(tmp_path: Path) -> None:
    desc = write_segment(b"secret", directory=tmp_path, token="k" * 32)
    with pytest.raises(AuthError):
        read_segment(desc, directory=tmp_path, token="w" * 32)


@pytest.mark.linux
def test_second_read_reports_gone(tmp_path: Path) -> None:
    desc = write_segment(b"once", directory=tmp_path, token="k" * 32)
    buffer, mapping = read_segment(desc, directory=tmp_path, token="k" * 32)
    del buffer
    gc.collect()
    mapping.close()
    with pytest.raises(SegmentGone):
        read_segment(desc, directory=tmp_path, token="k" * 32)


@pytest.mark.linux
def test_crc_mismatch_is_rejected(tmp_path: Path) -> None:
    desc = write_segment(b"data", directory=tmp_path, token="k" * 32)
    wrong = Descriptor(desc.name, desc.length, desc.crc32 ^ 0xFF, desc.token)
    with pytest.raises(ChecksumMismatch):
        read_segment(wrong, directory=tmp_path, token="k" * 32)


@pytest.mark.linux
def test_sweep_removes_only_stale_segments(tmp_path: Path) -> None:
    fresh = write_segment(b"new", directory=tmp_path, token="k" * 32)
    old = write_segment(b"old", directory=tmp_path, token="k" * 32)
    old_path = tmp_path / old.name
    past = time.time() - 3600
    os.utime(old_path, (past, past))
    removed = sweep(directory=tmp_path, ttl_s=60)
    assert removed == 1
    assert (tmp_path / fresh.name).exists()
    assert not old_path.exists()


def test_write_segment_is_binary_safe(tmp_path: Path) -> None:
    payload = b"a\nb\r\nc\n" * 1000
    descriptor = write_segment(payload, directory=tmp_path, token="k" * 32)
    path = tmp_path / descriptor.name
    assert descriptor.length == len(payload)
    assert path.stat().st_size == len(payload)
    assert path.read_bytes() == payload


def test_zero_length_write_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("arrowlane.shm.os.write", lambda fd, data: 0)
    with pytest.raises(SegmentError, match="short write"):
        write_segment(b"payload", directory=tmp_path, token="k" * 32)
    assert list(tmp_path.iterdir()) == [], "a failed write must leave no segment"


def test_write_attempts_are_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def one_byte(fd: int, data: memoryview) -> int:
        calls["n"] += 1
        return 1

    monkeypatch.setattr("arrowlane.shm.os.write", one_byte)
    with pytest.raises(SegmentError, match="attempts"):
        write_segment(b"x" * 64, directory=tmp_path, token="k" * 32, max_attempts=8)
    assert calls["n"] == 8


def test_is_ready_does_not_create_the_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("arrowlane.shm.os.name", "posix")
    target = tmp_path / "missing"
    assert is_ready(target) is False
    assert not target.exists()


def test_is_ready_rejects_the_temp_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARROWLAND_SHM_DIR", raising=False)
    monkeypatch.setattr("arrowlane.shm._memory_dir_available", lambda: False)
    assert is_ready() is False
