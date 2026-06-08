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
    raise NotImplementedError(f"calibrate.aggregate_monthly_kwh — see MODEL.md §8")


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
    raise NotImplementedError(f"calibrate.calculate_pit_value — see MODEL.md §8")


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
    raise NotImplementedError(
        f"calibrate.calculate_calibration_metrics — see MODEL.md §8"
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
        f"calibrate.run_walk_forward_backtest — see MODEL.md §8"
    )
