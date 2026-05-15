"""Open-Meteo weather backfill for Clay ML v3 Phase A."""

from __future__ import annotations

import csv
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from .clay_v3_venues import VenueGeo


OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FIELDNAMES = [
    "venue_key",
    "match_date",
    "temp_mean_c",
    "humidity_pct",
    "humidity_source",
    "wind_max_kph",
    "precipitation_mm",
    "source",
]


@dataclass(frozen=True)
class WeatherCoverage:
    rows: list[dict[str, Any]]
    fixture_coverage_count: int
    fixture_total: int
    humidity_sources: dict[str, int]
    unresolved_fixture_keys: list[tuple[str, str]]

    @property
    def coverage(self) -> float:
        return self.fixture_coverage_count / self.fixture_total if self.fixture_total else 1.0


def _get_json_with_retry(session: requests.Session, params: dict[str, Any], max_attempts: int = 4) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = session.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=60)
            if response.status_code == 429:
                time.sleep(2.0 * attempt)
                continue
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # pragma: no cover - network failures are environment-specific.
            last_error = exc
            if attempt == max_attempts:
                break
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"Open-Meteo request failed: {last_error}")


def _mean(values: list[float]) -> float | None:
    good = [float(v) for v in values if v is not None]
    if not good:
        return None
    return sum(good) / len(good)


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.3f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return ""


def fetch_venue_weather(session: requests.Session, venue: VenueGeo, dates: list[str]) -> tuple[list[dict[str, Any]], str]:
    if not dates:
        return [], "none"
    start_date = min(dates)
    end_date = max(dates)
    params = {
        "latitude": venue.lat,
        "longitude": venue.lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": "temperature_2m_mean,wind_speed_10m_max,precipitation_sum",
        "hourly": "relative_humidity_2m",
        "timezone": "UTC",
        "wind_speed_unit": "kmh",
    }
    payload = _get_json_with_retry(session, params)
    daily = payload.get("daily") or {}
    hourly = payload.get("hourly") or {}

    humidity_by_date: dict[str, float | None] = {}
    hourly_times = hourly.get("time") or []
    hourly_humidity = hourly.get("relative_humidity_2m") or []
    buckets: dict[str, list[float]] = defaultdict(list)
    for ts, humidity in zip(hourly_times, hourly_humidity, strict=False):
        if humidity is None:
            continue
        day = str(ts)[:10]
        buckets[day].append(float(humidity))
    for day in dates:
        humidity_by_date[day] = _mean(buckets.get(day, []))

    daily_rows: dict[str, dict[str, Any]] = {}
    for idx, day in enumerate(daily.get("time") or []):
        daily_rows[str(day)] = {
            "temp_mean_c": (daily.get("temperature_2m_mean") or [None])[idx],
            "wind_max_kph": (daily.get("wind_speed_10m_max") or [None])[idx],
            "precipitation_mm": (daily.get("precipitation_sum") or [None])[idx],
        }

    rows: list[dict[str, Any]] = []
    for day in sorted(set(dates)):
        d = daily_rows.get(day, {})
        rows.append(
            {
                "venue_key": venue.venue_key,
                "match_date": day,
                "temp_mean_c": _fmt(d.get("temp_mean_c")),
                "humidity_pct": _fmt(humidity_by_date.get(day)),
                "humidity_source": "hourly_aggregated",
                "wind_max_kph": _fmt(d.get("wind_max_kph")),
                "precipitation_mm": _fmt(d.get("precipitation_mm")),
                "source": "open-meteo:daily+hourly-humidity",
            }
        )
    return rows, "hourly_aggregated"


def build_weather_cache(
    fixtures: list[dict[str, Any]],
    fixture_venue_keys: dict[int, str | None],
    venue_geo: dict[str, VenueGeo],
    out_path: Path,
) -> WeatherCoverage:
    dates_by_venue: dict[str, set[str]] = defaultdict(set)
    for idx, fixture in enumerate(fixtures):
        venue_key = fixture_venue_keys.get(idx)
        if venue_key and venue_key in venue_geo:
            dates_by_venue[venue_key].add(str(fixture["date"]))

    session = requests.Session()
    session.headers.update({"User-Agent": "il-margine-clay-v3-weather/1.0"})
    rows: list[dict[str, Any]] = []
    humidity_sources: dict[str, int] = defaultdict(int)
    for venue_key in sorted(dates_by_venue):
        venue_rows, source = fetch_venue_weather(session, venue_geo[venue_key], sorted(dates_by_venue[venue_key]))
        rows.extend(venue_rows)
        humidity_sources[source] += len(venue_rows)
        time.sleep(0.25)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    row_index = {(row["venue_key"], row["match_date"]): row for row in rows}
    coverage = 0
    missing: list[tuple[str, str]] = []
    for idx, fixture in enumerate(fixtures):
        venue_key = fixture_venue_keys.get(idx)
        date_iso = str(fixture["date"])
        row = row_index.get((venue_key or "", date_iso))
        if row and row["temp_mean_c"] and row["humidity_pct"] and row["wind_max_kph"] and row["precipitation_mm"] != "":
            coverage += 1
        else:
            missing.append((venue_key or "", date_iso))
    return WeatherCoverage(
        rows=rows,
        fixture_coverage_count=coverage,
        fixture_total=len(fixtures),
        humidity_sources=dict(humidity_sources),
        unresolved_fixture_keys=missing,
    )
