"""Populate the climate cache for every unique lat/lon in eval_cases.json.

Decouples Open-Meteo network calls from the evaluation run. Reads
data/heatpumpmonitor/eval_cases.json, deduplicates to unique
(latitude_4dp, longitude_4dp) pairs, and fetches winter daily mean
temperatures for each into data/heatpumpmonitor/climate_cache/.

Honours Open-Meteo rate limits: respects HTTP 429 Retry-After when
present, otherwise applies exponential backoff with a base delay
appropriate to ~1 call/sec sustained throughput. Skips locations that
are already cached.
"""

from __future__ import annotations

import argparse
import email.utils
import json
import os
import sys
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

import httpx

from app.forecast.climate import (
    CACHE_MAX_AGE_SECONDS,
    fetch_winter_daily_mean_temperatures,
)

DEFAULT_INPUT_PATH = Path("data/heatpumpmonitor/eval_cases.json")
DEFAULT_CACHE_DIR = Path("data/heatpumpmonitor/climate_cache")
HTTP_TOO_MANY_REQUESTS = 429
MAX_RETRY_AFTER_SECONDS = 300
MAX_BACKOFF_SECONDS = 60

SSL_VERIFY_FALSE = False


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Populate the HeatpumpMonitor Open-Meteo climate cache.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help=f"Path to eval_cases.json. Default: {DEFAULT_INPUT_PATH}",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help=f"Climate cache directory. Default: {DEFAULT_CACHE_DIR}",
    )
    parser.add_argument(
        "--winters",
        type=int,
        default=20,
        help="Number of complete winters to fetch. Default: 20.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Maximum fetch attempts per uncached location. Default: 5.",
    )
    parser.add_argument(
        "--base-delay-seconds",
        type=float,
        default=1.0,
        help="Base backoff and politeness delay in seconds. Default: 1.0.",
    )
    return parser.parse_args()


def _load_cases(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _unique_locations(cases: list[dict[str, Any]]) -> list[tuple[float, float]]:
    locations = {
        (round(float(case["latitude"]), 4), round(float(case["longitude"]), 4))
        for case in cases
    }
    return sorted(locations)


def _cache_path(cache_dir: Path, latitude: float, longitude: float, winters: int) -> Path:
    return cache_dir / f"{latitude:.4f}_{longitude:.4f}_{winters}.parquet"


def _cache_is_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    cache_age_seconds = time.time() - os.path.getmtime(path)
    return cache_age_seconds < CACHE_MAX_AGE_SECONDS


def _retry_after_seconds(response: httpx.Response) -> float | None:
    retry_after = response.headers.get("Retry-After")
    if retry_after is None:
        return None

    try:
        seconds = float(retry_after)
    except ValueError:
        try:
            retry_datetime = email.utils.parsedate_to_datetime(retry_after)
        except (TypeError, ValueError):
            return None
        if retry_datetime.tzinfo is None:
            retry_datetime = retry_datetime.replace(tzinfo=UTC)
        seconds = (retry_datetime - datetime.now(UTC)).total_seconds()

    if 0 <= seconds <= MAX_RETRY_AFTER_SECONDS:
        return seconds
    return None


def _backoff_seconds(attempt: int, base_delay_seconds: float) -> float:
    return min(base_delay_seconds * (2 ** (attempt - 1)), MAX_BACKOFF_SECONDS)


@contextmanager
def _patched_httpx_verify_false_if_needed() -> Iterator[None]:
    if not SSL_VERIFY_FALSE:
        yield
        return

    original_client = httpx.Client

    def client_with_verify_false(*args: Any, **kwargs: Any) -> httpx.Client:
        kwargs["verify"] = False
        return original_client(*args, **kwargs)

    httpx.Client = client_with_verify_false
    try:
        yield
    finally:
        httpx.Client = original_client


def _fetch_with_ssl_fallback(latitude: float, longitude: float, winters: int) -> Any:
    global SSL_VERIFY_FALSE
    with _patched_httpx_verify_false_if_needed():
        try:
            return fetch_winter_daily_mean_temperatures(latitude, longitude, winters)
        except httpx.ConnectError as exc:
            if "CERTIFICATE_VERIFY_FAILED" not in repr(exc):
                raise
            if not SSL_VERIFY_FALSE:
                print(
                    "WARNING: local SSL trust store rejected Open-Meteo; "
                    "retrying with httpx verify=False for this script run.",
                    file=sys.stderr,
                )
            SSL_VERIFY_FALSE = True

    with _patched_httpx_verify_false_if_needed():
        return fetch_winter_daily_mean_temperatures(latitude, longitude, winters)


def _fetch_and_cache_location(
    *,
    latitude: float,
    longitude: float,
    cache_path: Path,
    winters: int,
    max_retries: int,
    base_delay_seconds: float,
) -> bool:
    for attempt in range(1, max_retries + 1):
        try:
            climate = _fetch_with_ssl_fallback(latitude, longitude, winters)
            tmp_path = cache_path.with_name(f"{cache_path.name}.tmp")
            climate.to_parquet(tmp_path, index=False)
            tmp_path.replace(cache_path)
            return True
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == HTTP_TOO_MANY_REQUESTS:
                delay = _retry_after_seconds(exc.response)
                if delay is None:
                    delay = _backoff_seconds(attempt, base_delay_seconds)
                print(
                    f"HTTP 429 for {latitude:.4f},{longitude:.4f}; "
                    f"attempt {attempt}/{max_retries}; sleeping {delay:.1f}s.",
                    file=sys.stderr,
                )
                time.sleep(delay)
                continue
            if 500 <= status_code <= 599:
                delay = _backoff_seconds(attempt, base_delay_seconds)
                print(
                    f"HTTP {status_code} for {latitude:.4f},{longitude:.4f}; "
                    f"attempt {attempt}/{max_retries}; sleeping {delay:.1f}s.",
                    file=sys.stderr,
                )
                time.sleep(delay)
                continue
            print(
                f"Permanent HTTP failure for {latitude:.4f},{longitude:.4f}: {exc!r}",
                file=sys.stderr,
            )
            return False
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as exc:
            delay = _backoff_seconds(attempt, base_delay_seconds)
            print(
                f"Network failure for {latitude:.4f},{longitude:.4f}: {exc!r}; "
                f"attempt {attempt}/{max_retries}; sleeping {delay:.1f}s.",
                file=sys.stderr,
            )
            time.sleep(delay)

    print(
        f"Permanent failure after {max_retries} attempts for "
        f"{latitude:.4f},{longitude:.4f}.",
        file=sys.stderr,
    )
    return False


def _log_progress(
    index: int,
    total: int,
    latitude: float,
    longitude: float,
    cached_after_run: int,
    skipped_existing: int,
    failed_permanently: int,
) -> None:
    print(
        f"[{index}/{total}] fetched {latitude:.4f},{longitude:.4f} "
        f"({cached_after_run} cached, {skipped_existing} skipped, "
        f"{failed_permanently} failed)"
    )


def main() -> None:
    args = _parse_args()
    cases = _load_cases(args.input)
    locations = _unique_locations(cases)
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    cached_after_run = 0
    skipped_existing = 0
    failed_permanently = 0

    for index, (latitude, longitude) in enumerate(locations, start=1):
        cache_path = _cache_path(args.cache_dir, latitude, longitude, args.winters)
        if _cache_is_fresh(cache_path):
            skipped_existing += 1
            cached_after_run += 1
            if index % 25 == 0 or index == len(locations):
                _log_progress(
                    index,
                    len(locations),
                    latitude,
                    longitude,
                    cached_after_run,
                    skipped_existing,
                    failed_permanently,
                )
            continue

        fetched = _fetch_and_cache_location(
            latitude=latitude,
            longitude=longitude,
            cache_path=cache_path,
            winters=args.winters,
            max_retries=args.max_retries,
            base_delay_seconds=args.base_delay_seconds,
        )
        if fetched:
            cached_after_run += 1
            time.sleep(args.base_delay_seconds)
        else:
            failed_permanently += 1

        if index % 25 == 0 or index == len(locations):
            _log_progress(
                index,
                len(locations),
                latitude,
                longitude,
                cached_after_run,
                skipped_existing,
                failed_permanently,
            )

    print(
        "Summary: "
        f"total_unique_locations={len(locations)}, "
        f"cached_after_run={cached_after_run}, "
        f"skipped_existing={skipped_existing}, "
        f"failed_permanently={failed_permanently}"
    )


if __name__ == "__main__":
    main()
