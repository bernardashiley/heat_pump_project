import numpy as np
import pytest

from app.forecast.demand import (
    _cold_inlet_c,
    calculate_annual_dhw_demand,
    calculate_daily_space_heating_demand,
    derive_hlc_w_per_k,
    distribute_daily_dhw_demand,
)
from app.models import DhwInput, PropertyInput


def _property_input(**overrides: object) -> PropertyInput:
    values = {
        "floor_area_m2": 95,
        "hlc_w_per_k": None,
        "heat_loss_design_w": 5000,
        "t_design_outdoor_c": -2,
        "t_internal_c": 21,
        "t_base_c": 15.5,
        "postcode": "OX1 2JD",
    }
    values.update(overrides)
    return PropertyInput(**values)


def _dhw_input(**overrides: object) -> DhwInput:
    values = {
        "occupants": 3,
        "cylinder_l": 210,
        "t_setpoint_c": 48,
        "t_flow_dhw_c": 52,
    }
    values.update(overrides)
    return DhwInput(**values)


def _expected_cold_inlet_c(day_of_year: int) -> float:
    if 152 <= day_of_year <= 243:
        return 10.0
    if day_of_year >= 335 or day_of_year <= 59:
        return 6.0
    if 60 <= day_of_year <= 151:
        return 6.0 + ((day_of_year - 60) / 91) * 4.0
    if 244 <= day_of_year <= 334:
        return 10.0 - ((day_of_year - 244) / 90) * 4.0
    raise ValueError("day_of_year must be in the range 1..365")


def _expected_annual_dhw_kwh(occupants: int, t_setpoint_c: float) -> float:
    total = 0.0
    for day_of_year in range(1, 366):
        total += (
            50
            * 4.186
            * (t_setpoint_c - _expected_cold_inlet_c(day_of_year))
            / 3600
        )
    return occupants * total


def test_derive_hlc_from_design_heat_loss() -> None:
    property_input = _property_input(
        heat_loss_design_w=5000,
        t_internal_c=21,
        t_design_outdoor_c=-2,
    )

    assert derive_hlc_w_per_k(property_input) == pytest.approx(5000 / 23)


def test_derive_hlc_uses_direct_value_when_provided() -> None:
    property_input = _property_input(
        hlc_w_per_k=180,
        heat_loss_design_w=5000,
        t_internal_c=21,
        t_design_outdoor_c=-2,
    )

    assert derive_hlc_w_per_k(property_input) == 180


def test_space_heating_demand_zero_above_base_temperature() -> None:
    demand = calculate_daily_space_heating_demand(
        t_out_c=np.array([16.0, 20.0, 25.0]),
        hlc_w_per_k=200,
        t_base_c=15.5,
    )

    np.testing.assert_array_equal(demand, np.array([0.0, 0.0, 0.0]))


def test_space_heating_demand_known_value() -> None:
    demand = calculate_daily_space_heating_demand(
        t_out_c=np.array([5.5]),
        hlc_w_per_k=200,
        t_base_c=15.5,
    )

    assert demand[0] == pytest.approx(48.0, abs=1e-9)


def test_space_heating_demand_monotone_in_outdoor_temp() -> None:
    demand = calculate_daily_space_heating_demand(
        t_out_c=np.arange(-10, 16),
        hlc_w_per_k=200,
        t_base_c=15.5,
    )

    assert np.all(np.diff(demand) <= 0)


def test_cold_inlet_summer_minimum() -> None:
    assert _cold_inlet_c(200) == 10.0


def test_cold_inlet_winter_minimum() -> None:
    assert _cold_inlet_c(15) == 6.0


def test_cold_inlet_spring_linear() -> None:
    assert _cold_inlet_c(105) == pytest.approx(8.0, abs=0.5)


def test_annual_dhw_demand_known_value() -> None:
    dhw = _dhw_input(occupants=3, t_setpoint_c=48)
    expected = _expected_annual_dhw_kwh(occupants=3, t_setpoint_c=48)

    assert calculate_annual_dhw_demand(dhw) == pytest.approx(expected, abs=1e-6)


def test_annual_dhw_demand_scales_with_occupants() -> None:
    one_occupant = calculate_annual_dhw_demand(_dhw_input(occupants=1))
    two_occupants = calculate_annual_dhw_demand(_dhw_input(occupants=2))

    assert two_occupants == pytest.approx(2 * one_occupant, abs=1e-12)


def test_annual_dhw_demand_scales_with_setpoint_gap() -> None:
    cold_inlet_mean_c = np.mean(
        [_expected_cold_inlet_c(day_of_year) for day_of_year in range(1, 366)]
    )
    lower_setpoint_c = 48
    higher_setpoint_c = 58

    lower_demand = calculate_annual_dhw_demand(
        _dhw_input(occupants=1, t_setpoint_c=lower_setpoint_c, t_flow_dhw_c=58)
    )
    higher_demand = calculate_annual_dhw_demand(
        _dhw_input(occupants=1, t_setpoint_c=higher_setpoint_c, t_flow_dhw_c=58)
    )

    assert higher_demand / lower_demand == pytest.approx(
        (higher_setpoint_c - cold_inlet_mean_c)
        / (lower_setpoint_c - cold_inlet_mean_c)
    )


def test_distribute_daily_dhw_demand_sums_to_annual() -> None:
    annual_dhw_kwh = 1234.5

    daily_dhw_kwh = distribute_daily_dhw_demand(annual_dhw_kwh)

    assert np.sum(daily_dhw_kwh) == pytest.approx(annual_dhw_kwh, abs=1e-9)


def test_distribute_daily_dhw_demand_uniform() -> None:
    daily_dhw_kwh = distribute_daily_dhw_demand(annual_dhw_kwh=1234.5)

    assert np.allclose(daily_dhw_kwh, daily_dhw_kwh[0], atol=1e-12)
