#!/usr/bin/env bash
# Run every local check. One line per check. Exit 1 on any failure.
set -uo pipefail
cd "$(dirname "$0")/.."

if [ -x .venv/Scripts/python.exe ]; then
  PY=.venv/Scripts/python.exe
  RUFF=.venv/Scripts/ruff.exe
  MYPY=.venv/Scripts/mypy.exe
  PYTEST=.venv/Scripts/pytest.exe
  AUDIT=.venv/Scripts/pip-audit.exe
else
  PY=.venv/bin/python
  RUFF=.venv/bin/ruff
  MYPY=.venv/bin/mypy
  PYTEST=.venv/bin/pytest
  AUDIT=.venv/bin/pip-audit
fi

fail=0
run() {
  name=$1
  shift
  log="$(mktemp)"
  if "$@" >"$log" 2>&1; then
    echo "CHECK ${name} PASS"
  else
    echo "CHECK ${name} FAIL"
    tail -n 15 "$log"
    fail=1
  fi
  rm -f "$log"
}

run ruff-check "$RUFF" check .
run ruff-format "$RUFF" format --check .
run mypy "$MYPY" --strict src tests
run pytest "$PYTEST" -q

if [ "$(uname -s)" = "Linux" ]; then
  run coverage "$PY" -m coverage run -m pytest -q
  run coverage-report "$PY" -m coverage report
else
  echo "CHECK coverage SKIP (POSIX lanes)"
fi

run audit "$AUDIT" --progress-spinner off

if [ "$fail" -eq 0 ]; then
  echo "RESULT: PASS"
else
  echo "RESULT: FAIL"
  exit 1
fi
