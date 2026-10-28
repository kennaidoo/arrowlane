"""Write the static agent manifest from the code."""

from __future__ import annotations

import json
from pathlib import Path

from arrowlane.describe import describe

TARGET = Path("docs/ai/manifest.json")


def main() -> int:
    """Generate the manifest so it cannot drift from the code."""
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(describe(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
