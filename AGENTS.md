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

## Cross-repository check

The Python package and the C++ port must agree on bytes. The C++ test writes a
dictionary stream, and the Python test reads it:

    # in arrowlane-cpp, build and test everything
    scripts/gate.cmd

    # in arrowlane, point at the fixture the C++ test wrote
    ARROWLANE_CPP_DICT=<path to arrowlane-cpp>/build/dict_cpp.arrows \
      uv run --no-sync pytest tests/test_dictionary_interop.py -q

Expected: `1 passed`, not `1 skipped`. A skip means the environment variable did
not reach the test, so the check did not run.
