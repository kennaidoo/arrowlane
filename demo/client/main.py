"""Measure every portable lane against the running service."""

from __future__ import annotations

import datetime as dt
import json
import os
import time
import urllib.request

from arrowlane.table import schema_digest
from arrowlane.transit import unpack

BASE = os.environ.get("ARROWLAND_BASE", "http://127.0.0.1:8080")
ROWS = int(os.environ.get("ARROWLAND_ROWS", "50000"))
OUT = os.environ.get("ARROWLAND_OUT", "/data/results.json")
LANES = ("json", "ipc", "ipc-zstd")


def fetch(path: str) -> bytes:
    """Read one response body."""
    with urllib.request.urlopen(f"{BASE}{path}", timeout=120) as response:
        return response.read()


def main() -> int:
    """Measure the lanes and write one result file."""
    reference = None
    digest = ""
    results = []
    for lane in LANES:
        start = time.perf_counter()
        body = fetch(f"/table?rows={ROWS}&lane={lane}")
        ms = (time.perf_counter() - start) * 1000.0
        table = unpack(body)
        if reference is None:
            reference = table
            digest = schema_digest(table)
        elif not table.equals(reference):
            raise SystemExit(f"{lane}: payload differs from the json reference")
        results.append(
            {
                "lane": lane,
                "bytes": len(body),
                "ms": round(ms, 3),
                "digest": digest,
                "rows": table.num_rows,
            }
        )
    decision = json.loads(fetch(f"/decision?rows={ROWS}"))
    payload = {
        "measured_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "rows": ROWS,
        "lanes": results,
        "decision": decision,
    }
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    print(f"RESULTS: {len(results)}/{len(LANES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
