#!/usr/bin/env bash
# Start the demo, measure every lane, check the results, stop.
set -euo pipefail
cd "$(dirname "$0")"

docker compose up -d --build app console
trap 'docker compose down -v' EXIT

for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8080/health >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

docker compose run --rm client
docker compose exec -T console cat /data/results.json > results.json

python - <<'PY'
import json
import pathlib
import sys

data = json.loads(pathlib.Path("results.json").read_text(encoding="utf-8"))
lanes = {row["lane"]: row for row in data["lanes"]}
checks = [
    ("three-lanes", set(lanes) == {"json", "ipc", "ipc-zstd"}),
    ("digests-match", len({row["digest"] for row in lanes.values()}) == 1),
    ("rows-match", all(row["rows"] == data["rows"] for row in lanes.values())),
    ("ipc-smaller-than-json", lanes["ipc"]["bytes"] < lanes["json"]["bytes"]),
    ("zstd-smaller-than-ipc", lanes["ipc-zstd"]["bytes"] < lanes["ipc"]["bytes"]),
    ("decision-is-portable", data["decision"]["lane"] in lanes),
]
failed = 0
for name, ok in checks:
    print(f"CHECK {name} {'PASS' if ok else 'FAIL'}")
    failed += 0 if ok else 1
print("RESULT: PASS" if failed == 0 else "RESULT: FAIL")
sys.exit(1 if failed else 0)
PY
