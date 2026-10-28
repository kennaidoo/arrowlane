"""The public facade must plan, pack and unpack on every available lane."""

from __future__ import annotations

import pyarrow as pa
import pytest

import arrowlane
from arrowlane.errors import OversizeFrame, SegmentGone, UnknownLane
from arrowlane.lanes import available_names


@pytest.fixture
def table() -> pa.Table:
    return pa.table({"a": list(range(1000)), "b": ["x"] * 1000})


def test_every_lane_roundtrips(table: pa.Table) -> None:
    for name in available_names():
        if name == "shm":
            continue
        wire = arrowlane.pack(table, lane=name)
        assert arrowlane.unpack(wire).equals(table), name


def test_transit_uses_the_planned_lane(table: pa.Table) -> None:
    wire, decision = arrowlane.transit(table, topology="wide_area")
    assert decision.lane == "ipc-zstd"
    assert wire[4] == 1, "frame version"
    assert arrowlane.unpack(wire).equals(table)


def test_transit_without_a_token_never_plans_shm(table: pa.Table) -> None:
    _, decision = arrowlane.transit(table, topology="same_host")
    assert decision.lane != "shm"


def test_pack_rejects_an_unknown_lane(table: pa.Table) -> None:
    with pytest.raises(UnknownLane):
        arrowlane.pack(table, lane="nope")


def test_unpack_enforces_the_payload_cap() -> None:
    table = pa.table({"a": list(range(1000))})
    wire = arrowlane.pack(table, lane="ipc")
    with pytest.raises(OversizeFrame):
        arrowlane.unpack(wire, max_payload=64)


def test_unpack_enforces_the_uncompressed_cap() -> None:
    table = pa.table({"a": list(range(1000))})
    wire = arrowlane.pack(table, lane="ipc-zstd")
    with pytest.raises(OversizeFrame):
        arrowlane.unpack(wire, max_uncompressed=64)


@pytest.mark.linux
def test_shm_roundtrips_through_the_facade(table: pa.Table) -> None:
    token = "t" * 32
    wire = arrowlane.pack(table, lane="shm", token=token)
    assert arrowlane.unpack(wire, token=token).equals(table)
    with pytest.raises(SegmentGone):
        arrowlane.unpack(wire, token=token)
