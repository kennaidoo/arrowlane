"""End to end transit: plan a lane, pack a table, unpack it again."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa

from .costmodel import CostModel, load_default
from .frame import MAX_PAYLOAD_BYTES, MAX_UNCOMPRESSED_BYTES, decode_frame, encode_frame
from .lanes import get_lane
from .lanes.base import Lane
from .select import Decision, Policy, Topology, Workload, select_plan
from .shm import is_ready
from .table import estimate_bytes, to_table


def _lane(name: str, *, token: str | None, directory: Path | None) -> Lane:
    """Return the lane for a name. The shm lane is built for this call."""
    if name == "shm":
        from .lanes.shm_lane import ShmLane

        return ShmLane(directory=directory, token=token)
    return get_lane(name)


def plan(
    table: pa.Table,
    *,
    topology: Topology | str,
    policy: Policy | str = Policy.LATENCY,
    model: CostModel | None = None,
    allowed: tuple[str, ...] | None = None,
    shm: bool | None = None,
    min_gain: float = 0.10,
) -> Decision:
    """Choose a lane for this table. Probes shared memory when shm is None."""
    resolved = model or load_default()
    ready = is_ready() if shm is None else shm
    return select_plan(
        Workload(rows=table.num_rows, arrow_bytes=estimate_bytes(table)),
        topology=topology,
        policy=policy,
        model=resolved,
        allowed=allowed,
        shm_ready=ready,
        min_gain=min_gain,
    )


def pack(
    table: pa.Table,
    *,
    lane: str,
    token: str | None = None,
    directory: Path | None = None,
    level: int | None = None,
    max_payload: int = MAX_PAYLOAD_BYTES,
) -> bytes:
    """Encode the table on one lane and return the wire frame."""
    chosen = _lane(lane, token=token, directory=directory)
    return encode_frame(chosen.encode(table, level=level), max_payload=max_payload)


def unpack(
    data: bytes | bytearray | memoryview,
    *,
    token: str | None = None,
    directory: Path | None = None,
    max_payload: int = MAX_PAYLOAD_BYTES,
    max_uncompressed: int = MAX_UNCOMPRESSED_BYTES,
) -> pa.Table:
    """Validate a wire frame and decode it on the lane it names."""
    frame = decode_frame(data, max_payload=max_payload, max_uncompressed=max_uncompressed)
    chosen = _lane(frame.lane, token=token, directory=directory)
    return chosen.decode(frame, max_uncompressed=max_uncompressed)


def transit(
    obj: Any,
    *,
    topology: Topology | str = Topology.SAME_NETWORK,
    policy: Policy | str = Policy.LATENCY,
    model: CostModel | None = None,
    allowed: tuple[str, ...] | None = None,
    token: str | None = None,
    directory: Path | None = None,
    level: int | None = None,
) -> tuple[bytes, Decision]:
    """Plan a lane, encode the table, and return the bytes with the decision."""
    table = to_table(obj)
    decision = plan(
        table,
        topology=topology,
        policy=policy,
        model=model,
        allowed=allowed,
        shm=token is not None,
    )
    wire = pack(table, lane=decision.lane, token=token, directory=directory, level=level)
    return wire, decision
