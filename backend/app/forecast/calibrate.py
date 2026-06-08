from pathlib import Path

import numpy as np
import pandas as pd

from app.forecast.monte_carlo import DEFAULT_CACHE_DIR, forecast_from_request
from app.models import (
    CalibrationRequest,
    CalibrationResponse,
    CalibrationYearResult,
    ForecastRequest,
    PastMonthlyKwh,
)


def aggregate_monthly_kwh(past_monthly_kwh: list[PastMonthlyKwh]) -> pd.DataFrame:
    """Aggregate submitted monthly electricity readings into annual calibration data.

    Implements MODEL.md section 8 - Calibration.

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

    Implements MODEL.md section 8 - Calibration.

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

    Implements MODEL.md section 8 - Calibration.

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


def run_walk_forward_backtest(
    request: CalibrationRequest,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> CalibrationResponse:
    """Run walk-forward calibration backtest for submitted past monthly electricity data.

    Implements MODEL.md section 8 - Calibration.

    The v1 forecast model is unconditional: it does not fit parameters from past
    consumption. Walk-forward backtesting therefore runs one forecast for the home
    and compares that predictive distribution against each complete realised year.
    Future versions that fit per-home parameters can make this loop refit using
    only years strictly before each target year.

    Inputs:
    - request: calibration request schema with property, heat pump, DHW, tariffs,
      and past monthly electricity in kWh/month.
    - cache_dir: filesystem path where climate cache files are stored.

    Outputs:
    - calibration response schema with MAE in kWh and GBP, 80% coverage as a fraction,
      PIT histogram bin fractions, and per-year results.
    """
    annual_realised = aggregate_monthly_kwh(request.past_monthly_kwh)
    forecast_request = ForecastRequest(
        property=request.property,
        heat_pump=request.heat_pump,
        dhw=request.dhw,
        tariff_scenarios=request.tariff_scenarios,
    )
    forecast = forecast_from_request(forecast_request, cache_dir=cache_dir)
    draws_kwh = np.asarray(forecast.draws_kwh, dtype=float)
    p10_kwh, p50_kwh, p90_kwh = np.percentile(draws_kwh, [10, 50, 90])
    tariff = request.tariff_scenarios[0]

    per_year_results = []
    pit_values = []
    realised_costs_gbp = []
    predicted_median_costs_gbp = []
    for row in annual_realised.itertuples(index=False):
        realised_kwh = float(row.realised_kwh)
        pit_values.append(calculate_pit_value(realised_kwh, draws_kwh))
        per_year_results.append(
            CalibrationYearResult(
                year=int(row.year),
                realised_kwh=realised_kwh,
                p10_kwh=float(p10_kwh),
                p50_kwh=float(p50_kwh),
                p90_kwh=float(p90_kwh),
                in_band=bool(p10_kwh <= realised_kwh <= p90_kwh),
            )
        )
        realised_costs_gbp.append(
            (realised_kwh * tariff.unit_rate_p_per_kwh / 100)
            + (365 * tariff.standing_charge_p_per_day / 100)
        )
        predicted_median_costs_gbp.append(
            (p50_kwh * tariff.unit_rate_p_per_kwh / 100)
            + (365 * tariff.standing_charge_p_per_day / 100)
        )

    return calculate_calibration_metrics(
        per_year_results=per_year_results,
        pit_values=np.asarray(pit_values, dtype=float),
        realised_costs_gbp=np.asarray(realised_costs_gbp, dtype=float),
        predicted_median_costs_gbp=np.asarray(
            predicted_median_costs_gbp,
            dtype=float,
        ),
    )
