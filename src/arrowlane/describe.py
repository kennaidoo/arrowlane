"""Machine-readable capabilities for agents and builds."""

from __future__ import annotations

from .frame import MAX_HEADER_BYTES, MAX_PAYLOAD_BYTES, MAX_UNCOMPRESSED_BYTES
from .lanes import get_lane, lane_names
from .shm import MAX_SEGMENT_BYTES
from .version import __version__


def describe() -> dict[str, object]:
    """Return the capability manifest. The static JSON must equal this."""
    lanes = []
    for name in lane_names():
        info = get_lane(name).info
        lanes.append(
            {
                "name": info.name,
                "id": info.id,
                "requires": info.requires,
                "media_type": info.media_type,
            }
        )
    return {
        "schema_version": 1,
        "package": "arrowlane",
        "package_version": __version__,
        "source": "arrowlane",
        "python_requires": ">=3.14",
        "install": {
            "pip": "pip install arrowlane",
            "extras": ["server", "pandas", "polars", "duckdb", "bench", "dev"],
        },
        "entrypoints": {
            "transit": "arrowlane.transit",
            "describe": "arrowlane describe",
            "cli": "arrowlane.cli:main",
        },
        "lanes": lanes,
        "limits": {
            "max_header_bytes": MAX_HEADER_BYTES,
            "max_payload_bytes": MAX_PAYLOAD_BYTES,
            "max_uncompressed_bytes": MAX_UNCOMPRESSED_BYTES,
            "max_segment_bytes": MAX_SEGMENT_BYTES,
        },
        "docs": {
            "agents": "docs/ai/operating-guide.md",
            "llms": "llms.txt",
            "quickstart": "docs/ai/quickstart.md",
            "api": "docs/ai/api.md",
            "recipes": "docs/ai/recipes.md",
            "decisions": "docs/ADR",
        },
        "checks": {
            "gate": "bash scripts/gate.sh",
            "tests": "python -m pytest -q",
            "bench": "python bench/verify.py",
            "demo": "bash demo/verify.sh",
        },
    }
