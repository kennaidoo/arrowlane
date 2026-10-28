"""The agent documentation must not drift from the code."""

from __future__ import annotations

import json
import re
from pathlib import Path

from arrowlane.describe import describe
from arrowlane.version import __version__

ROOT = Path(__file__).resolve().parents[1]
FENCE = "`" * 3


def test_manifest_matches_the_code() -> None:
    manifest = json.loads((ROOT / "docs/ai/manifest.json").read_text(encoding="utf-8"))
    assert manifest == describe()
    assert manifest["package_version"] == __version__


def test_manifest_paths_exist() -> None:
    manifest = json.loads((ROOT / "docs/ai/manifest.json").read_text(encoding="utf-8"))
    for path in manifest["docs"].values():
        assert (ROOT / path).exists(), path


def test_agent_docs_have_no_em_dash() -> None:
    paths = [ROOT / "llms.txt", *sorted((ROOT / "docs/ai").glob("*.md"))]
    for path in paths:
        assert "\u2014" not in path.read_text(encoding="utf-8"), path


def test_ai_python_blocks_compile() -> None:
    pattern = re.escape(FENCE + "python") + r"\n(.*?)" + re.escape(FENCE)
    for path in sorted((ROOT / "docs/ai").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for index, block in enumerate(re.findall(pattern, text, flags=re.DOTALL)):
            compile(block, f"{path.name}:{index}", "exec")
