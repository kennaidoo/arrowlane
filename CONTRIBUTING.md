# Contributing

This repository is the Python implementation of arrowlane. The Rust and Zig
implementations live in separate repositories.

## Before you start

- Open an issue for behaviour changes, new lanes, or wire-format changes.
- Keep a change small and focused. One concern per pull request.
- Do not change a lane id. Add a new id instead.
- Do not publish a performance claim without a reproducible measurement.

## Local checks

```bash
uv sync --frozen --extra dev --extra server
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
bash scripts/gate.sh
```

A change is complete only when `bash scripts/gate.sh` prints `RESULT: PASS`.

## Documentation

Update the page that describes the behaviour you changed. Keep `docs/ai/` and
`llms.txt` accurate for agents.

## Commit messages

Use `type(scope): description`, for example:

```text
fix(frame): reject a truncated payload before allocation
```

## Security

Do not report a vulnerability in a public issue. Follow `SECURITY.md`.
