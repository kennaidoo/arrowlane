"""Rules that keep the repository honest."""

from __future__ import annotations

import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_version_matches_pyproject() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["version"] == "0.1.0"
    import arrowlane

    assert arrowlane.__version__ == data["project"]["version"]


def test_workflows_are_valid_yaml() -> None:
    files = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    assert files, "no workflows found"
    for path in files:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), path


def test_no_em_dash() -> None:
    offenders = []
    for path in list(ROOT.glob("*.md")) + list((ROOT / "docs").rglob("*.md")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "\u2014" in line:
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert not offenders, offenders


def test_library_does_not_print() -> None:
    offenders = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "src" / "arrowlane").rglob("*.py")
        if "print(" in path.read_text(encoding="utf-8") and path.name != "cli.py"
    ]
    assert not offenders, offenders
