"""Compute the naive CRPS baseline for v1.1 CRPSS reporting.

The baseline is the dataset-mean predictor specified in
docs/CALIBRATION_METHODOLOGY_V1_1.md section 4.1. Each case receives the
same point prediction: the mean realised annual electricity across the
evaluation set. CRPS for a single-point ensemble is equivalent to absolute
error, but this script uses properscoring.crps_ensemble for consistency with
run_calibration_eval.py.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from properscoring import crps_ensemble


DEFAULT_INPUT = Path("data/heatpumpmonitor/eval_cases.json")
DEFAULT_OUTPUT = Path("data/heatpumpmonitor/crpss_baseline.json")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute dataset-mean CRPS baseline for CRPSS reporting."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Evaluation cases JSON. Default: {DEFAULT_INPUT}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output JSON path. Default: {DEFAULT_OUTPUT}",
    )
    return parser.parse_args()


def _load_realised(path: Path) -> np.ndarray:
    if not path.exists():
        raise FileNotFoundError(
            f"Evaluation cases file not found: {path}. "
            "Run backend/scripts/build_eval_dataset.py first."
        )
    cases: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    return np.asarray(
        [float(case["realised"]["annual_elec_kwh"]) for case in cases],
        dtype=float,
    )


def main() -> None:
    args = _parse_args()
    realised = _load_realised(args.input)
    mean_realised = float(np.mean(realised))
    point_ensemble = np.asarray([mean_realised], dtype=float)
    crps_values = [
        float(crps_ensemble(observation, point_ensemble)) for observation in realised
    ]
    mean_crps_baseline = float(np.mean(crps_values))

    result = {
        "n_cases": int(len(realised)),
        "dataset_mean_realised_kwh": mean_realised,
        "mean_crps_baseline_kwh": mean_crps_baseline,
        "computed_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": args.input.as_posix(),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"n_cases: {result['n_cases']}")
    print(f"dataset_mean_realised_kwh: {mean_realised:.6f}")
    print(f"mean_crps_baseline_kwh: {mean_crps_baseline:.6f}")
    print(f"wrote: {args.output}")


if __name__ == "__main__":
    main()
