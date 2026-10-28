"""Fit the lane cost model from the latest codec probe result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

MIN_R2_ENCODE = 0.99
MIN_R2_DECODE = 0.90
MAX_RATIO_SPREAD = 1.20
MAX_ERROR_AT_LARGEST = 0.25
MODEL = Path("src/arrowlane/costmodel.json")


def fit(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Least squares fit of y = intercept + slope * x, with R squared."""
    design = np.vstack([np.ones(len(xs)), np.asarray(xs, dtype=float)]).T
    solution, *_ = np.linalg.lstsq(design, np.asarray(ys, dtype=float), rcond=None)
    intercept = float(solution[0])
    slope = float(solution[1])
    predicted = design @ solution
    residual = float(((np.asarray(ys) - predicted) ** 2).sum())
    total = float(((np.asarray(ys) - np.mean(ys)) ** 2).sum())
    r2 = 1.0 if total == 0.0 else 1.0 - residual / total
    return intercept, slope, r2


def slope_with_fixed(xs: list[float], ys: list[float], fixed: float) -> float:
    """Least squares slope when the fixed term is held."""
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    return float((x * (y - fixed)).sum() / (x * x).sum())


def calibrate(payload: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Return a complete cost model document."""
    records = payload["records"]
    lanes = sorted({record["lane"] for record in records})
    fitted: dict[str, Any] = {}
    ratio_spreads: dict[str, float] = {}
    prediction_errors: dict[str, dict[str, float]] = {}
    for lane in lanes:
        rows = [record for record in records if record["lane"] == lane]
        mb = [record["arrow_bytes"] / 1e6 for record in rows]
        enc_fixed, enc_slope, enc_r2 = fit(mb, [record["enc_ms"] for record in rows])
        dec_fixed, dec_slope, dec_r2 = fit(mb, [record["dec_ms"] for record in rows])
        if enc_r2 < MIN_R2_ENCODE or dec_r2 < MIN_R2_DECODE:
            raise SystemExit(f"{lane}: poor fit, enc R2={enc_r2:.4f} dec R2={dec_r2:.4f}")
        if enc_slope < 0 or dec_slope < 0:
            raise SystemExit(f"{lane}: negative slope, the measurements are not usable")
        ratios = [record["wire_bytes"] / record["arrow_bytes"] for record in rows]
        spread = max(ratios) / min(ratios)
        if spread > MAX_RATIO_SPREAD:
            raise SystemExit(f"{lane}: ratio spread {spread:.3f} exceeds {MAX_RATIO_SPREAD}")
        ratio_spreads[lane] = round(spread, 6)
        largest = max(rows, key=lambda record: record["arrow_bytes"])
        ratio = largest["wire_bytes"] / largest["arrow_bytes"]
        seed_fixed = float(current["lanes"][lane]["fixed_ms"])
        fixed = max(enc_fixed + dec_fixed, seed_fixed)
        total = [record["enc_ms"] + record["dec_ms"] for record in rows]
        total_slope = slope_with_fixed(mb, total, fixed)
        share = enc_slope / (enc_slope + dec_slope)
        lane_errors: dict[str, float] = {}
        for record in rows:
            predicted = fixed + total_slope * (record["arrow_bytes"] / 1e6)
            actual = record["enc_ms"] + record["dec_ms"]
            lane_errors[str(record["rows"])] = round(abs(predicted - actual) / actual, 6)
        largest_error = lane_errors[str(largest["rows"])]
        if largest_error > MAX_ERROR_AT_LARGEST:
            raise SystemExit(f"{lane}: largest-shape error {largest_error:.3f}")
        prediction_errors[lane] = lane_errors
        fitted[lane] = {
            "fixed_ms": round(fixed, 6),
            "enc_ms_per_mb": round(total_slope * share, 6),
            "dec_ms_per_mb": round(total_slope * (1.0 - share), 6),
            "ratio": round(ratio, 6),
        }
        print(
            f"{lane}: fixed={fitted[lane]['fixed_ms']:.6f} "
            f"enc={fitted[lane]['enc_ms_per_mb']:.6f} "
            f"dec={fitted[lane]['dec_ms_per_mb']:.6f} "
            f"ratio={fitted[lane]['ratio']:.6f} "
            f"largest_error={largest_error:.4f}"
        )
    fitted["shm"] = current["lanes"]["shm"]
    provenance = {
        "platform": payload["provenance"]["platform"],
        "python": payload["provenance"]["python"],
        "pyarrow": payload["provenance"]["pyarrow"],
        "measured_at": payload["provenance"]["measured_at"],
        "method": (
            "bench/probes/codec_probe.py, "
            f"{len(payload['provenance']['shapes'])} shapes x 8 columns, "
            f"median of {payload['provenance']['repeats']}"
        ),
        "source": "bench",
        "commit": payload["provenance"]["commit"],
        "command": payload["provenance"]["command"],
        "shapes": payload["provenance"]["shapes"],
        "repeats": payload["provenance"]["repeats"],
        "wire_source": "estimate",
        "fixed_source": "max(fitted intercept, seed estimate)",
        "slope_source": "bench, fixed term held",
        "estimated_lanes": ["shm"],
        "ratio_source": "largest shape",
        "ratio_spreads": ratio_spreads,
        "prediction_errors": prediction_errors,
        "max_prediction_error": max(max(errors.values()) for errors in prediction_errors.values()),
    }
    return {
        "schema_version": 1,
        "provenance": provenance,
        "wire_us_per_mb": current["wire_us_per_mb"],
        "lanes": fitted,
    }


def main() -> int:
    """Read a probe result, fit, and write the shipped model."""
    parser = argparse.ArgumentParser()
    parser.add_argument("result", type=Path, nargs="?")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = args.result
    if result is None:
        candidates = sorted(Path("bench/results").glob("codec-*.json"))
        if not candidates:
            raise SystemExit("no probe result found, run bench/probes/codec_probe.py")
        result = candidates[-1]
    payload = json.loads(result.read_text(encoding="utf-8"))
    current = json.loads(MODEL.read_text(encoding="utf-8"))
    model = calibrate(payload, current)
    text = json.dumps(model, indent=2) + "\n"
    if args.write:
        MODEL.write_text(text, encoding="utf-8")
        print(f"wrote {MODEL}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
