"""Build and run the three container benchmarks, then write results."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMPOSE = HERE / "compose.yaml"
RESULTS = HERE / "results"
LANES = ("json", "ipc", "ipc-zstd")
IMPLS = ("python", "rust", "zig")
PREFIXES = {"python": [], "rust": ["bench"], "zig": ["bench"]}
DOCKER = shutil.which("docker")


def compose_run(service: str, args: list[str]) -> str:
    """Run one service and return its standard output."""

    command = [
        DOCKER,
        "compose",
        "-f",
        str(COMPOSE),
        "run",
        "--rm",
        "--no-deps",
        "-T",
        service,
        *args,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(
            f"{service} failed with code {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result.stdout


def parse_measurements(text: str) -> dict[str, tuple[int, float, float]]:
    """Parse four-field lane lines and require all three lanes."""

    found: dict[str, tuple[int, float, float]] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 4 or parts[0] not in LANES:
            continue
        try:
            found[parts[0]] = (int(parts[1]), float(parts[2]), float(parts[3]))
        except ValueError as error:
            raise SystemExit(f"cannot parse line: {line!r}") from error
    missing = set(LANES) - set(found)
    if missing:
        raise SystemExit(f"missing lanes: {sorted(missing)}\n{text}")
    return found


def measure(impl: str, rows: int, repeats: int) -> dict[str, tuple[int, float, float]]:
    """Discard one warmup run, then measure the requested repeats."""

    args = [*PREFIXES[impl], "--rows", str(rows), "--repeats"]
    compose_run(impl, [*args, "1"])
    return parse_measurements(compose_run(impl, [*args, str(repeats)]))


def main() -> int:
    """Build images, measure all implementations, and write report files."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=200_000)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.rows < 0:
        parser.error("--rows must be non-negative")
    if args.repeats < 1:
        parser.error("--repeats must be positive")

    if DOCKER is None:
        raise SystemExit("docker not found on PATH")
    subprocess.run(
        [DOCKER, "compose", "-f", str(COMPOSE), "build"],
        check=True,
    )

    measured: dict[str, dict[str, tuple[int, float, float]]] = {}
    for impl in IMPLS:
        print(f"measuring {impl}", file=sys.stderr)
        measured[impl] = measure(impl, args.rows, args.repeats)

    now = dt.datetime.now(dt.UTC)
    payload = {
        "schema_version": 1,
        "rows": args.rows,
        "repeats": args.repeats,
        "warmup_repeats": 1,
        "measured_at": now.isoformat(timespec="seconds"),
        "wire_delta_baseline": "python",
        "results": [
            {
                "impl": impl,
                "lane": lane,
                "wire_bytes": measured[impl][lane][0],
                "wire_delta_bytes": measured[impl][lane][0] - measured["python"][lane][0],
                "encode_ms": measured[impl][lane][1],
                "decode_ms": measured[impl][lane][2],
            }
            for impl in IMPLS
            for lane in LANES
        ],
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    raw_path = RESULTS / f"bench-{stamp}.json"
    latest_json = RESULTS / "latest.json"
    latest_md = RESULTS / "latest.md"
    raw_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    latest_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# arrowlane Docker benchmark",
        "",
        f"- Rows: {args.rows}",
        f"- Repeats: {args.repeats}",
        "- Warmup repeats: 1",
        f"- Measured at: {payload['measured_at']}",
        "- Wire delta baseline: Python",
        "",
        "| Implementation | Lane | Wire bytes | Wire delta | Encode ms | Decode ms |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in payload["results"]:
        lines.append(
            f"| {item['impl']} | {item['lane']} | {item['wire_bytes']} "
            f"| {item['wire_delta_bytes']:+d} "
            f"| {item['encode_ms']:.3f} | {item['decode_ms']:.3f} |"
        )
    latest_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(raw_path)
    print(latest_json)
    print(latest_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
