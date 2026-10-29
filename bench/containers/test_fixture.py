"""Prove that the benchmark fixture matches the Rust canonical fixture."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fixture import sample_table  # noqa: E402


def load_canonical():
    """Load the canonical fixture from the sibling Rust repository."""

    path = HERE.parents[1].parent / "arrowlane-rust" / "interop" / "check_wire.py"
    if not path.is_file():
        pytest.skip(f"canonical fixture not found: {path}")
    spec = importlib.util.spec_from_file_location("arrowlane_check_wire", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fixture_matches_rust_canonical() -> None:
    """The copied fixture must be column-for-column identical."""

    canonical = load_canonical()
    ours = sample_table(37)
    theirs = canonical.sample_table(37)
    assert ours.schema == theirs.schema  # noqa: S101
    assert ours.equals(theirs)  # noqa: S101
