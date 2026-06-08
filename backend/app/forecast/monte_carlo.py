import numpy as np

from app.models import ForecastRequest, ForecastResponse


def calculate_daily_electricity(
    daily_space_heating_kwh: np.ndarray,
    daily_dhw_kwh: np.ndarray,
    space_heating_cop: np.ndarray,
    dhw_cop: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert delivered heat demand into daily electricity for SH, DHW, and total.

    Implements MODEL.md §6.1 — Daily electricity.

    Inputs:
    - daily_space_heating_kwh: delivered space-heating demand in kWh/day.
    - daily_dhw_kwh: delivered DHW demand in kWh/day.
    - space_heating_cop: space-heating COP values, dimensionless.
    - dhw_cop: DHW COP values, dimensionless.

    Outputs:
    - tuple of daily space-heating, DHW, and total electricity in kWh/day.
    """
    raise NotImplementedError(
        f"monte_carlo.calculate_daily_electricity — see MODEL.md §6.1"
    )


def calculate_annual_electricity_by_winter(
    daily_total_electricity_kwh: np.ndarray,
    winter_index: np.ndarray,
) -> np.ndarray:
    """Aggregate daily total electricity into annual totals for each winter realisation.

    Implements MODEL.md §6.1 — Daily electricity.

    Inputs:
    - daily_total_electricity_kwh: daily total electricity in kWh/day.
    - winter_index: winter realisation identifier for each daily value, count labels.

    Outputs:
    - annual electricity totals by winter realisation in kWh/year.
    """
    raise NotImplementedError(
        f"monte_carlo.calculate_annual_electricity_by_winter — see MODEL.md §6.1"
    )


def generate_electricity_draws(
    annual_electricity_by_winter_kwh: np.ndarray,
    draw_count: int = 1000,
    residual_sigma_fraction: float = 0.08,
    random_seed: int | None = None,
) -> np.ndarray:
    """Generate Monte Carlo annual electricity draws from weather and residual noise.

    Implements MODEL.md §6.2 — Monte Carlo.

    Inputs:
    - annual_electricity_by_winter_kwh: annual electricity by winter realisation in kWh/year.
    - draw_count: number of Monte Carlo draws, count.
    - residual_sigma_fraction: residual standard deviation as a fraction of annual kWh.
    - random_seed: optional random seed, integer.

    Outputs:
    - Monte Carlo annual electricity draws in kWh/year.
    """
    raise NotImplementedError(
        f"monte_carlo.generate_electricity_draws — see MODEL.md §6.2"
    )


def forecast_from_request(request: ForecastRequest) -> ForecastResponse:
    """Run the full forecast pipeline for an API forecast request.

    Implements MODEL.md §6 — From demand to electricity.

    Inputs:
    - request: forecast request schema with property, heat pump, DHW, and tariffs.

    Outputs:
    - forecast response schema with fitted eta, kWh percentiles, GBP percentiles,
      monthly kWh breakdown, 1000 annual kWh draws, assumptions, and warnings.
    """
    raise NotImplementedError(f"monte_carlo.forecast_from_request — see MODEL.md §6")
