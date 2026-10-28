"""Command line interface: select and version."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from . import __version__
from .costmodel import load, load_default
from .describe import describe
from .errors import ArrowLaneError
from .select import Topology, Workload, select_plan


def _build() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="arrowlane", description=__doc__)
    parser.add_argument("--version", action="version", version=f"arrowlane {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    select = sub.add_parser("select", help="explain a lane choice")
    select.add_argument("--rows", type=int, required=True)
    select.add_argument("--bytes", type=int, required=True, dest="arrow_bytes")
    select.add_argument("--topology", choices=[t.value for t in Topology], default="same_network")
    select.add_argument("--policy", choices=["latency", "throughput", "cpu"], default="latency")
    select.add_argument("--allow", default=None, help="comma separated lane allowlist")
    select.add_argument("--shm-ready", action="store_true")
    select.add_argument("--model", default=None, help="path to a cost model JSON file")
    select.add_argument("--json", action="store_true", dest="as_json")

    describe_parser = sub.add_parser(
        "describe", help="print the machine-readable capability manifest"
    )
    describe_parser.add_argument("--indent", type=int, default=2)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one CLI command and return the exit code."""
    args = _build().parse_args(argv)
    if args.command == "describe":
        print(json.dumps(describe(), indent=args.indent))
        return 0
    try:
        model = load(args.model) if args.model else load_default()
        allowed = (
            tuple(part.strip() for part in args.allow.split(",") if part.strip())
            if args.allow
            else None
        )
        decision = select_plan(
            Workload(rows=args.rows, arrow_bytes=args.arrow_bytes),
            topology=args.topology,
            policy=args.policy,
            model=model,
            allowed=allowed,
            shm_ready=args.shm_ready,
        )
    except (ArrowLaneError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps(decision.as_dict()))
    else:
        print(
            f"lane={decision.lane} reason={decision.reason} "
            f"predicted_ms={decision.predicted_ms:.3f} predicted_bytes={decision.predicted_bytes}"
        )
    return 0
