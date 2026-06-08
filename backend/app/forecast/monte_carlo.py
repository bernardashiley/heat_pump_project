import numpy as np

from app.models import ForecastRequest, ForecastResponse

DEFAULT_DRAW_COUNT = 1000
DEFAULT_RESIDUAL_SIGMA_FRACTION = 0.08


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
    daily_space_heating_kwh = np.asarray(daily_space_heating_kwh, dtype=float)
    daily_dhw_kwh = np.asarray(daily_dhw_kwh, dtype=float)
    space_heating_cop = np.asarray(space_heating_cop, dtype=float)
    dhw_cop = np.asarray(dhw_cop, dtype=float)

    zero_space_heating_demand = daily_space_heating_kwh == 0
    safe_space_heating_cop = np.where(zero_space_heating_demand, 1.0, space_heating_cop)
    electricity_sh_kwh = np.where(
        zero_space_heating_demand,
        0.0,
        daily_space_heating_kwh / safe_space_heating_cop,
    )
    electricity_dhw_kwh = daily_dhw_kwh / dhw_cop
    electricity_total_kwh = electricity_sh_kwh + electricity_dhw_kwh
    return electricity_sh_kwh, electricity_dhw_kwh, electricity_total_kwh


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
    - annual electricity totals by winter realisation in kWh/year, with output
      length equal to winter_index.max() + 1.
    """
    return np.bincount(winter_index, weights=daily_total_electricity_kwh)


def generate_electricity_draws(
    annual_electricity_by_winter_kwh: np.ndarray,
    draw_count: int = DEFAULT_DRAW_COUNT,
    residual_sigma_fraction: float = DEFAULT_RESIDUAL_SIGMA_FRACTION,
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
    annual_electricity_by_winter_kwh = np.asarray(
        annual_electricity_by_winter_kwh,
        dtype=float,
    )
    rng = np.random.default_rng(random_seed)
    sampled_winter_index = rng.integers(
        0,
        len(annual_electricity_by_winter_kwh),
        size=draw_count,
    )
    sampled_winter_kwh = annual_electricity_by_winter_kwh[sampled_winter_index]
    residual_sigma_kwh = residual_sigma_fraction * sampled_winter_kwh
    residual_noise_kwh = rng.normal(
        loc=0.0,
        scale=residual_sigma_kwh,
        size=draw_count,
    )
    return np.clip(sampled_winter_kwh + residual_noise_kwh, 0, None)


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
