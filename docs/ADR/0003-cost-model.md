# ADR 0003: the cost model

Status: accepted.

## Context

The selector needs a cost per lane. Absolute milliseconds do not survive a
different host, and a model fitted only on large tables mispredicts small ones.

## Decision

- Measure four shapes from 1,000 to 500,000 rows, eight column types, median of
  three runs.
- Fit `time = fixed + slope * megabytes` by least squares.
- Set the fixed term to the larger of the fitted intercept and the earlier seed
  estimate. The intercept is not identifiable below one millisecond.
- Take the wire ratio from the largest shape. The compression ratio changes with
  size; the spread is recorded in the provenance.
- Gate calibration on encode R2 at or above 0.99, decode R2 at or above 0.90, a
  wire ratio spread at or below 1.20, and an error at the largest shape at or
  below 25 percent.
- Record every residual in the model provenance. Do not claim a better fit than
  the data supports.

## Consequences

The model predicts the largest shape within 0.5 percent. Middle shapes can be
off by up to 69 percent because the JSON cost changes with cache residency. The
selector falls back to JSON when the predicted gain is under 10 percent, and the
benchmark gate uses the same eight-column shape as the calibration.

Network terms are estimates. They sit beside measured slopes under a separate
`wire_source` key. A host that differs from the provenance should recalibrate.
