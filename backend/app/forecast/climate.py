from pathlib import Path

import pandas as pd

from app.models import PropertyInput


def geocode_postcode(postcode: str) -> tuple[float, float]:
    """Look up a UK postcode and return latitude and longitude.

    Implements MODEL.md §2 — Climate input.

    Inputs:
    - postcode: UK postcode string, used only for lookup and not persisted.

    Outputs:
    - tuple of latitude and longitude in decimal degrees.
    """
    raise NotImplementedError(f"climate.geocode_postcode — see MODEL.md §2")


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
    raise NotImplementedError(
        f"climate.fetch_winter_daily_mean_temperatures — see MODEL.md §2"
    )


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
    raise NotImplementedError(f"climate.load_or_fetch_climate — see MODEL.md §2")
