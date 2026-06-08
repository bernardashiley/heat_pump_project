import numpy as np
import pytest

from app.forecast.cop import (
    ETA_MAX,
    ETA_MIN,
    calculate_cop_curve,
    carnot_cop,
    defrost_penalty,
    fit_eta_from_scop,
)
from app.forecast.demand import calculate_daily_space_heating_demand


def _synthetic_scop(
    eta: float,
    daily_demand_kwh: np.ndarray,
    t_out_c: np.ndarray,
    t_flow_c: float,
) -> float:
    return np.sum(daily_demand_kwh) / np.sum(
        daily_demand_kwh / (eta * carnot_cop(t_out_c, t_flow_c))
    )


def test_carnot_rejects_flow_below_outdoor() -> None:
    with pytest.raises(ValueError):
        carnot_cop(t_out_c=np.array([5.0]), t_flow_c=4.0)

    with pytest.raises(ValueError):
        carnot_cop(t_out_c=np.array([5.0]), t_flow_c=5.0)


def test_carnot_value_is_correct_in_kelvin() -> None:
    expected = (45 + 273.15) / (45 - 0)

    actual = carnot_cop(t_out_c=np.array([0.0]), t_flow_c=45)

    assert actual[0] == pytest.approx(expected, abs=1e-6)


def test_cop_never_exceeds_carnot() -> None:
    t_out_c = np.arange(-15, 15.5, 0.5)

    cop = calculate_cop_curve(t_out_c=t_out_c, t_flow_c=45, eta=0.5)
    carnot = carnot_cop(t_out_c=t_out_c, t_flow_c=45)

    assert np.all(cop <= carnot + 1e-12)


def test_cop_monotonic_in_outdoor_temperature() -> None:
    t_out_c = np.arange(-15, 16)

    cop = calculate_cop_curve(t_out_c=t_out_c, t_flow_c=45, eta=0.5)

    assert np.all(np.diff(cop) >= 0)


def test_calculate_cop_curve_rejects_invalid_eta() -> None:
    with pytest.raises(ValueError):
        calculate_cop_curve(t_out_c=np.array([5.0]), t_flow_c=45, eta=0)

    with pytest.raises(ValueError):
        calculate_cop_curve(t_out_c=np.array([5.0]), t_flow_c=45, eta=-0.1)

    with pytest.raises(ValueError):
        calculate_cop_curve(t_out_c=np.array([5.0]), t_flow_c=45, eta=1.1)


def test_fit_eta_recovers_known_value() -> None:
    eta_true = 0.48
    t_flow_sh_c = 45
    t_out_c = np.linspace(-5, 12, 100)
    daily_demand_kwh = calculate_daily_space_heating_demand(
        t_out_c=t_out_c,
        hlc_w_per_k=200,
        t_base_c=15.5,
    )
    scop_synthetic = _synthetic_scop(
        eta=eta_true,
        daily_demand_kwh=daily_demand_kwh,
        t_out_c=t_out_c,
        t_flow_c=t_flow_sh_c,
    )

    eta, at_boundary = fit_eta_from_scop(
        scop=scop_synthetic,
        daily_space_heating_kwh=daily_demand_kwh,
        t_out_c=t_out_c,
        t_flow_sh_c=t_flow_sh_c,
    )

    assert eta == pytest.approx(eta_true, abs=1e-9)
    assert at_boundary is False


def test_fit_eta_clamps_low_and_flags() -> None:
    t_flow_sh_c = 45
    t_out_c = np.linspace(-5, 12, 100)
    daily_demand_kwh = calculate_daily_space_heating_demand(
        t_out_c=t_out_c,
        hlc_w_per_k=200,
        t_base_c=15.5,
    )
    scop_synthetic = _synthetic_scop(
        eta=0.20,
        daily_demand_kwh=daily_demand_kwh,
        t_out_c=t_out_c,
        t_flow_c=t_flow_sh_c,
    )

    eta, at_boundary = fit_eta_from_scop(
        scop=scop_synthetic,
        daily_space_heating_kwh=daily_demand_kwh,
        t_out_c=t_out_c,
        t_flow_sh_c=t_flow_sh_c,
    )

    assert eta == ETA_MIN
    assert at_boundary is True


def test_fit_eta_clamps_high_and_flags() -> None:
    t_flow_sh_c = 45
    t_out_c = np.linspace(-5, 12, 100)
    daily_demand_kwh = calculate_daily_space_heating_demand(
        t_out_c=t_out_c,
        hlc_w_per_k=200,
        t_base_c=15.5,
    )
    scop_synthetic = _synthetic_scop(
        eta=0.80,
        daily_demand_kwh=daily_demand_kwh,
        t_out_c=t_out_c,
        t_flow_c=t_flow_sh_c,
    )

    eta, at_boundary = fit_eta_from_scop(
        scop=scop_synthetic,
        daily_space_heating_kwh=daily_demand_kwh,
        t_out_c=t_out_c,
        t_flow_sh_c=t_flow_sh_c,
    )

    assert eta == ETA_MAX
    assert at_boundary is True


def test_fit_eta_within_bounds_not_flagged() -> None:
    t_flow_sh_c = 45
    t_out_c = np.linspace(-5, 12, 100)
    daily_demand_kwh = calculate_daily_space_heating_demand(
        t_out_c=t_out_c,
        hlc_w_per_k=200,
        t_base_c=15.5,
    )
    scop_synthetic = _synthetic_scop(
        eta=0.48,
        daily_demand_kwh=daily_demand_kwh,
        t_out_c=t_out_c,
        t_flow_c=t_flow_sh_c,
    )

    _, at_boundary = fit_eta_from_scop(
        scop=scop_synthetic,
        daily_space_heating_kwh=daily_demand_kwh,
        t_out_c=t_out_c,
        t_flow_sh_c=t_flow_sh_c,
    )

    assert at_boundary is False


def test_fit_eta_ignores_zero_demand_days() -> None:
    eta_true = 0.48
    t_flow_sh_c = 45
    t_out_c = np.concatenate([np.linspace(-5, 12, 50), np.linspace(16, 25, 50)])
    daily_demand_kwh = calculate_daily_space_heating_demand(
        t_out_c=t_out_c,
        hlc_w_per_k=200,
        t_base_c=15.5,
    )
    non_zero_demand = daily_demand_kwh != 0
    scop_synthetic = _synthetic_scop(
        eta=eta_true,
        daily_demand_kwh=daily_demand_kwh[non_zero_demand],
        t_out_c=t_out_c[non_zero_demand],
        t_flow_c=t_flow_sh_c,
    )

    eta_with_zeros, _ = fit_eta_from_scop(
        scop=scop_synthetic,
        daily_space_heating_kwh=daily_demand_kwh,
        t_out_c=t_out_c,
        t_flow_sh_c=t_flow_sh_c,
    )
    eta_without_zeros, _ = fit_eta_from_scop(
        scop=scop_synthetic,
        daily_space_heating_kwh=daily_demand_kwh[non_zero_demand],
        t_out_c=t_out_c[non_zero_demand],
        t_flow_sh_c=t_flow_sh_c,
    )

    assert eta_with_zeros == pytest.approx(eta_without_zeros, abs=1e-12)


def test_defrost_penalty_zero_default_preserves_existing_cop() -> None:
    t_out_c = np.arange(-10, 16, 1)
    eta = 0.5

    cop = calculate_cop_curve(
        t_out_c=t_out_c,
        t_flow_c=45,
        eta=eta,
        defrost_penalty_peak_pct=0,
    )

    assert np.all(cop == pytest.approx(eta * carnot_cop(t_out_c, 45)))


def test_defrost_penalty_reduces_cop_in_dip_zone() -> None:
    t_out_c = np.array([2.0, 10.0])
    unpenalised = calculate_cop_curve(t_out_c=t_out_c, t_flow_c=45, eta=0.5)
    penalised = calculate_cop_curve(
        t_out_c=t_out_c,
        t_flow_c=45,
        eta=0.5,
        defrost_penalty_peak_pct=0.12,
    )
    relative_loss = 1 - (penalised / unpenalised)

    assert relative_loss[0] == pytest.approx(0.12)
    assert relative_loss[1] < 0.01


def test_defrost_penalty_vanishes_above_8c() -> None:
    penalty = defrost_penalty(np.array([10.0]), peak=0.20)

    assert penalty[0] < 0.20 * 0.01


def test_defrost_penalty_vanishes_below_minus10c() -> None:
    penalty = defrost_penalty(np.array([-15.0]), peak=0.20)

    assert penalty[0] < 0.20 * 0.01


def test_cop_floor_at_unity() -> None:
    cop = calculate_cop_curve(
        t_out_c=np.array([-5.0, 2.0, 5.0]),
        t_flow_c=45,
        eta=0.30,
        defrost_penalty_peak_pct=0.30,
    )

    assert np.all(cop >= 1.0)


def test_defrost_penalty_changes_fitted_eta_consistently() -> None:
    t_out_c = np.linspace(-5, 8, 90)
    daily_demand_kwh = calculate_daily_space_heating_demand(
        t_out_c=t_out_c,
        hlc_w_per_k=200,
        t_base_c=15.5,
    )

    eta_zero, _ = fit_eta_from_scop(
        scop=3.0,
        daily_space_heating_kwh=daily_demand_kwh,
        t_out_c=t_out_c,
        t_flow_sh_c=45,
        defrost_penalty_peak_pct=0,
    )
    eta_penalty, _ = fit_eta_from_scop(
        scop=3.0,
        daily_space_heating_kwh=daily_demand_kwh,
        t_out_c=t_out_c,
        t_flow_sh_c=45,
        defrost_penalty_peak_pct=0.12,
    )

    assert eta_penalty > eta_zero


def test_defrost_penalty_function_unit_test() -> None:
    t_out_c = np.arange(-15, 16, 1)

    penalty = defrost_penalty(t_out_c, peak=0.12)

    assert penalty.shape == t_out_c.shape
    assert np.max(penalty) == pytest.approx(0.12)
    assert t_out_c[np.argmax(penalty)] == 2
    assert penalty[t_out_c == 10][0] < 0.001
    assert penalty[t_out_c == -15][0] < 0.001
