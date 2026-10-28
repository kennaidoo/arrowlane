"""Shared fixtures. Every test starts from the built-in lane registry."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from arrowlane.lanes import base


@pytest.fixture(autouse=True)
def restore_lane_registry() -> Iterator[None]:
    """Undo any lane registered by a test."""
    snapshot = dict(base._REGISTRY)
    yield
    base._REGISTRY.clear()
    base._REGISTRY.update(snapshot)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Turn the `linux` marker into a skip on platforms without POSIX shared memory."""
    if os.name == "posix":
        return
    skip = pytest.mark.skip(reason="POSIX shared memory is required")
    for item in items:
        if "linux" in item.keywords:
            item.add_marker(skip)
