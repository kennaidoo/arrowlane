"""Selector rules, one case per rule."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from arrowlane.costmodel import CostModel, LaneCost, load_default
from arrowlane.select import Decision, Topology, Workload, select_plan

BIG = Workload(rows=200_000, arrow_bytes=13_380_000)
TINY = Workload(rows=6, arrow_bytes=400)
MODEL = load_default()


def pick(workload: Workload = BIG, **kwargs: Any) -> Decision:
    kwargs.setdefault("topology", Topology.SAME_NETWORK)
    kwargs.setdefault("policy", "latency")
    kwargs.setdefault("model", MODEL)
    return select_plan(workload, **kwargs)


@pytest.mark.linux
def test_same_host_with_shm_ready_chooses_shm() -> None:
    decision = pick(topology=Topology.SAME_HOST, shm_ready=True)
    assert decision.lane == "shm"
    assert decision.reason == "BEST"


def test_same_host_without_shm_chooses_ipc() -> None:
    decision = pick(topology=Topology.SAME_HOST, shm_ready=False)
    assert decision.lane == "ipc"
    assert ("shm", "SHM_UNAVAILABLE") in decision.rejected


def test_wide_area_chooses_zstd() -> None:
    assert pick(topology=Topology.WIDE_AREA).lane == "ipc-zstd"


def test_lan_chooses_ipc() -> None:
    assert pick(topology=Topology.SAME_NETWORK).lane == "ipc"


def test_tiny_payload_falls_back_to_json() -> None:
    decision = pick(TINY)
    assert decision.lane == "json"
    assert decision.reason == "GAIN_TOO_SMALL"


def test_empty_table_falls_back_to_json() -> None:
    decision = pick(Workload(rows=0, arrow_bytes=0))
    assert (decision.lane, decision.reason) == ("json", "EMPTY")


def test_non_tabular_falls_back_to_json() -> None:
    decision = pick(Workload(rows=10, arrow_bytes=100, tabular=False))
    assert (decision.lane, decision.reason) == ("json", "NON_TABULAR")


def test_allowlist_excludes_zstd() -> None:
    decision = pick(topology=Topology.WIDE_AREA, allowed=("json", "ipc"))
    assert decision.lane == "ipc"


def test_unknown_lane_in_allowlist_is_reported() -> None:
    decision = pick(allowed=("json", "ipc", "nope"))
    assert ("nope", "UNKNOWN_LANE") in decision.rejected


def test_cpu_policy_ignores_wire_cost() -> None:
    assert pick(topology=Topology.WIDE_AREA, policy="cpu").lane == "ipc"


def test_throughput_prefers_smaller_bytes_within_five_percent() -> None:
    close = dict(MODEL.lanes)
    close["ipc"] = LaneCost(0.10, 0.31, 0.05, 1.0)
    close["ipc-zstd"] = LaneCost(0.10, 0.311, 0.05, 0.38)
    model: CostModel = dataclasses.replace(
        MODEL, lanes=close, wire_us_per_mb={**MODEL.wire_us_per_mb, "same_host": 0.0}
    )
    decision = select_plan(BIG, topology=Topology.SAME_HOST, policy="throughput", model=model)
    assert decision.lane == "ipc-zstd"


def test_scores_cover_every_candidate() -> None:
    decision = pick()
    assert {name for name, _ in decision.scores} == {"json", "ipc", "ipc-zstd"}
    assert decision.predicted_ms > 0
    assert decision.predicted_bytes > 0
