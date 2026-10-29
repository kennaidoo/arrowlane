# ADR 0004: the Python 3.14 floor

Status: accepted.

## Context

The package targets containerized Python apps. The standard library gained the
features the lanes use only in Python 3.14.

## Decision

Require Python 3.14 or newer. The code uses `compression.zstd` for the zstd lane
and `uuid.uuid7()` for segment names.

## Consequences

Python 3.13 and older cannot install the package. The alternative is the
`zstandard` package plus `uuid4`, which adds a binary dependency and a weaker
name guarantee. The floor is recorded in `pyproject.toml` and tested on 3.14 and
3.15.
