import numpy as np

from app.models import CostScenarioPercentiles, TariffScenarioInput


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
    raise NotImplementedError(f"cost.apply_tariff_to_draws — see MODEL.md §6.3")


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
    raise NotImplementedError(f"cost.summarise_cost_percentiles — see MODEL.md §6.3")


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
    raise NotImplementedError(f"cost.calculate_cost_by_scenario — see MODEL.md §6.3")
