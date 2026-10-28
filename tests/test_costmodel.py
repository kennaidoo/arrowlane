"""Cost model parsing and prediction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from arrowlane.costmodel import CostModel, load, load_default
from arrowlane.errors import ConfigError

GOOD = {
    "schema_version": 1,
    "provenance": {
        "host": "x",
        "platform": "linux",
        "python": "3.15.1",
        "pyarrow": "26.0.0",
        "measured_at": "2026-10-28",
        "method": "test",
        "source": "test",
    },
    "wire_us_per_mb": {"same_host": 300.0, "same_network": 800.0, "wide_area": 25000.0},
    "lanes": {
        "json": {"fixed_ms": 0.002, "enc_ms_per_mb": 100.0, "dec_ms_per_mb": 40.0, "ratio": 2.0},
        "ipc": {"fixed_ms": 0.06, "enc_ms_per_mb": 0.3, "dec_ms_per_mb": 0.05, "ratio": 1.0},
    },
}


def write(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "model.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_good(tmp_path: Path) -> None:
    model = load(write(tmp_path, GOOD))
    assert isinstance(model, CostModel)
    assert model.lanes["ipc"].ratio == 1.0
    assert model.predict("ipc", mb=1.0, topology="same_network") == pytest.approx(0.06 + 0.35 + 0.8)


def test_predict_cpu_ignores_wire(tmp_path: Path) -> None:
    model = load(write(tmp_path, GOOD))
    assert model.predict("ipc", mb=1.0, topology="wide_area", policy="cpu") == pytest.approx(0.41)


def test_bytes_for(tmp_path: Path) -> None:
    model = load(write(tmp_path, GOOD))
    assert model.bytes_for("json", arrow_bytes=1000) == 2000


def test_missing_wire_topology_is_rejected(tmp_path: Path) -> None:
    bad = json.loads(json.dumps(GOOD))
    del bad["wire_us_per_mb"]["wide_area"]
    with pytest.raises(ConfigError, match="wide_area"):
        load(write(tmp_path, bad))


def test_negative_value_is_rejected(tmp_path: Path) -> None:
    bad = json.loads(json.dumps(GOOD))
    bad["lanes"]["ipc"]["enc_ms_per_mb"] = -1.0
    with pytest.raises(ConfigError, match="negative"):
        load(write(tmp_path, bad))


def test_unknown_lane_key_is_rejected(tmp_path: Path) -> None:
    bad = json.loads(json.dumps(GOOD))
    bad["lanes"]["ipc"]["typo"] = 1.0
    with pytest.raises(ConfigError, match="unknown key"):
        load(write(tmp_path, bad))


def test_missing_json_lane_is_rejected(tmp_path: Path) -> None:
    bad = json.loads(json.dumps(GOOD))
    del bad["lanes"]["json"]
    with pytest.raises(ConfigError, match="json"):
        load(write(tmp_path, bad))


def test_wrong_schema_version_is_rejected(tmp_path: Path) -> None:
    bad = json.loads(json.dumps(GOOD))
    bad["schema_version"] = 2
    with pytest.raises(ConfigError, match="schema_version"):
        load(write(tmp_path, bad))


def test_default_model_loads() -> None:
    model = load_default()
    assert set(model.lanes) == {"json", "ipc", "ipc-zstd", "shm"}
    assert model.provenance["source"] in {"seed", "bench"}
