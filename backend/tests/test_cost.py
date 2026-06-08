import numpy as np
import pytest

from app.forecast.cost import (
    apply_tariff_to_draws,
    calculate_cost_by_scenario,
    summarise_cost_percentiles,
)
from app.models import CostScenarioPercentiles, TariffScenarioInput


def _tariff(
    name: str = "central",
    standing_charge_p_per_day: float = 50,
    unit_rate_p_per_kwh: float = 25,
) -> TariffScenarioInput:
    return TariffScenarioInput(
        name=name,
        standing_charge_p_per_day=standing_charge_p_per_day,
        unit_rate_p_per_kwh=unit_rate_p_per_kwh,
    )


def test_apply_tariff_known_value() -> None:
    costs_gbp = apply_tariff_to_draws(
        draws_kwh=np.array([1000.0]),
        tariff=_tariff(unit_rate_p_per_kwh=25, standing_charge_p_per_day=50),
    )
    expected_gbp = (1000 * 25 / 100) + (365 * 50 / 100)

    assert costs_gbp[0] == pytest.approx(expected_gbp, abs=1e-9)


def test_apply_tariff_zero_consumption_yields_standing_charge_only() -> None:
    standing_charge_p_per_day = 53

    costs_gbp = apply_tariff_to_draws(
        draws_kwh=np.array([0.0]),
        tariff=_tariff(standing_charge_p_per_day=standing_charge_p_per_day),
    )

    assert costs_gbp[0] == pytest.approx(365 * standing_charge_p_per_day / 100)


def test_apply_tariff_zero_standing_charge() -> None:
    draws_kwh = np.array([100.0, 250.0, 1000.0])
    unit_rate_p_per_kwh = 30

    costs_gbp = apply_tariff_to_draws(
        draws_kwh=draws_kwh,
        tariff=_tariff(
            standing_charge_p_per_day=0,
            unit_rate_p_per_kwh=unit_rate_p_per_kwh,
        ),
    )

    np.testing.assert_array_equal(costs_gbp, draws_kwh * unit_rate_p_per_kwh / 100)


def test_apply_tariff_linear_in_consumption() -> None:
    tariff = _tariff(standing_charge_p_per_day=50, unit_rate_p_per_kwh=25)

    cost_zero = apply_tariff_to_draws(np.array([0.0]), tariff)[0]
    cost_single = apply_tariff_to_draws(np.array([1000.0]), tariff)[0]
    cost_double = apply_tariff_to_draws(np.array([2000.0]), tariff)[0]

    assert cost_double - cost_single == pytest.approx(cost_single - cost_zero)


def test_apply_tariff_returns_same_length_as_draws() -> None:
    draws_kwh = np.arange(1000, dtype=float)

    costs_gbp = apply_tariff_to_draws(draws_kwh, _tariff())

    assert len(costs_gbp) == 1000


def test_apply_tariff_unit_conversion_is_correct() -> None:
    costs_gbp = apply_tariff_to_draws(
        draws_kwh=np.array([1.0]),
        tariff=_tariff(unit_rate_p_per_kwh=100, standing_charge_p_per_day=0),
    )

    assert costs_gbp[0] == 1.0


def test_summarise_percentiles_ordered() -> None:
    summary = summarise_cost_percentiles(
        name="central",
        costs_gbp=np.arange(0, 1000),
    )

    assert summary.p10_gbp < summary.p50_gbp < summary.p90_gbp
    assert summary.p10_gbp == pytest.approx(99.9)
    assert summary.p50_gbp == pytest.approx(499.5)
    assert summary.p90_gbp == pytest.approx(899.1)


def test_summarise_percentiles_pydantic_round_trip() -> None:
    summary = summarise_cost_percentiles(
        name="central",
        costs_gbp=np.arange(0, 1000),
    )

    assert isinstance(summary, CostScenarioPercentiles)
    assert summary.name == "central"


def test_calculate_cost_by_scenario_handles_multiple_tariffs() -> None:
    tariffs = [
        _tariff(name="cheap", standing_charge_p_per_day=30, unit_rate_p_per_kwh=15),
        _tariff(name="expensive", standing_charge_p_per_day=60, unit_rate_p_per_kwh=35),
    ]

    results = calculate_cost_by_scenario(
        draws_kwh=np.array([1000.0, 2000.0, 3000.0]),
        tariffs=tariffs,
    )

    assert len(results) == 2
    assert all(isinstance(result, CostScenarioPercentiles) for result in results)
    assert [result.name for result in results] == ["cheap", "expensive"]
    assert results[1].p50_gbp > results[0].p50_gbp


def test_calculate_cost_by_scenario_empty_tariff_list() -> None:
    assert calculate_cost_by_scenario(draws_kwh=np.array([1000.0]), tariffs=[]) == []
