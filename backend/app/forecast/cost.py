import numpy as np

from app.models import CostScenarioPercentiles, TariffScenarioInput

PENCE_PER_POUND = 100
DAYS_PER_YEAR = 365


def apply_tariff_to_draws(
    draws_kwh: np.ndarray,
    tariff: TariffScenarioInput,
) -> np.ndarray:
    """Apply one tariff scenario to annual electricity draws.

    Implements MODEL.md §6.3 — Cost.

    Inputs:
    - draws_kwh: annual electricity draws in kWh/year.
    - tariff: tariff schema with unit_rate_p_per_kwh in p/kWh and
      standing_charge_p_per_day in p/day.

    Outputs:
    - annual running-cost draws in GBP/year.
    """
    draws_kwh = np.asarray(draws_kwh, dtype=float)
    consumption_cost_gbp = (
        draws_kwh * tariff.unit_rate_p_per_kwh / PENCE_PER_POUND
    )
    standing_charge_gbp = (
        DAYS_PER_YEAR * tariff.standing_charge_p_per_day / PENCE_PER_POUND
    )
    return consumption_cost_gbp + standing_charge_gbp


def summarise_cost_percentiles(
    name: str,
    costs_gbp: np.ndarray,
) -> CostScenarioPercentiles:
    """Summarise annual cost draws into 10th, 50th, and 90th percentiles.

    Implements MODEL.md §6.3 — Cost.

    Inputs:
    - name: tariff scenario name.
    - costs_gbp: annual running-cost draws in GBP/year.

    Outputs:
    - cost percentile schema with p10_gbp, p50_gbp, and p90_gbp in GBP/year.
    """
    p10_gbp, p50_gbp, p90_gbp = np.percentile(costs_gbp, [10, 50, 90])
    return CostScenarioPercentiles(
        name=name,
        p10_gbp=float(p10_gbp),
        p50_gbp=float(p50_gbp),
        p90_gbp=float(p90_gbp),
    )


def calculate_cost_by_scenario(
    draws_kwh: np.ndarray,
    tariffs: list[TariffScenarioInput],
) -> list[CostScenarioPercentiles]:
    """Calculate cost percentiles for each tariff scenario.

    Implements MODEL.md §6.3 — Cost.

    Inputs:
    - draws_kwh: annual electricity draws in kWh/year.
    - tariffs: tariff schemas with unit rates in p/kWh and standing charges in p/day.

    Outputs:
    - list of cost percentile schemas with annual costs in GBP/year.
    """
    results = []
    for tariff in tariffs:
        costs_gbp = apply_tariff_to_draws(draws_kwh, tariff)
        results.append(summarise_cost_percentiles(tariff.name, costs_gbp))
    return results
