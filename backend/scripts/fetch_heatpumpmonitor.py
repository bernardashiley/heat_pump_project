from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import httpx

SYSTEMS_URL = "https://heatpumpmonitor.org/system/list/public.json"
STATS_ALL_URL = "https://heatpumpmonitor.org/system/stats/all"
TIMEOUT_SECONDS = 60
OUTPUT_DIR = Path("data/heatpumpmonitor")


def _parse_json(url: str, response: httpx.Response) -> object:
    try:
        return response.json()
    except json.JSONDecodeError as exc:
        snippet = response.text[:200]
        raise ValueError(
            f"failed to parse JSON from {url}; first 200 chars: {snippet!r}"
        ) from exc


def _fetch_json(client: httpx.Client, url: str) -> object:
    response = client.get(url)
    if response.status_code != 200:
        raise RuntimeError(f"fetch failed for {url}: HTTP {response.status_code}")
    return _parse_json(url, response)


def _fetch_json_with_ssl_fallback(url: str) -> object:
    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
            return _fetch_json(client, url)
    except httpx.ConnectError as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise

        # Development-only fallback documented in NEXT.md. Do not copy this
        # pattern into production request paths; fix the local trust store.
        print(
            f"Warning: SSL certificate verification failed for {url}; "
            "retrying with verify=False for this diagnostic fetch."
        )
        with httpx.Client(timeout=TIMEOUT_SECONDS, verify=False) as client:
            return _fetch_json(client, url)


def _record_count(payload: object) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list):
                return len(value)
        return len(payload)
    return 0


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today_utc = datetime.now(UTC).strftime("%Y%m%d")

    systems = _fetch_json_with_ssl_fallback(SYSTEMS_URL)
    stats = _fetch_json_with_ssl_fallback(STATS_ALL_URL)

    systems_path = OUTPUT_DIR / f"systems_{today_utc}.json"
    stats_path = OUTPUT_DIR / f"stats_all_{today_utc}.json"
    _write_json(systems_path, systems)
    _write_json(stats_path, stats)

    shutil.copyfile(systems_path, OUTPUT_DIR / "systems_latest.json")
    shutil.copyfile(stats_path, OUTPUT_DIR / "stats_all_latest.json")

    print(
        f"Fetched {_record_count(systems)} systems and {_record_count(stats)} "
        f"stats records. Saved to {OUTPUT_DIR.as_posix()}/."
    )


if __name__ == "__main__":
    main()
