# Agent guide

Read CONTRIBUTING.md before changing code.

## Commands

- Install: `uv sync --frozen --extra dev --extra server`
- Test: `uv run pytest`
- Lint: `uv run ruff check .`
- Format check: `uv run ruff format --check .`
- Types: `uv run mypy src`
- Full gate: `bash scripts/gate.sh`

## Boundaries

- Do not create an issue or pull request unless the human asks.
- Do not change a lane id.
- Do not commit generated files or benchmark results.
- Do not run benchmarks in CI.
- Keep changes focused. Report changed files, checks run and open risks.

## References

- `docs/ai/operating-guide.md` for the full development guide.
- `docs/ai/manifest.json`, `docs/ai/quickstart.md` and `docs/ai/api.md` for the public contract.
- `llms.txt` for the short retrieval entry point.
