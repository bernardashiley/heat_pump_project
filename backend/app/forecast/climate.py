import os
from pathlib import Path
from time import time

import httpx
import pandas as pd

from app.models import PropertyInput

POSTCODES_IO_BASE_URL = "https://api.postcodes.io"
OPEN_METEO_BASE_URL = "https://archive-api.open-meteo.com/v1/archive"
HTTP_TIMEOUT_SECONDS = 10
CACHE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60
LATEST_COMPLETE_WINTER_END_YEAR = 2026
WINTER_MONTHS = {1, 2, 3, 10, 11, 12}


def geocode_postcode(postcode: str) -> tuple[float, float]:
    """Look up a UK postcode and return latitude and longitude.

    Implements MODEL.md §2 — Climate input.

    Inputs:
    - postcode: UK postcode string, used only for lookup and not persisted.

    Outputs:
    - tuple of latitude and longitude in decimal degrees.
    """
    url = f"{POSTCODES_IO_BASE_URL}/postcodes/{postcode}"
    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        response = client.get(url)
        if response.status_code == 404:
            raise ValueError(f"postcode not found: {postcode}")
        response.raise_for_status()

    result = response.json()["result"]
    return float(result["latitude"]), float(result["longitude"])


def _winter_start_year(date: pd.Timestamp) -> int:
    if date.month >= 10:
        return date.year
    return date.year - 1


def _expected_winter_days(start_year: int, winters: int) -> int:
    start_date = pd.Timestamp(year=start_year, month=10, day=1)
    end_date = pd.Timestamp(year=start_year + winters, month=3, day=31)
    dates = pd.date_range(start_date, end_date, freq="D")
    return int(dates.month.isin(WINTER_MONTHS).sum())


def fetch_winter_daily_mean_temperatures(
    latitude: float,
    longitude: float,
    winters: int = 20,
) -> pd.DataFrame:
    """Fetch historical winter daily mean outdoor temperatures for one location.

    Implements MODEL.md §2 — Climate input.

    Inputs:
    - latitude: site latitude in decimal degrees.
    - longitude: site longitude in decimal degrees.
    - winters: number of October-March winter realisations to fetch, count.

    Outputs:
    - pandas.DataFrame with winter identifiers, dates, and daily mean temperatures in °C.
    """
    start_year = LATEST_COMPLETE_WINTER_END_YEAR - winters
    start_date = f"{start_year}-10-01"
    end_date = f"{LATEST_COMPLETE_WINTER_END_YEAR}-03-31"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "daily": "temperature_2m_mean",
        "timezone": "Europe/London",
    }

    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        response = client.get(OPEN_METEO_BASE_URL, params=params)
        response.raise_for_status()

    daily = response.json()["daily"]
    climate = pd.DataFrame(
        {
            "date": pd.to_datetime(daily["time"]),
            "t_out_c": daily["temperature_2m_mean"],
        }
    )
    climate = climate[climate["date"].dt.month.isin(WINTER_MONTHS)].copy()
    climate["winter_start_year"] = climate["date"].map(_winter_start_year)
    climate["winter_id"] = climate["winter_start_year"] - start_year
    climate = climate[["date", "winter_id", "t_out_c"]].sort_values("date")
    climate["winter_id"] = climate["winter_id"].astype(int)
    climate["t_out_c"] = climate["t_out_c"].astype(float)
    climate = climate.reset_index(drop=True)

    expected_days = _expected_winter_days(start_year, winters)
    actual_days = len(climate)
    if actual_days != expected_days:
        raise ValueError(
            f"climate data has gaps: expected {expected_days} days, got {actual_days}"
        )

    return climate


def load_or_fetch_climate(
    property_input: PropertyInput,
    cache_dir: Path,
    winters: int = 20,
) -> pd.DataFrame:
    """Load cached climate data or fetch and cache winter daily mean temperatures.

    Implements MODEL.md §2 — Climate input.

    Inputs:
    - property_input: property schema containing postcode for location lookup.
    - cache_dir: filesystem path where climate cache files are stored.
    - winters: number of October-March winter realisations to load or fetch, count.

    Outputs:
    - pandas.DataFrame with winter identifiers, dates, and daily mean temperatures in °C.
    """
    latitude, longitude = geocode_postcode(property_input.postcode)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = f"{latitude:.4f}_{longitude:.4f}_{winters}.parquet"
    cache_path = cache_dir / cache_key

    if cache_path.exists():
        cache_age_seconds = time() - os.path.getmtime(cache_path)
        if cache_age_seconds < CACHE_MAX_AGE_SECONDS:
            return pd.read_parquet(cache_path)

    climate = fetch_winter_daily_mean_temperatures(latitude, longitude, winters)
    tmp_path = cache_path.with_name(f"{cache_path.name}.tmp")
    climate.to_parquet(tmp_path, index=False)
    tmp_path.replace(cache_path)
    return climate
