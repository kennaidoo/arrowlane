"""CLI surface, exercised through main() so no subprocess is needed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arrowlane.cli import main


def test_select_prints_json(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "select",
            "--rows",
            "200000",
            "--bytes",
            "13380000",
            "--topology",
            "same_network",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["lane"] == "ipc"
    assert payload["reason"] == "BEST"
    assert payload["predicted_bytes"] > 0


def test_select_human_output(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["select", "--rows", "200000", "--bytes", "13380000"])
    out = capsys.readouterr().out
    assert code == 0
    assert "lane=ipc" in out
    assert "reason=BEST" in out


def test_unknown_topology_exits_nonzero() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["select", "--rows", "1", "--bytes", "10", "--topology", "moon"])
    assert exc.value.code == 2


def test_missing_model_exits_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["select", "--rows", "1", "--bytes", "10", "--model", str(tmp_path / "nope.json")])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("error:")
    assert "Traceback" not in captured.err


def test_allowlist_spaces_are_trimmed(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["select", "--rows", "200000", "--bytes", "13380000", "--allow", "json, ipc"])
    assert code == 0
    assert "lane=" in capsys.readouterr().out


def test_describe_is_json(capsys: pytest.CaptureFixture[str]) -> None:
    from arrowlane.version import __version__

    code = main(["describe"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["package_version"] == __version__
    assert {lane["name"] for lane in payload["lanes"]} == {"json", "ipc", "ipc-zstd", "shm"}
