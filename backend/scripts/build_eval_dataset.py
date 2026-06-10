"""Build HeatpumpMonitor evaluation cases from a fetched dataset snapshot.

Default mode reads data/heatpumpmonitor/systems_latest.json and
stats_all_latest.json. Reproducible evaluation mode uses
--use-frozen-snapshot --snapshot-date YYYYMMDD to read the dated snapshot files
systems_YYYYMMDD.json and stats_all_YYYYMMDD.json.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

INPUT_DIR = Path("data/heatpumpmonitor")
SYSTEMS_LATEST_PATH = INPUT_DIR / "systems_latest.json"
STATS_LATEST_PATH = INPUT_DIR / "stats_all_latest.json"
EVAL_CASES_PATH = INPUT_DIR / "eval_cases.json"
FILTER_REPORT_PATH = INPUT_DIR / "eval_filter_report.txt"
SECONDS_PER_DAY = 86400
DAYS_PER_YEAR = 365
MIN_DATA_SECONDS = DAYS_PER_YEAR * SECONDS_PER_DAY
ESSENTIAL_FIELDS = (
    "floor_area",
    "heat_loss",
    "design_temp",
    "flow_temp",
    "hp_output",
    "latitude",
    "longitude",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build HeatpumpMonitor evaluation cases from fetched JSON.",
    )
    parser.add_argument(
        "--use-frozen-snapshot",
        action="store_true",
        help="Read dated snapshot files instead of systems_latest/stats_all_latest.",
    )
    parser.add_argument(
        "--snapshot-date",
        metavar="YYYYMMDD",
        help="Snapshot date to use with --use-frozen-snapshot.",
    )
    args = parser.parse_args()

    if args.use_frozen_snapshot and not args.snapshot_date:
        parser.error("--use-frozen-snapshot requires --snapshot-date YYYYMMDD")
    if args.snapshot_date and not args.use_frozen_snapshot:
        parser.error("--snapshot-date is only valid with --use-frozen-snapshot")

    return args


def _input_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    if not args.use_frozen_snapshot:
        return SYSTEMS_LATEST_PATH, STATS_LATEST_PATH

    systems_path = INPUT_DIR / f"systems_{args.snapshot_date}.json"
    stats_path = INPUT_DIR / f"stats_all_{args.snapshot_date}.json"
    missing_paths = [path for path in (systems_path, stats_path) if not path.exists()]
    if missing_paths:
        missing = ", ".join(path.as_posix() for path in missing_paths)
        raise FileNotFoundError(
            f"frozen snapshot file(s) not found for {args.snapshot_date}: {missing}",
        )
    return systems_path, stats_path


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _is_present(value: Any) -> bool:
    return value not in (None, "", "0")


def _truthy_flag(value: Any) -> bool:
    return value not in (None, "", 0, "0", False)


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _required_float(system: dict[str, Any], field: str) -> float:
    value = _to_float(system.get(field))
    if value is None:
        raise ValueError(f"missing required numeric field after filtering: {field}")
    return value


def _optional_energy_kwh(stats: dict[str, Any], field: str) -> float:
    value = _to_float(stats.get(field))
    return value if value is not None else 0.0


def _optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _internal_temperature(system: dict[str, Any]) -> float:
    indoor_temperature = _to_float(system.get("indoor_temperature"))
    if indoor_temperature is not None and 15 <= indoor_temperature <= 25:
        return indoor_temperature
    return 21.0


def _measured_indoor_temperature(stats: dict[str, Any]) -> float | None:
    quality_room = _to_float(stats.get("quality_roomT"))
    room_mean = _to_float(stats.get("combined_roomT_mean"))
    if quality_room is not None and quality_room >= 70 and room_mean is not None:
        return room_mean
    return None


def _measured_heat_loss(system: dict[str, Any]) -> float | None:
    measured_heat_loss_kw = _to_float(system.get("measured_heat_loss"))
    if measured_heat_loss_kw is not None and measured_heat_loss_kw > 0:
        return measured_heat_loss_kw * 1000
    return None


def _build_case(system: dict[str, Any], stats: dict[str, Any]) -> dict[str, Any]:
    data_length = _required_float(stats, "combined_data_length")
    scale_to_year = DAYS_PER_YEAR * SECONDS_PER_DAY / data_length
    notes = _optional_str(system.get("notes"))

    return {
        "system_id": int(system["id"]),
        "location": str(system.get("location") or ""),
        "hp_manufacturer": str(system.get("hp_manufacturer") or ""),
        "hp_model": str(system.get("hp_model") or ""),
        "property_type": str(system.get("property") or ""),
        "age": str(system.get("age") or ""),
        "insulation": str(system.get("insulation") or ""),
        "latitude": _required_float(system, "latitude"),
        "longitude": _required_float(system, "longitude"),
        "data_days": data_length / SECONDS_PER_DAY,
        "realised": {
            "annual_elec_kwh": _required_float(stats, "combined_elec_kwh")
            * scale_to_year,
            "annual_heat_kwh": _required_float(stats, "combined_heat_kwh")
            * scale_to_year,
            "cooling_elec_kwh": _optional_energy_kwh(stats, "cooling_elec_kwh")
            * scale_to_year,
            "immersion_kwh": _optional_energy_kwh(stats, "immersion_kwh")
            * scale_to_year,
            "spf": _required_float(stats, "combined_cop"),
            "mean_outside_c": _required_float(stats, "combined_outsideT_mean"),
            "mean_indoor_c": _to_float(stats.get("combined_roomT_mean")),
            "indoor_quality_pct": _to_float(stats.get("quality_roomT")) or 0.0,
        },
        "mcs_inputs": {
            "floor_area_m2": _required_float(system, "floor_area"),
            "heat_loss_design_w": _required_float(system, "heat_loss") * 1000,
            "t_design_outdoor_c": _required_float(system, "design_temp"),
            "t_flow_sh_c": _required_float(system, "flow_temp"),
            "t_internal_c": _internal_temperature(system),
            "hp_output_kw": _required_float(system, "hp_output"),
            "cylinder_l": _to_float(system.get("cylinder_volume")),
            "notes_field": notes[:500] if notes is not None else None,
        },
        "best_info_overrides": {
            "heat_loss_design_w_measured": _measured_heat_loss(system),
            "t_internal_c_measured": _measured_indoor_temperature(stats),
        },
    }


def _format_report(
    total: int,
    drops: dict[str, int],
    cases: list[dict[str, Any]],
) -> str:
    measured_heat_loss_count = sum(
        case["best_info_overrides"]["heat_loss_design_w_measured"] is not None
        for case in cases
    )
    measured_indoor_count = sum(
        case["best_info_overrides"]["t_internal_c_measured"] is not None
        for case in cases
    )
    strict_zero_count = sum(
        case["realised"]["cooling_elec_kwh"] == 0
        and case["realised"]["immersion_kwh"] == 0
        for case in cases
    )
    surviving = len(cases)
    heat_loss_pct = 100 * measured_heat_loss_count / surviving if surviving else 0
    indoor_pct = 100 * measured_indoor_count / surviving if surviving else 0
    strict_zero_pct = 100 * strict_zero_count / surviving if surviving else 0

    return "\n".join(
        [
            "HeatpumpMonitor evaluation dataset filter report",
            f"Generated: {datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00', 'Z')}",
            "",
            f"{'Total systems:':48s}{total:6d}",
            f"{'- Missing stats entry:':48s}{-drops['missing_stats']:6d}",
            f"{'- Less than 365 days of data:':48s}{-drops['short_data']:6d}",
            f"{'- data_flag set:':48s}{-drops['data_flag']:6d}",
            f"{'- Missing essential MCS fields:':48s}{-drops['missing_essential']:6d}",
            f"{'- Quality elec/heat < 90%:':48s}{-drops['low_quality']:6d}",
            f"{'- SPF null or <= 1.5:':48s}{-drops['bad_spf']:6d}",
            f"{'- Cooling or immersion backup > 5% of total electricity:':48s}"
            f"{-drops['cooling_immersion']:6d}",
            "",
            f"{'Surviving evaluation cases:':48s}{surviving:6d}",
            "",
            f"{'With measured_heat_loss override available:':48s}"
            f"{measured_heat_loss_count:6d} ({heat_loss_pct:.1f}%)",
            f"{'With measured indoor temp override available:':48s}"
            f"{measured_indoor_count:6d} ({indoor_pct:.1f}%)",
            f"{'Strict-zero cooling/immersion subset (both zero or missing):':48s}"
            f"{strict_zero_count:6d} of {surviving} surviving cases "
            f"({strict_zero_pct:.1f}%)",
            "",
        ]
    )


def main() -> None:
    args = _parse_args()
    systems_path, stats_path = _input_paths(args)
    systems = _load_json(systems_path)
    stats_by_id = _load_json(stats_path)
    drops = {
        "missing_stats": 0,
        "short_data": 0,
        "data_flag": 0,
        "missing_essential": 0,
        "low_quality": 0,
        "bad_spf": 0,
        "cooling_immersion": 0,
    }
    cases = []

    for system in systems:
        stats = stats_by_id.get(str(system["id"]))
        if stats is None:
            drops["missing_stats"] += 1
            continue

        data_length = _to_float(stats.get("combined_data_length"))
        if data_length is None or data_length < MIN_DATA_SECONDS:
            drops["short_data"] += 1
            continue

        if _truthy_flag(system.get("data_flag")):
            drops["data_flag"] += 1
            continue

        if any(not _is_present(system.get(field)) for field in ESSENTIAL_FIELDS):
            drops["missing_essential"] += 1
            continue

        quality_elec = _to_float(stats.get("quality_elec"))
        quality_heat = _to_float(stats.get("quality_heat"))
        if (
            quality_elec is None
            or quality_heat is None
            or quality_elec < 90
            or quality_heat < 90
            or _to_float(stats.get("combined_elec_kwh")) is None
            or _to_float(stats.get("combined_heat_kwh")) is None
            or _to_float(stats.get("combined_outsideT_mean")) is None
        ):
            drops["low_quality"] += 1
            continue

        spf = _to_float(stats.get("combined_cop"))
        if spf is None or spf <= 1.5:
            drops["bad_spf"] += 1
            continue

        combined_elec_kwh = _required_float(stats, "combined_elec_kwh")
        cooling_elec_kwh = _optional_energy_kwh(stats, "cooling_elec_kwh")
        immersion_kwh = _optional_energy_kwh(stats, "immersion_kwh")
        if (cooling_elec_kwh + immersion_kwh) / combined_elec_kwh > 0.05:
            drops["cooling_immersion"] += 1
            continue

        cases.append(_build_case(system, stats))

    _write_json(EVAL_CASES_PATH, cases)
    FILTER_REPORT_PATH.write_text(
        _format_report(len(systems), drops, cases),
        encoding="utf-8",
    )
    print(
        f"Built {len(cases)} evaluation cases from {len(systems)} systems. "
        f"Saved to {EVAL_CASES_PATH.as_posix()}."
    )


if __name__ == "__main__":
    main()
