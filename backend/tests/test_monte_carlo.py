import numpy as np
import pytest

from app.forecast.monte_carlo import (
    calculate_annual_electricity_by_winter,
    calculate_daily_electricity,
    generate_electricity_draws,
    sample_occupancy_draws,
)


def test_daily_electricity_zero_demand_yields_zero_sh() -> None:
    electricity_sh_kwh, _, _ = calculate_daily_electricity(
        daily_space_heating_kwh=np.array([0.0, 10.0]),
        daily_dhw_kwh=np.array([5.0, 5.0]),
        space_heating_cop=np.array([0.0, 2.0]),
        dhw_cop=np.array([2.0, 2.0]),
    )

    assert electricity_sh_kwh[0] == 0.0


def test_daily_electricity_total_is_sum_of_parts() -> None:
    electricity_sh_kwh, electricity_dhw_kwh, electricity_total_kwh = (
        calculate_daily_electricity(
            daily_space_heating_kwh=np.array([10.0, 20.0, 30.0]),
            daily_dhw_kwh=np.array([3.0, 4.0, 5.0]),
            space_heating_cop=np.array([2.0, 4.0, 5.0]),
            dhw_cop=np.array([3.0, 2.0, 2.5]),
        )
    )

    np.testing.assert_array_equal(
        electricity_total_kwh,
        electricity_sh_kwh + electricity_dhw_kwh,
    )


def test_daily_electricity_division_by_cop() -> None:
    electricity_sh_kwh, electricity_dhw_kwh, _ = calculate_daily_electricity(
        daily_space_heating_kwh=np.array([10.0, 20.0]),
        daily_dhw_kwh=np.array([8.0, 15.0]),
        space_heating_cop=np.array([2.0, 4.0]),
        dhw_cop=np.array([2.0, 3.0]),
    )

    np.testing.assert_array_equal(electricity_sh_kwh, np.array([5.0, 5.0]))
    np.testing.assert_array_equal(electricity_dhw_kwh, np.array([4.0, 5.0]))
    assert electricity_sh_kwh.shape == (2,)
    assert electricity_dhw_kwh.shape == (2,)


def test_daily_electricity_shape_preserved() -> None:
    length = 365

    outputs = calculate_daily_electricity(
        daily_space_heating_kwh=np.ones(length),
        daily_dhw_kwh=np.ones(length),
        space_heating_cop=np.full(length, 2.0),
        dhw_cop=np.full(length, 2.0),
    )

    assert all(output.shape == (length,) for output in outputs)


def test_annual_by_winter_simple_grouping() -> None:
    annual_kwh = calculate_annual_electricity_by_winter(
        daily_total_electricity_kwh=np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]),
        winter_index=np.array([0, 0, 0, 1, 1, 1]),
    )

    np.testing.assert_array_equal(annual_kwh, np.array([6.0, 15.0]))


def test_annual_by_winter_handles_twenty_winters() -> None:
    day_counts = np.arange(170, 190)
    winter_index = np.repeat(np.arange(20), day_counts)
    daily_total_electricity_kwh = np.ones(np.sum(day_counts))

    annual_kwh = calculate_annual_electricity_by_winter(
        daily_total_electricity_kwh=daily_total_electricity_kwh,
        winter_index=winter_index,
    )

    np.testing.assert_array_equal(annual_kwh, day_counts.astype(float))


def test_draws_count_and_shape() -> None:
    draws = generate_electricity_draws(
        annual_electricity_by_winter_kwh=np.array([1000.0, 2000.0]),
        draw_count=1000,
        random_seed=42,
    )

    assert draws.shape == (1000,)


def test_draws_non_negative() -> None:
    draws = generate_electricity_draws(
        annual_electricity_by_winter_kwh=np.array([100.0, 200.0]),
        draw_count=10000,
        residual_sigma_fraction=0.5,
        random_seed=3,
    )

    assert np.min(draws) >= 0
    assert (draws == 0).sum() >= 100


def test_draws_reproducible_with_seed() -> None:
    first = generate_electricity_draws(
        annual_electricity_by_winter_kwh=np.array([1000.0, 2000.0]),
        random_seed=42,
    )
    second = generate_electricity_draws(
        annual_electricity_by_winter_kwh=np.array([1000.0, 2000.0]),
        random_seed=42,
    )

    np.testing.assert_array_equal(first, second)


def test_draws_different_seeds_different() -> None:
    first = generate_electricity_draws(
        annual_electricity_by_winter_kwh=np.array([1000.0, 2000.0]),
        random_seed=1,
    )
    second = generate_electricity_draws(
        annual_electricity_by_winter_kwh=np.array([1000.0, 2000.0]),
        random_seed=2,
    )

    assert not np.array_equal(first, second)


def test_occupancy_draws_are_seeded_and_within_support() -> None:
    first = sample_occupancy_draws(draw_count=1000, random_seed=42)
    second = sample_occupancy_draws(draw_count=1000, random_seed=42)

    np.testing.assert_array_equal(first, second)
    assert set(first).issubset({1, 2, 3, 4, 5})
    assert set(first) == {1, 2, 3, 4, 5}


def test_draws_mean_converges_to_population_mean() -> None:
    draws = generate_electricity_draws(
        annual_electricity_by_winter_kwh=np.array(
            [1000.0, 2000.0, 3000.0, 4000.0, 5000.0]
        ),
        draw_count=100_000,
        residual_sigma_fraction=0,
        random_seed=42,
    )

    assert np.mean(draws) == pytest.approx(3000, rel=0.01)


def test_draws_variance_decomposes() -> None:
    winters_kwh = np.array([1000.0, 2000.0, 3000.0, 4000.0, 5000.0])
    residual_sigma_fraction = 0.08
    draws = generate_electricity_draws(
        annual_electricity_by_winter_kwh=winters_kwh,
        draw_count=100_000,
        residual_sigma_fraction=residual_sigma_fraction,
        random_seed=42,
    )
    expected_variance = np.var(winters_kwh) + np.mean(
        (residual_sigma_fraction * winters_kwh) ** 2
    )

    assert np.var(draws) == pytest.approx(expected_variance, rel=0.05)
