"""Measured cost model for the lane selector.

Every slope is milliseconds per megabyte of Arrow data. The `ratio` is wire
bytes divided by Arrow bytes. The fixed term is the per-call overhead. The wire
term is microseconds per megabyte for a topology, multiplied by the lane ratio.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any, Final

from .errors import ConfigError

SCHEMA_VERSION: Final = 1
TOPOLOGIES: Final = ("same_host", "same_network", "wide_area")
_LANE_KEYS: Final = ("fixed_ms", "enc_ms_per_mb", "dec_ms_per_mb", "ratio")
_TOP_KEYS: Final = ("schema_version", "provenance", "wire_us_per_mb", "lanes")


@dataclass(frozen=True, slots=True)
class LaneCost:
    """Cost coefficients for one lane."""

    fixed_ms: float
    enc_ms_per_mb: float
    dec_ms_per_mb: float
    ratio: float


@dataclass(frozen=True, slots=True)
class CostModel:
    """A validated, versioned cost model."""

    schema_version: int
    provenance: dict[str, Any]
    wire_us_per_mb: dict[str, float]
    lanes: dict[str, LaneCost]

    def predict(self, lane: str, *, mb: float, topology: str, policy: str = "latency") -> float:
        """Predicted end to end milliseconds for one table on one lane."""
        cost = self.lane_cost(lane)
        total = cost.fixed_ms + (cost.enc_ms_per_mb + cost.dec_ms_per_mb) * mb
        if policy != "cpu":
            total += (self.wire_us_per_mb[topology] / 1000.0) * mb * cost.ratio
        return total

    def lane_cost(self, lane: str) -> LaneCost:
        """Return the coefficients for a lane."""
        try:
            return self.lanes[lane]
        except KeyError as exc:
            raise ConfigError(f"lane {lane!r} is not in the cost model") from exc

    def bytes_for(self, lane: str, *, arrow_bytes: int) -> int:
        """Predicted wire bytes for a table of this Arrow size."""
        return int(arrow_bytes * self.lane_cost(lane).ratio)


def _number(value: Any, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{what} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ConfigError(f"{what} must be finite")
    if number < 0:
        raise ConfigError(f"{what} must not be negative")
    return number


def load(path: str | Path) -> CostModel:
    """Read and validate a cost model file."""
    raw = Path(path).read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"cost model is not JSON: {exc}") from exc
    return parse(data)


def parse(data: Any) -> CostModel:
    """Validate an already parsed cost model."""
    if not isinstance(data, dict):
        raise ConfigError("cost model must be a JSON object")
    unknown = set(data) - set(_TOP_KEYS)
    if unknown:
        raise ConfigError(f"unknown key: {sorted(unknown)[0]}")
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ConfigError(f"schema_version must be {SCHEMA_VERSION}")
    provenance = data.get("provenance")
    if not isinstance(provenance, dict) or not provenance:
        raise ConfigError("provenance must be a non-empty object")
    wire_raw = data.get("wire_us_per_mb")
    if not isinstance(wire_raw, dict):
        raise ConfigError("wire_us_per_mb must be an object")
    wire = {name: _number(wire_raw.get(name), f"wire_us_per_mb.{name}") for name in TOPOLOGIES}
    lanes_raw = data.get("lanes")
    if not isinstance(lanes_raw, dict) or not lanes_raw:
        raise ConfigError("lanes must be a non-empty object")
    lanes: dict[str, LaneCost] = {}
    for name, entry in lanes_raw.items():
        if not isinstance(entry, dict):
            raise ConfigError(f"lane {name} must be an object")
        extra = set(entry) - set(_LANE_KEYS)
        if extra:
            raise ConfigError(f"lane {name} has unknown key {sorted(extra)[0]}")
        missing = set(_LANE_KEYS) - set(entry)
        if missing:
            raise ConfigError(f"lane {name} is missing {sorted(missing)[0]}")
        lanes[name] = LaneCost(
            fixed_ms=_number(entry["fixed_ms"], f"lanes.{name}.fixed_ms"),
            enc_ms_per_mb=_number(entry["enc_ms_per_mb"], f"lanes.{name}.enc_ms_per_mb"),
            dec_ms_per_mb=_number(entry["dec_ms_per_mb"], f"lanes.{name}.dec_ms_per_mb"),
            ratio=_number(entry["ratio"], f"lanes.{name}.ratio"),
        )
    if "json" not in lanes:
        raise ConfigError("cost model must carry the json lane as the baseline")
    return CostModel(version, provenance, wire, lanes)


def load_default() -> CostModel:
    """Load the shipped cost model."""
    resource = files("arrowlane").joinpath("costmodel.json")
    return parse(json.loads(resource.read_text(encoding="utf-8")))
