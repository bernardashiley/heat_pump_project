import os
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pandas as pd
import pytest
import respx

from app.forecast.climate import (
    OPEN_METEO_BASE_URL,
    fetch_year_daily_mean_temperatures,
    fetch_winter_daily_mean_temperatures,
    geocode_postcode,
    load_or_fetch_climate,
)
from app.models import PropertyInput


def _property_input(postcode: str = "OX1 2JD") -> PropertyInput:
    return PropertyInput(
        floor_area_m2=95,
        hlc_w_per_k=180,
        heat_loss_design_w=None,
        t_design_outdoor_c=-2,
        t_internal_c=21,
        t_base_c=15.5,
        postcode=postcode,
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


def _open_meteo_payload(start_date: str, end_date: str) -> dict[str, dict[str, list]]:
    dates = pd.date_range(start_date, end_date, freq="D")
    return {
        "daily": {
            "time": [date.strftime("%Y-%m-%d") for date in dates],
            "temperature_2m_mean": [float(i % 20) for i in range(len(dates))],
        }
    }


def _mock_open_meteo(
    router: respx.MockRouter,
    payload: dict[str, dict[str, list]],
) -> respx.Route:
    return router.get(host="archive-api.open-meteo.com").mock(
        return_value=httpx.Response(200, json=payload)
    )


def _mock_open_meteo_dynamic(router: respx.MockRouter) -> respx.Route:
    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        return httpx.Response(
            200,
            json=_open_meteo_payload(params["start_date"], params["end_date"]),
        )

    return router.get(host="archive-api.open-meteo.com").mock(side_effect=handler)


def test_geocode_postcode_happy_path(respx_mock: respx.MockRouter) -> None:
    _mock_postcode(respx_mock, latitude=51.75, longitude=-1.25)

    assert geocode_postcode("OX1 2JD") == (51.75, -1.25)


def test_geocode_postcode_404_raises_value_error(
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.get(host="api.postcodes.io").mock(return_value=httpx.Response(404))

    with pytest.raises(ValueError, match="OX1 2JD"):
        geocode_postcode("OX1 2JD")


def test_geocode_postcode_timeout_propagates(respx_mock: respx.MockRouter) -> None:
    respx_mock.get(host="api.postcodes.io").mock(
        side_effect=httpx.TimeoutException("timed out")
    )

    with pytest.raises(httpx.TimeoutException):
        geocode_postcode("OX1 2JD")


def test_fetch_filters_to_winter_only(respx_mock: respx.MockRouter) -> None:
    _mock_open_meteo(respx_mock, _open_meteo_payload("2025-04-01", "2026-03-31"))

    climate = fetch_winter_daily_mean_temperatures(51.75, -1.25, winters=1)

    assert len(climate) == 182
    assert set(climate["date"].dt.month).issubset({1, 2, 3, 10, 11, 12})


def test_fetch_year_returns_full_calendar_years(respx_mock: respx.MockRouter) -> None:
    _mock_open_meteo(respx_mock, _open_meteo_payload("2024-01-01", "2025-12-31"))

    climate = fetch_year_daily_mean_temperatures(51.75, -1.25, years=2)

    assert len(climate) == 731
    assert set(climate["date"].dt.month) == set(range(1, 13))
    assert set(climate["year_id"]) == {0, 1}
    assert len(climate.loc[climate["year_id"] == 0]) == 366
    assert len(climate.loc[climate["year_id"] == 1]) == 365


def test_fetch_assigns_correct_winter_id(respx_mock: respx.MockRouter) -> None:
    _mock_open_meteo(respx_mock, _open_meteo_payload("2024-10-01", "2026-03-31"))

    climate = fetch_winter_daily_mean_temperatures(51.75, -1.25, winters=2)

    assert set(climate.loc[climate["date"] < "2025-04-01", "winter_id"]) == {0}
    assert set(climate.loc[climate["date"] >= "2025-10-01", "winter_id"]) == {1}


def test_fetch_raises_on_data_gaps(respx_mock: respx.MockRouter) -> None:
    payload = _open_meteo_payload("2025-04-01", "2026-03-31")
    payload["daily"]["time"].pop()
    payload["daily"]["temperature_2m_mean"].pop()
    _mock_open_meteo(respx_mock, payload)

    with pytest.raises(ValueError, match="gaps"):
        fetch_winter_daily_mean_temperatures(51.75, -1.25, winters=1)


def test_load_or_fetch_uses_cache_when_fresh(
    tmp_path: Path,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_postcode(respx_mock, latitude=51.75, longitude=-1.25)
    open_meteo_route = respx_mock.get(host="archive-api.open-meteo.com").mock(
        return_value=httpx.Response(500)
    )
    cached = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-10-01"]),
            "winter_id": [0],
            "t_out_c": [7.5],
        }
    )
    cache_path = tmp_path / "51.7500_-1.2500_1.parquet"
    cached.to_parquet(cache_path, index=False)

    climate = load_or_fetch_climate(_property_input(), tmp_path, winters=1)

    pd.testing.assert_frame_equal(climate, cached)
    assert open_meteo_route.call_count == 0


def test_load_or_fetch_refreshes_stale_cache(
    tmp_path: Path,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_postcode(respx_mock, latitude=51.75, longitude=-1.25)
    open_meteo_route = _mock_open_meteo(
        respx_mock,
        _open_meteo_payload("2025-04-01", "2026-03-31")
    )
    stale = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-10-01"]),
            "winter_id": [0],
            "t_out_c": [7.5],
        }
    )
    cache_path = tmp_path / "51.7500_-1.2500_1.parquet"
    stale.to_parquet(cache_path, index=False)
    stale_time = (datetime.now() - timedelta(days=60)).timestamp()
    os.utime(cache_path, (stale_time, stale_time))

    climate = load_or_fetch_climate(_property_input(), tmp_path, winters=1)

    assert open_meteo_route.call_count == 1
    assert len(climate) == 182


def test_load_or_fetch_atomic_write(
    tmp_path: Path,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_postcode(respx_mock, latitude=51.75, longitude=-1.25)
    _mock_open_meteo(respx_mock, _open_meteo_payload("2025-04-01", "2026-03-31"))

    load_or_fetch_climate(_property_input(), tmp_path, winters=1)

    assert (tmp_path / "51.7500_-1.2500_1.parquet").exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_load_or_fetch_full_year_uses_distinct_cache_key(
    tmp_path: Path,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_postcode(respx_mock, latitude=51.75, longitude=-1.25)
    _mock_open_meteo(respx_mock, _open_meteo_payload("2025-01-01", "2025-12-31"))

    load_or_fetch_climate(
        _property_input(),
        tmp_path,
        winters=1,
        demand_period_mode="full_year",
    )

    assert (tmp_path / "51.7500_-1.2500_1_full.parquet").exists()
    assert not (tmp_path / "51.7500_-1.2500_1.parquet").exists()


def test_load_or_fetch_full_year_and_winter_caches_do_not_contaminate(
    tmp_path: Path,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_postcode(respx_mock, latitude=51.75, longitude=-1.25)
    _mock_open_meteo_dynamic(respx_mock)

    winter = load_or_fetch_climate(_property_input(), tmp_path, winters=1)
    full_year = load_or_fetch_climate(
        _property_input(),
        tmp_path,
        winters=1,
        demand_period_mode="full_year",
    )

    assert (tmp_path / "51.7500_-1.2500_1.parquet").exists()
    assert (tmp_path / "51.7500_-1.2500_1_full.parquet").exists()
    assert "winter_id" in winter.columns
    assert "year_id" not in winter.columns
    assert "year_id" in full_year.columns
    assert "winter_id" not in full_year.columns
    assert len(winter) == 182
    assert len(full_year) == 365


def test_cache_filename_does_not_contain_postcode(
    tmp_path: Path,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_postcode(respx_mock, latitude=51.75, longitude=-1.25)
    _mock_open_meteo(respx_mock, _open_meteo_payload("2025-04-01", "2026-03-31"))

    load_or_fetch_climate(_property_input(postcode="OX1 2JD"), tmp_path, winters=1)

    cache_names = [path.name for path in tmp_path.iterdir()]
    assert all("OX1" not in name and "2JD" not in name for name in cache_names)
