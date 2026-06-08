from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import respx
from fastapi.testclient import TestClient

from app.main import app


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


def _forecast_request_json() -> dict:
    return {
        "property": {
            "floor_area_m2": 95,
            "hlc_w_per_k": 180,
            "heat_loss_design_w": None,
            "t_design_outdoor_c": -2,
            "t_internal_c": 21,
            "t_base_c": 15.5,
            "postcode": "OX1 2JD",
        },
        "heat_pump": {
            "scop": 3.9,
            "t_flow_sh_c": 45,
            "t_design_outdoor_c": -2,
        },
        "dhw": {
            "occupants": 3,
            "cylinder_l": 210,
            "t_setpoint_c": 48,
            "t_flow_dhw_c": 52,
        },
        "tariff_scenarios": [
            {
                "name": "central",
                "standing_charge_p_per_day": 53,
                "unit_rate_p_per_kwh": 27,
            }
        ],
    }


def test_forecast_endpoint_returns_real_response_via_orchestrator(
    tmp_path: Path,
    monkeypatch,
    respx_mock: respx.MockRouter,
) -> None:
    monkeypatch.chdir(tmp_path)
    _mock_apis(respx_mock)
    client = TestClient(app)

    response = client.post("/api/forecast", json=_forecast_request_json())

    assert response.status_code == 200
    payload = response.json()
    assert 0.30 <= payload["fitted_eta"] <= 0.65
    assert len(payload["draws_kwh"]) == 1000
    assert payload["total"]["p10_kwh"] > 0
    assert payload["cost_by_scenario"][0]["p50_gbp"] > 0


def test_healthz_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
