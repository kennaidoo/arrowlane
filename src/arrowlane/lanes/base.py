"""Lane protocol and registry."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

import pyarrow as pa

from ..errors import UnknownLane
from ..frame import Frame


@dataclass(frozen=True, slots=True)
class LaneInfo:
    """Static description of a lane."""

    id: int
    name: str
    media_type: str
    requires: Literal["any", "posix"] = "any"


@runtime_checkable
class Lane(Protocol):
    """A physical transport for one table."""

    info: LaneInfo

    def encode(self, table: pa.Table, *, level: int | None = None) -> Frame:
        """Encode a table into a frame."""
        ...

    def decode(self, frame: Frame, *, max_uncompressed: int | None = None) -> pa.Table:
        """Decode a frame into a table."""
        ...


_REGISTRY: dict[str, Lane] = {}


def register(lane: Lane) -> None:
    """Add a lane to the registry. A duplicate name is a programming error."""
    if lane.info.name in _REGISTRY:
        raise ValueError(f"lane {lane.info.name!r} is already registered")
    _REGISTRY[lane.info.name] = lane


def get_lane(name: str) -> Lane:
    """Return a registered lane or raise UnknownLane."""
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise UnknownLane(f"unknown lane {name!r}, known: {sorted(_REGISTRY)}") from exc


def lane_names() -> tuple[str, ...]:
    """Registered lane names in registration order."""
    return tuple(_REGISTRY)


def available_names() -> tuple[str, ...]:
    """Registered lanes that this platform can serve."""
    return tuple(
        name
        for name, lane in _REGISTRY.items()
        if lane.info.requires == "any" or os.name == "posix"
    )
