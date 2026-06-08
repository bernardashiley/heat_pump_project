from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest
import respx

from app.forecast.calibrate import (
    aggregate_monthly_kwh,
    calculate_calibration_metrics,
    calculate_pit_value,
    run_walk_forward_backtest,
)
from app.models import (
    CalibrationRequest,
    CalibrationResponse,
    CalibrationYearResult,
    DhwInput,
    HeatPumpInput,
    PastMonthlyKwh,
    PropertyInput,
    TariffScenarioInput,
)


def _monthly_readings(year: int, values: list[float]) -> list[PastMonthlyKwh]:
    return [
        PastMonthlyKwh(year=year, month=month, kwh=kwh)
        for month, kwh in enumerate(values, start=1)
    ]


def _open_meteo_payload() -> dict[str, dict[str, list]]:
    dates = pd.date_range("2006-10-01", "2026-03-31", freq="D")
    winter_dates = dates[dates.month.isin({1, 2, 3, 10, 11, 12})]
    temperatures = []
    for index, date in enumerate(winter_dates):
        seasonal = 5.0 + 4.0 * np.sin(index / 29.0)
        if date.month in {1, 2}:
            seasonal -= 3.0
        temperatures.append(float(seasonal))

    return {
        "daily": {
            "time": [date.strftime("%Y-%m-%d") for date in winter_dates],
            "temperature_2m_mean": temperatures,
        }
    }


def _mock_apis(router: respx.MockRouter) -> None:
    router.get(host="api.postcodes.io").mock(
        return_value=httpx.Response(
            200,
            json={"result": {"latitude": 51.75, "longitude": -1.25}},
        )
    )
    router.get(host="archive-api.open-meteo.com").mock(
        return_value=httpx.Response(200, json=_open_meteo_payload())
    )


def _year_result(
    year: int,
    realised_kwh: float,
    p50_kwh: float,
    in_band: bool,
) -> CalibrationYearResult:
    return CalibrationYearResult(
        year=year,
        realised_kwh=realised_kwh,
        p10_kwh=max(0, p50_kwh - 100),
        p50_kwh=p50_kwh,
        p90_kwh=p50_kwh + 100,
        in_band=in_band,
    )


def _calibration_request(
    past_monthly_kwh: list[PastMonthlyKwh] | None = None,
) -> CalibrationRequest:
    if past_monthly_kwh is None:
        past_monthly_kwh = _monthly_readings(2024, [250] * 12)

    return CalibrationRequest(
        property=PropertyInput(
            floor_area_m2=95,
            hlc_w_per_k=180,
            heat_loss_design_w=None,
            t_design_outdoor_c=-2,
            t_internal_c=21,
            t_base_c=15.5,
            postcode="OX1 2JD",
        ),
        heat_pump=HeatPumpInput(
            scop=3.9,
            t_flow_sh_c=45,
            t_design_outdoor_c=-2,
        ),
        dhw=DhwInput(
            occupants=3,
            cylinder_l=210,
            t_setpoint_c=48,
            t_flow_dhw_c=52,
        ),
        tariff_scenarios=[
            TariffScenarioInput(
                name="central",
                standing_charge_p_per_day=53,
                unit_rate_p_per_kwh=27,
            )
        ],
        past_monthly_kwh=past_monthly_kwh,
    )


def test_aggregate_complete_year() -> None:
    values = list(range(100, 1300, 100))

    annual = aggregate_monthly_kwh(_monthly_readings(2024, values))

    expected = pd.DataFrame(
        {"year": [2024], "realised_kwh": [float(sum(range(100, 1300, 100)))]}
    )
    pd.testing.assert_frame_equal(annual, expected)


def test_aggregate_drops_partial_years() -> None:
    readings = _monthly_readings(2023, [100] * 12)
    readings.extend(_monthly_readings(2024, [100] * 5))

    annual = aggregate_monthly_kwh(readings)

    assert annual["year"].tolist() == [2023]


def test_aggregate_raises_on_no_complete_years() -> None:
    with pytest.raises(ValueError, match="no complete years"):
        aggregate_monthly_kwh(_monthly_readings(2024, [100] * 5))


def test_aggregate_sorted_ascending() -> None:
    readings = _monthly_readings(2024, [100] * 12)
    readings.extend(_monthly_readings(2023, [100] * 12))

    annual = aggregate_monthly_kwh(readings)

    assert annual["year"].tolist() == [2023, 2024]


def test_pit_value_below_all_draws() -> None:
    assert calculate_pit_value(-1, np.array([0, 1, 2, 3])) == 0


def test_pit_value_above_all_draws() -> None:
    assert calculate_pit_value(100, np.array([0, 1, 2, 3])) == 1


def test_pit_value_median() -> None:
    assert calculate_pit_value(5, np.array([1, 2, 3, 4, 6, 7, 8, 9])) == 0.5


def test_pit_uniform_for_uniform_data() -> None:
    rng = np.random.default_rng(42)
    predicted_draws = rng.uniform(0, 100, 10_000)
    realised_values = rng.uniform(0, 100, 1000)

    pits = np.array(
        [calculate_pit_value(realised, predicted_draws) for realised in realised_values]
    )
    histogram = np.histogram(pits, bins=10, range=(0, 1))[0] / 1000

    assert np.std(histogram) < 0.05


def test_metrics_mae_kwh() -> None:
    per_year_results = [
        _year_result(2023, realised_kwh=1000, p50_kwh=900, in_band=True),
        _year_result(2024, realised_kwh=2000, p50_kwh=2300, in_band=True),
    ]

    response = calculate_calibration_metrics(
        per_year_results=per_year_results,
        pit_values=np.array([0.2, 0.8]),
        realised_costs_gbp=np.array([300, 600]),
        predicted_median_costs_gbp=np.array([280, 650]),
    )

    assert response.mae_kwh == pytest.approx(
        np.mean(np.abs(np.array([1000, 2000]) - np.array([900, 2300])))
    )
    assert response.mae_gbp == pytest.approx(
        np.mean(np.abs(np.array([300, 600]) - np.array([280, 650])))
    )


def test_metrics_coverage_80_with_known_band_results() -> None:
    per_year_results = [
        _year_result(2000 + index, 1000, 1000, in_band=index < 8)
        for index in range(10)
    ]

    response = calculate_calibration_metrics(
        per_year_results=per_year_results,
        pit_values=np.linspace(0, 1, 10, endpoint=False),
        realised_costs_gbp=np.ones(10),
        predicted_median_costs_gbp=np.ones(10),
    )

    assert response.coverage_80_pct == 0.8


def test_metrics_pit_histogram_sums_to_one() -> None:
    response = calculate_calibration_metrics(
        per_year_results=[_year_result(2024, 1000, 1000, True)],
        pit_values=np.array([0.25]),
        realised_costs_gbp=np.array([300]),
        predicted_median_costs_gbp=np.array([300]),
    )

    assert sum(response.pit_bins) == pytest.approx(1.0, abs=1e-12)


def test_metrics_pit_histogram_uniform_input_is_flat() -> None:
    response = calculate_calibration_metrics(
        per_year_results=[_year_result(2024, 1000, 1000, True)],
        pit_values=np.linspace(0, 1, 10000, endpoint=False),
        realised_costs_gbp=np.array([300]),
        predicted_median_costs_gbp=np.array([300]),
    )

    assert all(0.09 <= pit_bin <= 0.11 for pit_bin in response.pit_bins)


def test_walk_forward_returns_response_for_single_complete_year(
    tmp_path: Path,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_apis(respx_mock)

    response = run_walk_forward_backtest(_calibration_request(), cache_dir=tmp_path)

    assert isinstance(response, CalibrationResponse)
    assert len(response.per_year_results) == 1
    assert response.per_year_results[0].year == 2024
    assert len(response.pit_bins) == 10
    assert sum(response.pit_bins) == pytest.approx(1.0)
    assert 0 <= response.coverage_80_pct <= 1


def test_walk_forward_handles_two_years(
    tmp_path: Path,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_apis(respx_mock)
    readings = _monthly_readings(2023, [240] * 12)
    readings.extend(_monthly_readings(2024, [260] * 12))

    response = run_walk_forward_backtest(
        _calibration_request(readings),
        cache_dir=tmp_path,
    )

    assert len(response.per_year_results) == 2
    assert [result.year for result in response.per_year_results] == [2023, 2024]


def test_walk_forward_in_band_logic(
    tmp_path: Path,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_apis(respx_mock)
    probe = run_walk_forward_backtest(_calibration_request(), cache_dir=tmp_path)
    p50_kwh = probe.per_year_results[0].p50_kwh
    p90_kwh = probe.per_year_results[0].p90_kwh

    inside_response = run_walk_forward_backtest(
        _calibration_request(_monthly_readings(2024, [p50_kwh / 12] * 12)),
        cache_dir=tmp_path,
    )
    outside_response = run_walk_forward_backtest(
        _calibration_request(_monthly_readings(2024, [(p90_kwh * 10) / 12] * 12)),
        cache_dir=tmp_path,
    )

    assert inside_response.per_year_results[0].in_band is True
    assert outside_response.per_year_results[0].in_band is False
