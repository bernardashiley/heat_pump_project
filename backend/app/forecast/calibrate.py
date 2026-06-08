import numpy as np
import pandas as pd

from app.models import (
    CalibrationRequest,
    CalibrationResponse,
    CalibrationYearResult,
    PastMonthlyKwh,
)


def aggregate_monthly_kwh(past_monthly_kwh: list[PastMonthlyKwh]) -> pd.DataFrame:
    """Aggregate submitted monthly electricity readings into annual calibration data.

    Implements MODEL.md §8 — Calibration.

    Inputs:
    - past_monthly_kwh: monthly readings with year, month, and electricity in kWh/month.

    Outputs:
    - pandas.DataFrame of annual realised electricity in kWh/year.
    """
    monthly = pd.DataFrame(
        {
            "year": [reading.year for reading in past_monthly_kwh],
            "month": [reading.month for reading in past_monthly_kwh],
            "kwh": [reading.kwh for reading in past_monthly_kwh],
        }
    )
    complete_years = monthly.groupby("year")["month"].nunique()
    complete_years = complete_years[complete_years == 12].index
    annual = (
        monthly[monthly["year"].isin(complete_years)]
        .groupby("year", as_index=False)["kwh"]
        .sum()
        .rename(columns={"kwh": "realised_kwh"})
        .sort_values("year")
        .reset_index(drop=True)
    )

    if annual.empty:
        raise ValueError(
            "no complete years in past_monthly_kwh; at least one year with all 12 months is required"
        )

    annual["year"] = annual["year"].astype(int)
    annual["realised_kwh"] = annual["realised_kwh"].astype(float)
    return annual


def calculate_pit_value(
    realised_kwh: float,
    predicted_draws_kwh: np.ndarray,
) -> float:
    """Calculate the PIT value for one realised annual electricity value.

    Implements MODEL.md §8 — Calibration.

    Inputs:
    - realised_kwh: realised annual electricity in kWh/year.
    - predicted_draws_kwh: predicted annual electricity draws in kWh/year.

    Outputs:
    - PIT value as empirical CDF rank divided by draw count, dimensionless fraction.
    """
    predicted_draws_kwh = np.asarray(predicted_draws_kwh, dtype=float)
    return float(np.sum(predicted_draws_kwh < realised_kwh) / len(predicted_draws_kwh))


def calculate_calibration_metrics(
    per_year_results: list[CalibrationYearResult],
    pit_values: np.ndarray,
    realised_costs_gbp: np.ndarray,
    predicted_median_costs_gbp: np.ndarray,
) -> CalibrationResponse:
    """Calculate MAE, 80% coverage, and PIT histogram from yearly backtest results.

    Implements MODEL.md §8 — Calibration.

    Inputs:
    - per_year_results: yearly calibration schemas with realised and forecast kWh in kWh/year.
    - pit_values: PIT values, dimensionless fractions.
    - realised_costs_gbp: realised annual costs in GBP/year.
    - predicted_median_costs_gbp: predicted median annual costs in GBP/year.

    Outputs:
    - calibration response schema with MAE in kWh and GBP, 80% coverage as a fraction,
      PIT histogram bin fractions, and per-year results.
    """
    realised_kwh = np.array([result.realised_kwh for result in per_year_results])
    predicted_p50_kwh = np.array([result.p50_kwh for result in per_year_results])
    in_band = np.array([result.in_band for result in per_year_results], dtype=float)
    pit_counts, _ = np.histogram(pit_values, bins=10, range=(0, 1))

    return CalibrationResponse(
        mae_kwh=float(np.mean(np.abs(realised_kwh - predicted_p50_kwh))),
        mae_gbp=float(
            np.mean(
                np.abs(
                    np.asarray(realised_costs_gbp, dtype=float)
                    - np.asarray(predicted_median_costs_gbp, dtype=float)
                )
            )
        ),
        coverage_80_pct=float(np.mean(in_band)),
        pit_bins=(pit_counts / len(pit_values)).astype(float).tolist(),
        per_year_results=per_year_results,
    )


def run_walk_forward_backtest(request: CalibrationRequest) -> CalibrationResponse:
    """Run walk-forward calibration backtest for submitted past monthly electricity data.

    Implements MODEL.md §8 — Calibration.

    Inputs:
    - request: calibration request schema with property, heat pump, DHW, tariffs,
      and past monthly electricity in kWh/month.

    Outputs:
    - calibration response schema with MAE in kWh and GBP, 80% coverage as a fraction,
      PIT histogram bin fractions, and per-year results.
    """
    raise NotImplementedError(
        "calibrate.run_walk_forward_backtest depends on monte_carlo.forecast_from_request; implement orchestrator first"
    )
