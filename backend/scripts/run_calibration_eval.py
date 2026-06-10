"""Run the pre-registered seven-run HeatpumpMonitor calibration evaluation.

This script implements docs/CALIBRATION_METHODOLOGY.md. It reads the prepared
eval_cases.json dataset, runs the forecast model under the seven ablation
conditions, and writes predictions, a flat CSV, and a methodology-shaped report.
It does not build the dataset; use build_eval_dataset.py first.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from collections import Counter
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

import httpx
import numpy as np
from properscoring import crps_ensemble
from scipy import stats

from app.forecast import climate
from app.forecast.monte_carlo import forecast_from_request
from app.models import (
    DhwInput,
    ForecastRequest,
    HeatPumpInput,
    PropertyInput,
    TariffScenarioInput,
)

INPUT_PATH = Path("data/heatpumpmonitor/eval_cases.json")
OUTPUT_DIR = Path("data/heatpumpmonitor")
CLIMATE_CACHE_DIR = OUTPUT_DIR / "climate_cache"
PREDICTIONS_PATH = OUTPUT_DIR / "calibration_predictions.json"
PARTIAL_PREDICTIONS_PATH = OUTPUT_DIR / "calibration_predictions.partial.json"
REPORT_PATH = OUTPUT_DIR / "calibration_report.md"
ERRORS_CSV_PATH = OUTPUT_DIR / "calibration_errors.csv"

METHODOLOGY_COMMIT = "6b1a3ab523c032944bbc88202c57be7ef5b44baa"
DEFAULT_RANDOM_SEED = 20260609
POSTCODE_PLACEHOLDER = "AA1 1AA"
SAVE_EVERY_CASES = 25
SLEEP_SECONDS_BETWEEN_CASES = 0.1
FIXED_SCOP_PROXY = 3.5
TARIFF_UNIT_RATE_P_PER_KWH = 27
TARIFF_STANDING_CHARGE_P_PER_DAY = 53
ALPHA_80 = 0.2

RUN_ORDER = ["A-full", "A-subset", "B", "C", "D", "E", "F"]
MEASURED_SUBSET_RUNS = {"A-subset", "B", "C", "D", "E"}
FULL_SET_RUNS = {"A-full", "F"}
SENSITIVITY_OCCUPANTS = [1, 2, 3, 4, 5]

SSL_VERIFY_FALSE = False


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run HeatpumpMonitor seven-run calibration evaluation.",
    )
    parser.add_argument(
        "--use-frozen-snapshot",
        action="store_true",
        help="Record that eval_cases.json was built from a frozen snapshot.",
    )
    parser.add_argument(
        "--snapshot-date",
        metavar="YYYYMMDD",
        help="Frozen snapshot date recorded in the evaluation report.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=DEFAULT_RANDOM_SEED,
        help=f"Base random seed. Default: {DEFAULT_RANDOM_SEED}.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit evaluation to the first N cases. For testing only.",
    )
    args = parser.parse_args()
    if args.use_frozen_snapshot and not args.snapshot_date:
        parser.error("--use-frozen-snapshot requires --snapshot-date YYYYMMDD")
    if args.snapshot_date and not args.use_frozen_snapshot:
        parser.error("--snapshot-date is only valid with --use-frozen-snapshot")
    return args


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp_path, path)


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_measured_subset(case: dict[str, Any]) -> bool:
    overrides = case["best_info_overrides"]
    return (
        overrides["heat_loss_design_w_measured"] is not None
        and overrides["t_internal_c_measured"] is not None
    )


def _strict_zero(case: dict[str, Any]) -> bool:
    realised = case["realised"]
    return realised["cooling_elec_kwh"] == 0 and realised["immersion_kwh"] == 0


def _spf_band(spf: float) -> str:
    if spf < 2.5:
        return "<2.5"
    if spf < 3.5:
        return "2.5-3.5"
    if spf < 4.5:
        return "3.5-4.5"
    return ">4.5"


@contextmanager
def _patched_geocode(latitude: float, longitude: float) -> Iterator[None]:
    original_geocode = climate.geocode_postcode

    def geocode_postcode(_postcode: str) -> tuple[float, float]:
        return latitude, longitude

    climate.geocode_postcode = geocode_postcode
    try:
        yield
    finally:
        climate.geocode_postcode = original_geocode


@contextmanager
def _patched_httpx_verify_false_if_needed() -> Iterator[None]:
    if not SSL_VERIFY_FALSE:
        yield
        return

    original_client = httpx.Client

    def client_with_verify_false(*args: Any, **kwargs: Any) -> httpx.Client:
        kwargs["verify"] = False
        return original_client(*args, **kwargs)

    httpx.Client = client_with_verify_false
    try:
        yield
    finally:
        httpx.Client = original_client


def _forecast_with_ssl_fallback(
    request: ForecastRequest,
    *,
    latitude: float,
    longitude: float,
    random_seed: int,
) -> Any:
    global SSL_VERIFY_FALSE
    with _patched_geocode(latitude, longitude):
        with _patched_httpx_verify_false_if_needed():
            try:
                return forecast_from_request(
                    request,
                    cache_dir=CLIMATE_CACHE_DIR,
                    random_seed=random_seed,
                )
            except httpx.ConnectError as exc:
                if "CERTIFICATE_VERIFY_FAILED" not in repr(exc):
                    raise
                if not SSL_VERIFY_FALSE:
                    print(
                        "WARNING: local SSL trust store rejected Open-Meteo; "
                        "retrying with httpx verify=False for this script run.",
                        file=sys.stderr,
                    )
                SSL_VERIFY_FALSE = True
        with _patched_httpx_verify_false_if_needed():
            return forecast_from_request(
                request,
                cache_dir=CLIMATE_CACHE_DIR,
                random_seed=random_seed,
            )


def _run_applies(case: dict[str, Any], run_name: str) -> bool:
    if run_name in FULL_SET_RUNS:
        return True
    if run_name in MEASURED_SUBSET_RUNS:
        return _is_measured_subset(case)
    raise ValueError(f"unknown run: {run_name}")


def _run_inputs(
    case: dict[str, Any],
    run_name: str,
) -> tuple[float, float, float]:
    mcs = case["mcs_inputs"]
    overrides = case["best_info_overrides"]
    realised = case["realised"]
    mcs_hlc = float(mcs["heat_loss_design_w"])
    mcs_indoor = float(mcs["t_internal_c"])
    realised_spf = float(realised["spf"])

    if run_name == "A-full" or run_name == "A-subset":
        return mcs_hlc, mcs_indoor, realised_spf
    if run_name == "F":
        return mcs_hlc, mcs_indoor, FIXED_SCOP_PROXY

    measured_hlc_raw = overrides["heat_loss_design_w_measured"]
    measured_indoor_raw = overrides["t_internal_c_measured"]
    if measured_hlc_raw is None or measured_indoor_raw is None:
        raise ValueError(
            f"Run {run_name} requires measured HLC and measured indoor temperature; "
            f"this case is not in the measured-input subset."
        )
    measured_hlc = float(measured_hlc_raw)
    measured_indoor = float(measured_indoor_raw)

    if run_name == "B":
        return measured_hlc, measured_indoor, realised_spf
    if run_name == "C":
        return measured_hlc, measured_indoor, FIXED_SCOP_PROXY
    if run_name == "D":
        return mcs_hlc, measured_indoor, realised_spf
    if run_name == "E":
        return measured_hlc, mcs_indoor, realised_spf
    raise ValueError(f"unknown run: {run_name}")


def _build_request(
    case: dict[str, Any],
    run_name: str,
    *,
    occupants: int = 3,
) -> ForecastRequest:
    mcs = case["mcs_inputs"]
    heat_loss_design_w, t_internal_c, scop = _run_inputs(case, run_name)
    raw_cylinder_l = mcs.get("cylinder_l")
    cylinder_l = 200 if raw_cylinder_l is None or raw_cylinder_l <= 0 else raw_cylinder_l

    return ForecastRequest(
        property=PropertyInput(
            floor_area_m2=float(mcs["floor_area_m2"]),
            hlc_w_per_k=None,
            heat_loss_design_w=heat_loss_design_w,
            t_design_outdoor_c=float(mcs["t_design_outdoor_c"]),
            t_internal_c=t_internal_c,
            t_base_c=15.5,
            postcode=POSTCODE_PLACEHOLDER,
        ),
        heat_pump=HeatPumpInput(
            scop=scop,
            t_flow_sh_c=float(mcs["t_flow_sh_c"]),
            t_design_outdoor_c=float(mcs["t_design_outdoor_c"]),
            defrost_penalty_peak_pct=0.0,
        ),
        dhw=DhwInput(
            occupants=occupants,
            cylinder_l=float(cylinder_l),
            t_setpoint_c=48,
            t_flow_dhw_c=52,
        ),
        tariff_scenarios=[
            TariffScenarioInput(
                name="central",
                standing_charge_p_per_day=TARIFF_STANDING_CHARGE_P_PER_DAY,
                unit_rate_p_per_kwh=TARIFF_UNIT_RATE_P_PER_KWH,
            )
        ],
    )


def _run_forecast(
    case: dict[str, Any],
    run_name: str,
    *,
    random_seed: int,
    occupants: int = 3,
) -> dict[str, Any]:
    response = _forecast_with_ssl_fallback(
        _build_request(case, run_name, occupants=occupants),
        latitude=float(case["latitude"]),
        longitude=float(case["longitude"]),
        random_seed=random_seed,
    )
    realised = float(case["realised"]["annual_elec_kwh"])
    draws = np.asarray(response.draws_kwh, dtype=float)
    p10 = float(response.total.p10_kwh)
    p50 = float(response.total.p50_kwh)
    p90 = float(response.total.p90_kwh)
    error_kwh = p50 - realised
    error_pct = 100 * error_kwh / realised
    return {
        "predicted_p10_kwh": p10,
        "predicted_p50_kwh": p50,
        "predicted_p90_kwh": p90,
        "interval_width_kwh": p90 - p10,
        "fitted_eta": float(response.fitted_eta),
        "error_kwh": float(error_kwh),
        "error_pct": float(error_pct),
        "in_p10_p90_band": bool(p10 <= realised <= p90),
        "pit": float(np.mean(draws < realised)),
        "draws_kwh": [float(value) for value in draws],
        "warnings": list(response.warnings),
    }


def _evaluate_case(case: dict[str, Any], random_seed: int) -> dict[str, Any]:
    case_seed = random_seed * 1000 + int(case["system_id"])
    runs: dict[str, Any] = {}
    for run_name in RUN_ORDER:
        if _run_applies(case, run_name):
            runs[run_name] = _run_forecast(case, run_name, random_seed=case_seed)

    return {
        "system_id": int(case["system_id"]),
        "location": case["location"],
        "hp_manufacturer": case["hp_manufacturer"],
        "hp_model": case["hp_model"],
        "property_type": case["property_type"],
        "age": case["age"],
        "insulation": case["insulation"],
        "data_days": float(case["data_days"]),
        "realised_annual_elec_kwh": float(case["realised"]["annual_elec_kwh"]),
        "realised_spf": float(case["realised"]["spf"]),
        "strict_zero_cooling_immersion": _strict_zero(case),
        "measured_input_subset": _is_measured_subset(case),
        "case_seed": case_seed,
        "runs": runs,
    }


def _evaluate_dhw_sensitivity(
    cases: list[dict[str, Any]],
    random_seed: int,
) -> dict[str, dict[str, Any]]:
    measured_cases = [case for case in cases if _is_measured_subset(case)]
    sensitivity: dict[str, dict[str, Any]] = {}
    for occupants in SENSITIVITY_OCCUPANTS:
        records = []
        for case in measured_cases:
            try:
                run = _run_forecast(
                    case,
                    "B",
                    random_seed=random_seed * 1000 + int(case["system_id"]),
                    occupants=occupants,
                )
                records.append(
                    {
                        "system_id": case["system_id"],
                        "realised_annual_elec_kwh": case["realised"]["annual_elec_kwh"],
                        "runs": {f"B-occupants-{occupants}": run},
                    }
                )
            except Exception as exc:  # noqa: BLE001
                print(
                    f"DHW sensitivity failed for system_id={case['system_id']} "
                    f"occupants={occupants}: {exc!r}",
                    file=sys.stderr,
                )
        run_key = f"B-occupants-{occupants}"
        sensitivity[str(occupants)] = _aggregate_metrics(records, run_key)
    return sensitivity


def _run_records(
    predictions: list[dict[str, Any]],
    run_name: str,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    return [
        (record, record["runs"][run_name])
        for record in predictions
        if run_name in record.get("runs", {})
    ]


def _wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total == 0:
        return 0.0, 0.0
    phat = successes / total
    denominator = 1 + z**2 / total
    centre = (phat + z**2 / (2 * total)) / denominator
    half_width = (
        z
        * np.sqrt((phat * (1 - phat) + z**2 / (4 * total)) / total)
        / denominator
    )
    return 100 * max(0.0, centre - half_width), 100 * min(1.0, centre + half_width)


def _trimmed_mean(values: np.ndarray, trim_fraction: float = 0.01) -> float:
    if values.size == 0:
        return float("nan")
    sorted_values = np.sort(values)
    trim = int(np.floor(trim_fraction * sorted_values.size))
    if trim == 0 or sorted_values.size <= 2 * trim:
        return float(np.mean(sorted_values))
    return float(np.mean(sorted_values[trim:-trim]))


def _interval_score(lower: np.ndarray, upper: np.ndarray, realised: np.ndarray) -> np.ndarray:
    below = realised < lower
    above = realised > upper
    return (
        (upper - lower)
        + (2 / ALPHA_80) * (lower - realised) * below
        + (2 / ALPHA_80) * (realised - upper) * above
    )


def _aggregate_metrics(
    predictions: list[dict[str, Any]],
    run_name: str,
) -> dict[str, Any]:
    pairs = _run_records(predictions, run_name)
    if not pairs:
        return {
            "cases": 0,
            "mae_kwh": float("nan"),
            "mape": float("nan"),
            "mdape": float("nan"),
            "trimmed_mape": float("nan"),
            "median_signed_error_pct": float("nan"),
            "p10_signed_error_pct": float("nan"),
            "p90_signed_error_pct": float("nan"),
            "coverage_pct": float("nan"),
            "wilson_95_ci_lower": float("nan"),
            "wilson_95_ci_upper": float("nan"),
            "pit_bins": [float("nan")] * 10,
            "ks_p_value": float("nan"),
            "median_interval_width_kwh": float("nan"),
            "median_interval_width_pct": float("nan"),
            "mean_interval_score": float("nan"),
            "mean_crps": float("nan"),
        }

    realised = np.asarray([pair[0]["realised_annual_elec_kwh"] for pair in pairs], dtype=float)
    p10 = np.asarray([pair[1]["predicted_p10_kwh"] for pair in pairs], dtype=float)
    p50 = np.asarray([pair[1]["predicted_p50_kwh"] for pair in pairs], dtype=float)
    p90 = np.asarray([pair[1]["predicted_p90_kwh"] for pair in pairs], dtype=float)
    errors_kwh = p50 - realised
    errors_pct = 100 * errors_kwh / realised
    abs_errors_pct = np.abs(errors_pct)
    in_band = np.asarray([pair[1]["in_p10_p90_band"] for pair in pairs], dtype=bool)
    pits = np.asarray([pair[1]["pit"] for pair in pairs], dtype=float)
    interval_widths = p90 - p10
    successes = int(np.sum(in_band))
    wilson_low, wilson_high = _wilson_interval(successes, len(pairs))
    pit_bins = np.histogram(pits, bins=10, range=(0, 1))[0] / len(pairs)
    crps_values = [
        float(crps_ensemble(obs, np.asarray(pair[1]["draws_kwh"], dtype=float)))
        for obs, pair in zip(realised, pairs, strict=True)
    ]

    return {
        "cases": len(pairs),
        "mae_kwh": float(np.mean(np.abs(errors_kwh))),
        "mape": float(np.mean(abs_errors_pct)),
        "mdape": float(np.median(abs_errors_pct)),
        "trimmed_mape": _trimmed_mean(abs_errors_pct),
        "median_signed_error_pct": float(np.median(errors_pct)),
        "p10_signed_error_pct": float(np.percentile(errors_pct, 10)),
        "p90_signed_error_pct": float(np.percentile(errors_pct, 90)),
        "coverage_pct": float(100 * np.mean(in_band)),
        "wilson_95_ci_lower": wilson_low,
        "wilson_95_ci_upper": wilson_high,
        "pit_bins": [float(value) for value in pit_bins],
        "ks_p_value": float(stats.kstest(pits, "uniform").pvalue),
        "median_interval_width_kwh": float(np.median(interval_widths)),
        "median_interval_width_pct": float(100 * np.median(interval_widths) / np.median(realised)),
        "mean_interval_score": float(np.mean(_interval_score(p10, p90, realised))),
        "mean_crps": float(np.mean(crps_values)),
    }


def _aggregate_all(predictions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {run_name: _aggregate_metrics(predictions, run_name) for run_name in RUN_ORDER}


def _distribution(values: list[str]) -> dict[str, float]:
    total = len(values)
    counts = Counter(value or "unknown" for value in values)
    return {key: count / total for key, count in counts.items()} if total else {}


def _max_proportion_delta(full: dict[str, float], subset: dict[str, float]) -> float:
    keys = set(full) | set(subset)
    return max((abs(full.get(key, 0.0) - subset.get(key, 0.0)) for key in keys), default=0.0)


def _demographic_comparison(cases: list[dict[str, Any]]) -> dict[str, Any]:
    subset = [case for case in cases if _is_measured_subset(case)]
    fields = ["age", "insulation", "property_type"]
    comparison = {}
    for field in fields:
        full_dist = _distribution([case[field] for case in cases])
        subset_dist = _distribution([case[field] for case in subset])
        comparison[field] = {
            "max_proportion_delta_pct": 100 * _max_proportion_delta(full_dist, subset_dist),
            "eligible_distribution": full_dist,
            "measured_subset_distribution": subset_dist,
        }
    return comparison


def _slice_rows(
    predictions: list[dict[str, Any]],
    field_name: str,
    value_fn: Any,
) -> list[dict[str, Any]]:
    values = sorted({value_fn(record) for record in predictions})
    rows = []
    for value in values:
        slice_predictions = [record for record in predictions if value_fn(record) == value]
        metrics = _aggregate_metrics(slice_predictions, "A-full")
        rows.append(
            {
                "slice_type": field_name,
                "slice_value": value,
                "case_count": metrics["cases"],
                "coverage_pct": metrics["coverage_pct"],
                "wilson_95_ci_lower": metrics["wilson_95_ci_lower"],
                "wilson_95_ci_upper": metrics["wilson_95_ci_upper"],
                "mape": metrics["mape"],
                "median_signed_error_pct": metrics["median_signed_error_pct"],
                "median_interval_width_pct": metrics["median_interval_width_pct"],
                "flag": "insufficient sample size" if metrics["cases"] < 10 else "",
            }
        )
    return rows


def _slice_analyses(predictions: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "age": _slice_rows(predictions, "age", lambda record: record["age"] or "unknown"),
        "insulation": _slice_rows(
            predictions,
            "insulation",
            lambda record: record["insulation"] or "unknown",
        ),
        "realised_spf_band": _slice_rows(
            predictions,
            "realised_spf_band",
            lambda record: _spf_band(float(record["realised_spf"])),
        ),
        "property_type": _slice_rows(
            predictions,
            "property_type",
            lambda record: record["property_type"] or "unknown",
        ),
    }


def _strict_zero_metrics(predictions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    strict_predictions = [
        record for record in predictions if record["strict_zero_cooling_immersion"]
    ]
    return _aggregate_all(strict_predictions)


def _format_float(value: float, digits: int = 1) -> str:
    if value is None or np.isnan(value):
        return "n/a"
    return f"{value:.{digits}f}"


def _metrics_table(metrics_by_run: dict[str, dict[str, Any]]) -> list[str]:
    lines = [
        "| Run | Cases | Coverage % | Wilson 95% CI | MAPE % | MdAPE % | Trimmed MAPE % | Median signed error % | Median width % | Mean CRPS |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for run_name in RUN_ORDER:
        metrics = metrics_by_run[run_name]
        ci = (
            f"{_format_float(metrics['wilson_95_ci_lower'])}-"
            f"{_format_float(metrics['wilson_95_ci_upper'])}"
        )
        lines.append(
            f"| {run_name} | {metrics['cases']} | {_format_float(metrics['coverage_pct'])} | "
            f"{ci} | {_format_float(metrics['mape'])} | {_format_float(metrics['mdape'])} | "
            f"{_format_float(metrics['trimmed_mape'])} | "
            f"{_format_float(metrics['median_signed_error_pct'])} | "
            f"{_format_float(metrics['median_interval_width_pct'])} | "
            f"{_format_float(metrics['mean_crps'])} |"
        )
    return lines


def _coverage_delta(
    metrics_by_run: dict[str, dict[str, Any]],
    better: str,
    baseline: str,
) -> float:
    return metrics_by_run[better]["coverage_pct"] - metrics_by_run[baseline]["coverage_pct"]


def _comparison_lines(metrics_by_run: dict[str, dict[str, Any]]) -> list[str]:
    comparisons = [
        ("B - A-subset", "B", "A-subset", ">= 30 pp means HLC calibration is highest-impact v2 feature"),
        ("B - D", "B", "D", ">= 20 pp means MCS HLC substitution materially degrades accuracy"),
        ("B - E", "B", "E", ">= 15 pp means indoor-temperature substitution materially degrades accuracy"),
        ("B - C", "B", "C", ">= 20 pp means fixed generic SCOP proxy is inadequate"),
        ("F vs A-full", "F", "A-full", "Run F is realistic-user end-to-end vs oracle-SPF baseline"),
    ]
    lines = [
        "| Comparison | Coverage delta | Threshold / interpretation |",
        "|---|---:|---|",
    ]
    for label, better, baseline, threshold in comparisons:
        delta = _coverage_delta(metrics_by_run, better, baseline)
        lines.append(f"| {label} | {_format_float(delta)} pp | {threshold} |")
    return lines


def _band(value: float, validated: float, adequate: float, lower_is_better: bool) -> str:
    if lower_is_better:
        if value <= validated:
            return "Validated"
        if value <= adequate:
            return "Adequate"
        return "Inadequate"
    if value >= validated:
        return "Validated"
    if value >= adequate:
        return "Adequate"
    return "Inadequate"


def _run_b_validation(metrics_by_run: dict[str, dict[str, Any]]) -> list[str]:
    b = metrics_by_run["B"]
    rows = [
        (
            "Coverage of 80% interval",
            b["coverage_pct"],
            _band(b["coverage_pct"], 75, 60, lower_is_better=False),
        ),
        ("MAPE", b["mape"], _band(b["mape"], 12, 20, lower_is_better=True)),
        (
            "Median interval width as % of median realised",
            b["median_interval_width_pct"],
            _band(b["median_interval_width_pct"], 50, 80, lower_is_better=True),
        ),
    ]
    lines = ["| Metric | Value | Band |", "|---|---:|---|"]
    lines.extend(f"| {name} | {_format_float(value)} | {band} |" for name, value, band in rows)
    return lines


def _run_f_validation(metrics_by_run: dict[str, dict[str, Any]]) -> str:
    f = metrics_by_run["F"]
    if f["coverage_pct"] >= 60 and f["mape"] <= 25:
        return "Run F passes section 7.4: realistic-user product is viable with documented uncertainty disclosure."
    return "Run F fails section 7.4: realistic-user product is not viable in its current form; require calibration data as gating input."


def _sharpness_lines(metrics_by_run: dict[str, dict[str, Any]]) -> list[str]:
    lines = ["| Run | Median width % | Interpretation |", "|---|---:|---|"]
    for run_name in RUN_ORDER:
        width = metrics_by_run[run_name]["median_interval_width_pct"]
        if width <= 25:
            interpretation = "Sharp"
        elif width <= 50:
            interpretation = "Usable but broad"
        else:
            interpretation = "Too wide for individual decisions"
        lines.append(f"| {run_name} | {_format_float(width)} | {interpretation} |")
    return lines


def _pit_lines(metrics_by_run: dict[str, dict[str, Any]]) -> list[str]:
    lines = ["| Run | KS p-value | PIT bins |", "|---|---:|---|"]
    for run_name in RUN_ORDER:
        metrics = metrics_by_run[run_name]
        bins = ", ".join(_format_float(value, 3) for value in metrics["pit_bins"])
        lines.append(f"| {run_name} | {_format_float(metrics['ks_p_value'], 4)} | {bins} |")
    return lines


def _slice_table(slice_rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Slice | Cases | Coverage % | Wilson 95% CI | MAPE % | Median signed error % | Median width % | Flag |",
        "|---|---:|---:|---|---:|---:|---:|---|",
    ]
    for row in slice_rows:
        ci = f"{_format_float(row['wilson_95_ci_lower'])}-{_format_float(row['wilson_95_ci_upper'])}"
        lines.append(
            f"| {row['slice_value']} | {row['case_count']} | "
            f"{_format_float(row['coverage_pct'])} | {ci} | {_format_float(row['mape'])} | "
            f"{_format_float(row['median_signed_error_pct'])} | "
            f"{_format_float(row['median_interval_width_pct'])} | {row['flag']} |"
        )
    return lines


def _dhw_decision(sensitivity: dict[str, dict[str, Any]]) -> str:
    mapes = [metrics["mape"] for metrics in sensitivity.values() if not np.isnan(metrics["mape"])]
    if not mapes:
        return "DHW sensitivity could not be evaluated."
    movement = max(mapes) - min(mapes)
    if movement < 5:
        return f"Section 7.8: fixed 3-occupant assumption is acceptable (MAPE movement {movement:.1f} pp)."
    if movement <= 10:
        return f"Section 7.8: acceptable but DHW uncertainty should be propagated in v2 (MAPE movement {movement:.1f} pp)."
    return f"Section 7.8: occupancy is critical and v1 frontend must require it (MAPE movement {movement:.1f} pp)."


def _dhw_lines(sensitivity: dict[str, dict[str, Any]]) -> list[str]:
    lines = ["| Occupants | Cases | Coverage % | MAPE % |", "|---:|---:|---:|---:|"]
    for occupants in map(str, SENSITIVITY_OCCUPANTS):
        metrics = sensitivity[occupants]
        lines.append(
            f"| {occupants} | {metrics['cases']} | "
            f"{_format_float(metrics['coverage_pct'])} | {_format_float(metrics['mape'])} |"
        )
    lines.append("")
    lines.append(_dhw_decision(sensitivity))
    return lines


def _strict_zero_lines(
    headline: dict[str, dict[str, Any]],
    strict_zero: dict[str, dict[str, Any]],
) -> list[str]:
    lines = [
        "| Run | Strict-zero cases | Coverage shift pp | MAPE shift pp |",
        "|---|---:|---:|---:|",
    ]
    for run_name in RUN_ORDER:
        coverage_shift = strict_zero[run_name]["coverage_pct"] - headline[run_name]["coverage_pct"]
        mape_shift = strict_zero[run_name]["mape"] - headline[run_name]["mape"]
        lines.append(
            f"| {run_name} | {strict_zero[run_name]['cases']} | "
            f"{_format_float(coverage_shift)} | {_format_float(mape_shift)} |"
        )
    return lines


def _claim_mapping(metrics_by_run: dict[str, dict[str, Any]]) -> list[str]:
    b = metrics_by_run["B"]
    run_b_passes = (
        b["coverage_pct"] >= 75
        and b["mape"] <= 12
        and b["median_interval_width_pct"] <= 50
    )
    b_minus_d = _coverage_delta(metrics_by_run, "B", "D")
    b_minus_e = _coverage_delta(metrics_by_run, "B", "E")
    b_minus_c = _coverage_delta(metrics_by_run, "B", "C")
    f = metrics_by_run["F"]
    b_minus_a = _coverage_delta(metrics_by_run, "B", "A-subset")
    claims = [
        (
            "Demand-side model is validated conditional on measured HLC, measured indoor temperature, and realised SPF",
            run_b_passes,
        ),
        (
            "MCS HLC substitution materially degrades accuracy in the measured-input subset",
            b_minus_d >= 20,
        ),
        (
            "Indoor-temperature substitution materially degrades accuracy in the measured-input subset",
            b_minus_e >= 15,
        ),
        ("Fixed generic SCOP proxy is inadequate", b_minus_c >= 20),
        (
            "Realistic-user product is viable with documented uncertainty disclosure",
            f["coverage_pct"] >= 60 and f["mape"] <= 25,
        ),
        ("Calibration data is the highest-impact v2 feature", b_minus_a >= 30),
    ]
    lines = ["| Allowed claim | Evidence status |", "|---|---|"]
    for claim, supported in claims:
        lines.append(f"| {claim} | {'Supported' if supported else 'Not supported'} |")
    return lines


def _write_errors_csv(predictions: list[dict[str, Any]]) -> None:
    metadata_fields = [
        "system_id",
        "location",
        "age",
        "insulation",
        "property_type",
        "hp_manufacturer",
        "hp_model",
        "data_days",
        "realised_annual_elec_kwh",
        "realised_spf",
        "measured_input_subset",
        "strict_zero_cooling_immersion",
    ]
    run_fields = []
    for run_name in RUN_ORDER:
        prefix = run_name.lower().replace("-", "_")
        run_fields.extend(
            [
                f"{prefix}_p10",
                f"{prefix}_p50",
                f"{prefix}_p90",
                f"{prefix}_error_pct",
                f"{prefix}_in_band",
                f"{prefix}_pit",
            ]
        )

    with ERRORS_CSV_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=metadata_fields + run_fields)
        writer.writeheader()
        for record in predictions:
            row = {field: record[field] for field in metadata_fields}
            for run_name in RUN_ORDER:
                prefix = run_name.lower().replace("-", "_")
                run = record["runs"].get(run_name)
                row[f"{prefix}_p10"] = run["predicted_p10_kwh"] if run else ""
                row[f"{prefix}_p50"] = run["predicted_p50_kwh"] if run else ""
                row[f"{prefix}_p90"] = run["predicted_p90_kwh"] if run else ""
                row[f"{prefix}_error_pct"] = run["error_pct"] if run else ""
                row[f"{prefix}_in_band"] = run["in_p10_p90_band"] if run else ""
                row[f"{prefix}_pit"] = run["pit"] if run else ""
            writer.writerow(row)


def _git_head() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception as exc:  # noqa: BLE001
        return f"unavailable ({exc!r})"


def _write_report(
    *,
    predictions: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    args: argparse.Namespace,
    metrics_by_run: dict[str, dict[str, Any]],
    strict_zero_metrics: dict[str, dict[str, Any]],
    sensitivity: dict[str, dict[str, Any]],
) -> None:
    measured_count = sum(_is_measured_subset(case) for case in cases)
    strict_zero_count = sum(_strict_zero(case) for case in cases)
    demographic = _demographic_comparison(cases)
    slices = _slice_analyses(predictions)
    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    snapshot_mode = "frozen" if args.use_frozen_snapshot else "latest"
    snapshot_date = args.snapshot_date or "n/a"

    lines = [
        "# HeatpumpMonitor Calibration Evaluation",
        "",
        "## Preamble",
        "",
        f"- Methodology commit hash: `{METHODOLOGY_COMMIT}`",
        f"- Model code commit hash at script run time: `{_git_head()}`",
        f"- Evaluation timestamp: `{timestamp}`",
        f"- Random seed: `{args.random_seed}`",
        f"- Per-case seed scheme: `case_seed = random_seed * 1000 + system_id`; the same case seed is used across all seven runs.",
        f"- Snapshot mode: `{snapshot_mode}`",
        f"- Snapshot date: `{snapshot_date}`",
        f"- Per-case failures: `{len(failures)}`",
        "",
        "## Dataset Summary",
        "",
        f"- Eligible set size: {len(cases)}",
        f"- Measured-input subset size: {measured_count}",
        f"- Strict-zero cooling/immersion subset size: {strict_zero_count}",
        "",
        "### Demographic Comparison",
        "",
        "| Field | Max proportion difference between eligible and measured-input subset |",
        "|---|---:|",
    ]
    for field, values in demographic.items():
        lines.append(f"| {field} | {values['max_proportion_delta_pct']:.1f} pp |")

    lines.extend(
        [
            "",
            "## Headline Aggregate Metrics",
            "",
            *_metrics_table(metrics_by_run),
            "",
            "## Permitted Comparisons",
            "",
            *_comparison_lines(metrics_by_run),
            "",
            "## Section 7.1 Run B Validation Outcome",
            "",
            *_run_b_validation(metrics_by_run),
            "",
            "## Section 7.4 Run F Validation Outcome",
            "",
            _run_f_validation(metrics_by_run),
            "",
            "## Section 7.5 Sharpness Diagnostic",
            "",
            *_sharpness_lines(metrics_by_run),
            "",
            "## Section 7.6 PIT Histogram and KS Test",
            "",
            *_pit_lines(metrics_by_run),
            "",
            "## Section 5.3 Slice Analyses on Run A-full",
            "",
        ]
    )
    for slice_name, rows in slices.items():
        lines.extend([f"### {slice_name}", "", *_slice_table(rows), ""])

    lines.extend(
        [
            "## Section 5.4 DHW Occupancy Sensitivity",
            "",
            *_dhw_lines(sensitivity),
            "",
            "## Section 5.5 Strict-Zero Cooling/Immersion Sensitivity",
            "",
            *_strict_zero_lines(metrics_by_run, strict_zero_metrics),
            "",
            "## Section 10 Claim Mapping",
            "",
            *_claim_mapping(metrics_by_run),
            "",
        ]
    )

    if failures:
        lines.extend(["## Per-Case Failures", ""])
        for failure in failures:
            lines.append(f"- system_id={failure['system_id']}: `{failure['error']}`")
        lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _mean_mape_so_far(predictions: list[dict[str, Any]], run_name: str) -> float:
    metrics = _aggregate_metrics(predictions, run_name)
    return metrics["mape"]


def main() -> None:
    args = _parse_args()
    cases = _load_json(INPUT_PATH)
    if args.limit is not None:
        cases = cases[: args.limit]
        print(f"--limit {args.limit} applied; evaluating first {len(cases)} cases only.")
    measured_count = sum(_is_measured_subset(case) for case in cases)
    print(f"Eligible cases: {len(cases)}")
    print(f"Measured-input subset cases: {measured_count}")
    print(f"Random seed: {args.random_seed}")

    predictions: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        try:
            predictions.append(_evaluate_case(case, args.random_seed))
        except Exception as exc:  # noqa: BLE001
            failures.append({"system_id": case.get("system_id"), "error": repr(exc)})
            print(
                f"Evaluation failed for system_id={case.get('system_id')}: {exc!r}",
                file=sys.stderr,
            )

        if index % SAVE_EVERY_CASES == 0:
            _atomic_write_json(PARTIAL_PREDICTIONS_PATH, predictions)
            print(
                f"[{index}/{len(cases)}] cases done. Mean MAPE so far - "
                f"A-full: {_mean_mape_so_far(predictions, 'A-full'):.1f}%, "
                f"B: {_mean_mape_so_far(predictions, 'B'):.1f}%, "
                f"F: {_mean_mape_so_far(predictions, 'F'):.1f}%."
            )
        time.sleep(SLEEP_SECONDS_BETWEEN_CASES)

    _atomic_write_json(PARTIAL_PREDICTIONS_PATH, predictions)
    _atomic_write_json(PREDICTIONS_PATH, predictions)
    metrics_by_run = _aggregate_all(predictions)
    strict_metrics = _strict_zero_metrics(predictions)
    sensitivity = _evaluate_dhw_sensitivity(cases, args.random_seed)
    _write_errors_csv(predictions)
    _write_report(
        predictions=predictions,
        failures=failures,
        cases=cases,
        args=args,
        metrics_by_run=metrics_by_run,
        strict_zero_metrics=strict_metrics,
        sensitivity=sensitivity,
    )
    print(
        f"Evaluated {len(predictions)} cases with {len(failures)} failures. "
        f"Saved outputs to {OUTPUT_DIR.as_posix()}."
    )


if __name__ == "__main__":
    main()
