"""The README quick start must run."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FENCE = "`" * 3


def test_readme_quick_start_runs() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    pattern = re.escape(FENCE + "python") + r"\n(.*?)" + re.escape(FENCE)
    blocks = re.findall(pattern, text, flags=re.DOTALL)
    assert blocks, "README has no python block"
    namespace: dict[str, object] = {}
    exec(compile(blocks[0], "README.md", "exec"), namespace)  # noqa: S102 - run the example
    assert namespace["rows"] == 3
