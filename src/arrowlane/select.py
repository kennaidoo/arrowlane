"""Deterministic lane selection from a measured cost model."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .costmodel import CostModel
from .lanes import available_names


class Topology(StrEnum):
    """Where the two endpoints sit."""

    SAME_HOST = "same_host"
    SAME_NETWORK = "same_network"
    WIDE_AREA = "wide_area"


class Policy(StrEnum):
    """What the caller wants optimised."""

    LATENCY = "latency"
    THROUGHPUT = "throughput"
    CPU = "cpu"


@dataclass(frozen=True, slots=True)
class Workload:
    """What is about to be sent."""

    rows: int
    arrow_bytes: int
    tabular: bool = True


@dataclass(frozen=True, slots=True)
class Decision:
    """The chosen lane and the evidence for the choice."""

    lane: str
    reason: str
    predicted_ms: float
    predicted_bytes: int
    scores: tuple[tuple[str, float], ...] = ()
    rejected: tuple[tuple[str, str], ...] = field(default=())

    def as_dict(self) -> dict[str, object]:
        """JSON-ready form."""
        return {
            "lane": self.lane,
            "reason": self.reason,
            "predicted_ms": round(self.predicted_ms, 4),
            "predicted_bytes": self.predicted_bytes,
            "scores": [[name, round(value, 4)] for name, value in self.scores],
            "rejected": [[name, why] for name, why in self.rejected],
        }


_ORDER = {"shm": 0, "ipc-zstd": 1, "ipc": 2, "json": 3}


def select_plan(
    workload: Workload,
    *,
    topology: Topology | str,
    policy: Policy | str = Policy.LATENCY,
    model: CostModel,
    allowed: tuple[str, ...] | None = None,
    shm_ready: bool = False,
    min_gain: float = 0.10,
) -> Decision:
    """Choose a lane. The same input always produces the same decision."""
    resolved_topology = Topology(topology)
    resolved_policy = Policy(policy)
    if not 0.0 <= min_gain < 1.0:
        raise ValueError("min_gain must be in [0, 1)")
    mb = max(workload.arrow_bytes, 1) / 1e6
    baseline = model.predict(
        "json", mb=mb, topology=resolved_topology.value, policy=resolved_policy.value
    )
    if not workload.tabular:
        return Decision("json", "NON_TABULAR", baseline, workload.arrow_bytes)
    if workload.rows <= 0:
        return Decision("json", "EMPTY", baseline, workload.arrow_bytes)

    platform_lanes = frozenset(available_names())
    names = tuple(allowed) if allowed is not None else tuple(model.lanes)
    scores: list[tuple[str, float]] = []
    rejected: list[tuple[str, str]] = []
    for name in names:
        if name not in model.lanes:
            rejected.append((name, "UNKNOWN_LANE"))
            continue
        if name == "shm" and not shm_ready:
            rejected.append((name, "SHM_UNAVAILABLE"))
            continue
        if name not in platform_lanes:
            rejected.append((name, "NOT_AVAILABLE_ON_PLATFORM"))
            continue
        scores.append(
            (
                name,
                model.predict(
                    name,
                    mb=mb,
                    topology=resolved_topology.value,
                    policy=resolved_policy.value,
                ),
            )
        )
    if not scores:
        return Decision("json", "NO_CANDIDATE", baseline, workload.arrow_bytes, (), tuple(rejected))

    if resolved_policy is Policy.THROUGHPUT:
        floor = min(value for _, value in scores) * 1.05
        near = [(name, value) for name, value in scores if value <= floor]
        best_name, best_value = min(
            near,
            key=lambda item: (model.bytes_for(item[0], arrow_bytes=workload.arrow_bytes), item[1]),
        )
    else:
        best_name, best_value = min(scores, key=lambda item: (item[1], _ORDER.get(item[0], 99)))

    if best_name != "json" and "json" in dict(scores) and best_value > baseline * (1.0 - min_gain):
        return Decision(
            "json", "GAIN_TOO_SMALL", baseline, workload.arrow_bytes, tuple(scores), tuple(rejected)
        )
    return Decision(
        best_name,
        "BEST",
        best_value,
        model.bytes_for(best_name, arrow_bytes=workload.arrow_bytes),
        tuple(scores),
        tuple(rejected),
    )
