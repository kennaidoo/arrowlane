"""Lane registry contract."""

from __future__ import annotations

import dataclasses

import pyarrow as pa
import pytest

from arrowlane.errors import UnknownLane
from arrowlane.frame import Frame
from arrowlane.lanes import get_lane, lane_names, register
from arrowlane.lanes.base import LaneInfo, available_for


class DummyLane:
    info = LaneInfo(id=99, name="dummy", media_type="application/x-dummy")

    def encode(self, table: pa.Table, *, level: int | None = None) -> Frame:
        raise NotImplementedError

    def decode(self, frame: Frame, *, max_uncompressed: int | None = None) -> pa.Table:
        raise NotImplementedError


def test_registry_lists_the_builtin_lanes() -> None:
    assert lane_names() == ("json", "ipc", "ipc-zstd", "shm")


def test_unknown_lane_raises() -> None:
    with pytest.raises(UnknownLane):
        get_lane("nope")


def test_duplicate_registration_is_rejected() -> None:
    register(DummyLane())
    with pytest.raises(ValueError, match="already registered"):
        register(DummyLane())


def test_lane_info_is_frozen() -> None:
    info = LaneInfo(id=1, name="a", media_type="m")
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(info, "name", "b")  # noqa: B010 - the point is that it raises


def test_available_for_includes_shm_when_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("arrowlane.lanes.base.os.name", "posix")
    monkeypatch.setattr("arrowlane.lanes.base.is_ready", lambda directory=None: True)
    assert "shm" in available_for()
