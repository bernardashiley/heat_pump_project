import json
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest
import respx

from app.forecast.monte_carlo import forecast_from_request
from app.models import ForecastRequest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


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
            json={"result": {"latitude": 53.96, "longitude": -1.08}},
        )
    )
    router.get(host="archive-api.open-meteo.com").mock(
        return_value=httpx.Response(200, json=_open_meteo_payload())
    )


def _assert_within_tolerance(actual: float, expected: dict) -> None:
    tolerance = expected["value"] * expected["tolerance_pct"] / 100
    assert actual == pytest.approx(expected["value"], abs=tolerance)


def test_trip2nd_reference_case_annual_cost_band(
    tmp_path: Path,
    respx_mock: respx.MockRouter,
) -> None:
    fixture = _load_fixture("trip2nd.json")
    _mock_apis(respx_mock)

    response = forecast_from_request(
        ForecastRequest.model_validate(fixture["forecast_request"]),
        cache_dir=tmp_path,
    )

    assert fixture["expected"]["metric"] == "annual_gbp"
    _assert_within_tolerance(
        response.cost_by_scenario[0].p50_gbp,
        fixture["expected"],
    )


def test_twentyman_reference_case_daily_kwh_average(
    tmp_path: Path,
    respx_mock: respx.MockRouter,
) -> None:
    fixture = _load_fixture("twentyman.json")
    _mock_apis(respx_mock)

    response = forecast_from_request(
        ForecastRequest.model_validate(fixture["forecast_request"]),
        cache_dir=tmp_path,
    )
    daily_kwh_average = response.total.p50_kwh / 365

    assert fixture["expected"]["metric"] == "daily_kwh_average"
    _assert_within_tolerance(daily_kwh_average, fixture["expected"])
