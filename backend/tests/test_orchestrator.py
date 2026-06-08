from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest
import respx

from app.forecast.monte_carlo import DEFAULT_CACHE_DIR, forecast_from_request
from app.models import (
    DhwInput,
    ForecastRequest,
    ForecastResponse,
    HeatPumpInput,
    PropertyInput,
    TariffScenarioInput,
)


def _mock_postcode(
    router: respx.MockRouter,
    latitude: float = 51.75,
    longitude: float = -1.25,
) -> respx.Route:
    return router.get(host="api.postcodes.io").mock(
        return_value=httpx.Response(
            200,
            json={"result": {"latitude": latitude, "longitude": longitude}},
        )
    )


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


def _mock_open_meteo(router: respx.MockRouter) -> respx.Route:
    return router.get(host="archive-api.open-meteo.com").mock(
        return_value=httpx.Response(200, json=_open_meteo_payload())
    )


def _forecast_request(
    scop: float = 3.9,
    t_flow_sh_c: float = 45,
    defrost_penalty_peak_pct: float = 0,
    tariffs: list[TariffScenarioInput] | None = None,
) -> ForecastRequest:
    if tariffs is None:
        tariffs = [
            TariffScenarioInput(
                name="central",
                standing_charge_p_per_day=53,
                unit_rate_p_per_kwh=27,
            )
        ]
    return ForecastRequest(
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
            scop=scop,
            t_flow_sh_c=t_flow_sh_c,
            t_design_outdoor_c=-2,
            defrost_penalty_peak_pct=defrost_penalty_peak_pct,
        ),
        dhw=DhwInput(
            occupants=3,
            cylinder_l=210,
            t_setpoint_c=48,
            t_flow_dhw_c=52,
        ),
        tariff_scenarios=tariffs,
    )


def _mock_apis(router: respx.MockRouter) -> None:
    _mock_postcode(router)
    _mock_open_meteo(router)


def _assert_ordered_percentiles(p10: float, p50: float, p90: float) -> None:
    assert p10 <= p50 <= p90


def test_orchestrator_end_to_end_returns_valid_response(
    tmp_path: Path,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_apis(respx_mock)

    response = forecast_from_request(_forecast_request(), cache_dir=tmp_path)

    assert isinstance(response, ForecastResponse)
    assert 0.30 <= response.fitted_eta <= 0.65
    _assert_ordered_percentiles(
        response.space_heating.p10_kwh,
        response.space_heating.p50_kwh,
        response.space_heating.p90_kwh,
    )
    _assert_ordered_percentiles(
        response.dhw.p10_kwh,
        response.dhw.p50_kwh,
        response.dhw.p90_kwh,
    )
    _assert_ordered_percentiles(
        response.total.p10_kwh,
        response.total.p50_kwh,
        response.total.p90_kwh,
    )
    assert len(response.draws_kwh) == 1000
    assert len(response.monthly_breakdown_median_kwh) == 12
    assert len(response.cost_by_scenario) == 1
    assert response.cost_by_scenario[0].name == "central"
    assert response.assumptions.fitted_eta == response.fitted_eta


def test_orchestrator_warns_on_eta_boundary(
    tmp_path: Path,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_apis(respx_mock)

    response = forecast_from_request(
        _forecast_request(scop=8, t_flow_sh_c=60),
        cache_dir=tmp_path,
    )

    assert any(
        "eta" in warning or "boundary" in warning or "inconsistent" in warning
        for warning in response.warnings
    )


def test_orchestrator_cost_scales_with_tariff(
    tmp_path: Path,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_apis(respx_mock)
    tariffs = [
        TariffScenarioInput(
            name="cheap",
            standing_charge_p_per_day=40,
            unit_rate_p_per_kwh=15,
        ),
        TariffScenarioInput(
            name="expensive",
            standing_charge_p_per_day=40,
            unit_rate_p_per_kwh=35,
        ),
    ]

    response = forecast_from_request(
        _forecast_request(tariffs=tariffs),
        cache_dir=tmp_path,
    )

    assert [scenario.name for scenario in response.cost_by_scenario] == [
        "cheap",
        "expensive",
    ]
    assert response.cost_by_scenario[1].p50_gbp > response.cost_by_scenario[0].p50_gbp


def test_orchestrator_uses_cache_dir_argument(
    tmp_path: Path,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_apis(respx_mock)

    forecast_from_request(_forecast_request(), cache_dir=tmp_path)

    assert list(tmp_path.glob("*.parquet"))
    default_cache_file = DEFAULT_CACHE_DIR / "51.7500_-1.2500_20.parquet"
    assert not default_cache_file.exists()


def test_orchestrator_sh_dhw_total_consistency(
    tmp_path: Path,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_apis(respx_mock)

    response = forecast_from_request(_forecast_request(), cache_dir=tmp_path)

    assert response.total.p10_kwh == pytest.approx(
        response.space_heating.p10_kwh + response.dhw.p10_kwh,
        rel=0.05,
    )
    assert response.total.p50_kwh == pytest.approx(
        response.space_heating.p50_kwh + response.dhw.p50_kwh,
        rel=0.05,
    )
    assert response.total.p90_kwh == pytest.approx(
        response.space_heating.p90_kwh + response.dhw.p90_kwh,
        rel=0.05,
    )


def test_orchestrator_monthly_breakdown_winter_months_nonzero(
    tmp_path: Path,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_apis(respx_mock)

    response = forecast_from_request(_forecast_request(), cache_dir=tmp_path)

    assert all(value > 0 for value in response.monthly_breakdown_median_kwh[0:3])
    assert all(value == 0 for value in response.monthly_breakdown_median_kwh[3:9])
    assert all(value > 0 for value in response.monthly_breakdown_median_kwh[9:12])


def test_orchestrator_with_defrost_penalty_raises_electricity(
    tmp_path: Path,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_apis(respx_mock)

    unpenalised = forecast_from_request(
        _forecast_request(scop=5.0, defrost_penalty_peak_pct=0),
        cache_dir=tmp_path,
    )
    penalised = forecast_from_request(
        _forecast_request(scop=5.0, defrost_penalty_peak_pct=0.12),
        cache_dir=tmp_path,
    )

    increase_fraction = (
        (penalised.total.p50_kwh - unpenalised.total.p50_kwh)
        / unpenalised.total.p50_kwh
    )

    assert penalised.total.p50_kwh > unpenalised.total.p50_kwh
    assert 0.04 <= increase_fraction <= 0.15
