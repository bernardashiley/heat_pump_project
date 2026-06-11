from pathlib import Path
from typing import Literal

import numpy as np

from app.forecast.climate import load_or_fetch_climate
from app.forecast.cop import ETA_MAX, ETA_MIN, calculate_cop_curve, fit_eta_from_scop
from app.forecast.cost import calculate_cost_by_scenario
from app.forecast.demand import (
    calculate_annual_dhw_demand,
    calculate_daily_space_heating_demand,
    derive_hlc_w_per_k,
)
from app.models import Assumptions, ForecastRequest, ForecastResponse, KwhPercentiles

DEFAULT_DRAW_COUNT = 1000
DEFAULT_RESIDUAL_SIGMA_FRACTION = 0.08
DEFAULT_CACHE_DIR = Path("data/cache")


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


def _kwh_percentiles(draws_kwh: np.ndarray) -> KwhPercentiles:
    p10_kwh, p50_kwh, p90_kwh = np.percentile(draws_kwh, [10, 50, 90])
    return KwhPercentiles(
        p10_kwh=float(p10_kwh),
        p50_kwh=float(p50_kwh),
        p90_kwh=float(p90_kwh),
    )


def forecast_from_request(
    request: ForecastRequest,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    random_seed: int | None = None,
    demand_period_mode: Literal["winter", "full_year"] = "winter",
) -> ForecastResponse:
    """Run the full forecast pipeline for an API forecast request.

    Implements MODEL.md §6 — From demand to electricity.

    Inputs:
    - request: forecast request schema with property, heat pump, DHW, and tariffs.
    - cache_dir: filesystem path where climate cache files are stored.
    - random_seed: optional random seed for deterministic Monte Carlo draws.
    - demand_period_mode: "winter" preserves v1 October-March behavior;
      "full_year" evaluates complete calendar-year weather periods.

    Outputs:
    - forecast response schema with fitted eta, kWh percentiles, GBP percentiles,
      monthly kWh breakdown, 1000 annual kWh draws, assumptions, and warnings.
    """
    warnings = []
    climate = load_or_fetch_climate(
        request.property,
        cache_dir,
        winters=20,
        demand_period_mode=demand_period_mode,
    )
    t_out_c = climate["t_out_c"].to_numpy()
    period_column = "year_id" if demand_period_mode == "full_year" else "winter_id"
    period_index = climate[period_column].to_numpy()

    hlc_w_per_k = derive_hlc_w_per_k(request.property)
    daily_sh_kwh = calculate_daily_space_heating_demand(
        t_out_c,
        hlc_w_per_k,
        request.property.t_base_c,
    )
    annual_dhw_kwh = calculate_annual_dhw_demand(request.dhw)
    daily_dhw_kwh = np.full(len(climate), annual_dhw_kwh / 365)

    eta, at_boundary = fit_eta_from_scop(
        request.heat_pump.scop,
        daily_sh_kwh,
        t_out_c,
        request.heat_pump.t_flow_sh_c,
        request.heat_pump.defrost_penalty_peak_pct,
    )
    if at_boundary:
        warnings.append(
            "fitted second-law efficiency hit boundary "
            f"({ETA_MIN} or {ETA_MAX}); SCOP and flow temperature may be inconsistent"
        )

    cop_sh = calculate_cop_curve(
        t_out_c,
        request.heat_pump.t_flow_sh_c,
        eta,
        request.heat_pump.defrost_penalty_peak_pct,
    )
    cop_dhw = calculate_cop_curve(
        t_out_c,
        request.dhw.t_flow_dhw_c,
        eta,
        request.heat_pump.defrost_penalty_peak_pct,
    )
    e_sh, e_dhw, e_total = calculate_daily_electricity(
        daily_sh_kwh,
        daily_dhw_kwh,
        cop_sh,
        cop_dhw,
    )

    annual_sh_by_period = calculate_annual_electricity_by_winter(e_sh, period_index)
    annual_dhw_by_period = calculate_annual_electricity_by_winter(e_dhw, period_index)
    annual_total_by_period = calculate_annual_electricity_by_winter(
        e_total,
        period_index,
    )

    # Derive independent deterministic streams for SH, DHW, and total draws
    # while preserving fully random behavior when no seed is provided.
    sh_seed = random_seed
    dhw_seed = random_seed + 1 if random_seed is not None else None
    total_seed = random_seed + 2 if random_seed is not None else None
    draws_sh = generate_electricity_draws(
        annual_sh_by_period,
        random_seed=sh_seed,
    )
    draws_dhw = generate_electricity_draws(
        annual_dhw_by_period,
        random_seed=dhw_seed,
    )
    draws_total = generate_electricity_draws(
        annual_total_by_period,
        random_seed=total_seed,
    )

    median_total = np.median(annual_total_by_period)
    median_period_id = int(np.argmin(np.abs(annual_total_by_period - median_total)))
    median_period = period_index == median_period_id
    monthly_breakdown = [0.0] * 12
    for month in range(1, 13):
        month_mask = median_period & (climate["date"].dt.month.to_numpy() == month)
        if np.any(month_mask):
            monthly_breakdown[month - 1] = float(np.sum(e_total[month_mask]))

    return ForecastResponse(
        fitted_eta=eta,
        space_heating=_kwh_percentiles(draws_sh),
        dhw=_kwh_percentiles(draws_dhw),
        total=_kwh_percentiles(draws_total),
        cost_by_scenario=calculate_cost_by_scenario(
            draws_total,
            request.tariff_scenarios,
        ),
        monthly_breakdown_median_kwh=monthly_breakdown,
        draws_kwh=draws_total.tolist(),
        assumptions=Assumptions(
            property=request.property,
            heat_pump=request.heat_pump,
            dhw=request.dhw,
            tariff_scenarios=request.tariff_scenarios,
            fitted_eta=eta,
        ),
        warnings=warnings,
    )
