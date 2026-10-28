"""CLI surface, exercised through main() so no subprocess is needed."""

from __future__ import annotations

import json

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
