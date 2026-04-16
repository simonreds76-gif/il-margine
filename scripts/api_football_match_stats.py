#!/usr/bin/env python3
"""
Targeted API-Football fallback for finished match statistics.

Used only when Football-Data and FotMob did not provide a result row for a
specific pending fixture. This keeps request volume low enough for a capped
free-tier fallback.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
import os
from typing import Dict, Iterable, List, Optional

import requests

from settlement_utils import build_fixture_key, normalize_team_name

BASE_URL = "https://v3.football.api-sports.io"
DEFAULT_MAX_REQUESTS = 10

LEAGUE_CONFIGS = {
    "epl": {"league_id": 39, "label": "Premier League"},
    "serie-a": {"league_id": 135, "label": "Serie A"},
    "la-liga": {"league_id": 140, "label": "La Liga"},
    "bundesliga": {"league_id": 78, "label": "Bundesliga"},
    "ligue-1": {"league_id": 61, "label": "Ligue 1"},
}


def _headers() -> dict:
    key = (os.getenv("API_FOOTBALL_KEY") or "").strip()
    if not key:
        return {}
    return {
        "x-apisports-key": key,
        "Accept": "application/json",
        "User-Agent": "il-margine/settlement-fallback",
    }


def _season_for_day(day: date) -> int:
    return day.year if day.month >= 8 else day.year - 1


def _safe_int(value: object) -> Optional[int]:
    if value is None:
        return None
    try:
        text = str(value).strip()
        if not text:
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _extract_stat_int(stat_rows: Iterable[dict], names: Iterable[str]) -> Optional[int]:
    wanted = {name.casefold() for name in names}
    for row in stat_rows:
        stat_type = str(row.get("type") or "").strip().casefold()
        if stat_type not in wanted:
            continue
        return _safe_int(row.get("value"))
    return None


def _request(path: str, params: dict) -> dict:
    response = requests.get(
        f"{BASE_URL}/{path.lstrip('/')}",
        params=params,
        headers=_headers(),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def fetch_api_football_results(
    league_key: str,
    fixtures: List[dict],
    *,
    max_requests: int = DEFAULT_MAX_REQUESTS,
) -> tuple[Dict[str, dict], dict]:
    """
    Fetch stats rows for a small set of unresolved fixtures.

    fixtures entries must include: date, home_team, away_team
    """
    config = LEAGUE_CONFIGS.get(league_key)
    api_key = (os.getenv("API_FOOTBALL_KEY") or "").strip()
    if not config:
        return {}, {"error": "unknown league", "requests_used": 0}
    if not api_key:
        return {}, {"error": "missing API_FOOTBALL_KEY", "requests_used": 0}
    if max_requests <= 0 or not fixtures:
        return {}, {"error": None, "requests_used": 0}

    requests_used = 0
    results: Dict[str, dict] = {}
    matched_latest: Optional[str] = None
    unresolved_by_date: dict[str, List[dict]] = defaultdict(list)
    for fixture in fixtures:
        fixture_date = str(fixture.get("date") or "").strip()[:10]
        if fixture_date:
            unresolved_by_date[fixture_date].append(fixture)

    for fixture_date in sorted(unresolved_by_date):
        if requests_used >= max_requests:
            break
        try:
            day = date.fromisoformat(fixture_date)
        except ValueError:
            continue

        season = _season_for_day(day)
        try:
            payload = _request(
                "fixtures",
                {
                    "league": config["league_id"],
                    "season": season,
                    "date": fixture_date,
                    "status": "FT-AET-PEN",
                },
            )
        except Exception as exc:
            return results, {
                "error": f"fixtures request failed for {league_key} {fixture_date}: {exc}",
                "requests_used": requests_used,
                "api_football_latest": matched_latest,
            }
        requests_used += 1

        response_rows = payload.get("response") or []
        fixtures_by_match = {}
        for row in response_rows:
            teams = row.get("teams") or {}
            home_name = normalize_team_name(str((teams.get("home") or {}).get("name") or ""))
            away_name = normalize_team_name(str((teams.get("away") or {}).get("name") or ""))
            if not home_name or not away_name:
                continue
            fixtures_by_match[(home_name, away_name)] = row

        for target in unresolved_by_date[fixture_date]:
            if requests_used >= max_requests:
                break
            home_norm = normalize_team_name(str(target.get("home_team") or ""))
            away_norm = normalize_team_name(str(target.get("away_team") or ""))
            fixture_row = fixtures_by_match.get((home_norm, away_norm))
            if not fixture_row:
                continue

            fixture_id = _safe_int((fixture_row.get("fixture") or {}).get("id"))
            if not fixture_id:
                continue

            try:
                stats_payload = _request("fixtures/statistics", {"fixture": fixture_id})
            except Exception as exc:
                return results, {
                    "error": f"statistics request failed for fixture {fixture_id}: {exc}",
                    "requests_used": requests_used,
                    "api_football_latest": matched_latest,
                }
            requests_used += 1

            stats_response = stats_payload.get("response") or []
            if len(stats_response) < 2:
                continue

            home_stats = stats_response[0]
            away_stats = stats_response[1]
            home_values = home_stats.get("statistics") or []
            away_values = away_stats.get("statistics") or []

            home_shots = _extract_stat_int(home_values, ("Total Shots",))
            away_shots = _extract_stat_int(away_values, ("Total Shots",))
            home_sot = _extract_stat_int(home_values, ("Shots on Goal", "Shots on Target"))
            away_sot = _extract_stat_int(away_values, ("Shots on Goal", "Shots on Target"))
            home_corners = _extract_stat_int(home_values, ("Corner Kicks",))
            away_corners = _extract_stat_int(away_values, ("Corner Kicks",))

            if home_shots is None and away_shots is None and home_corners is None and away_corners is None:
                continue

            key = build_fixture_key(fixture_date, target["home_team"], target["away_team"])
            results[key] = {
                "home_team": home_norm,
                "away_team": away_norm,
                "home_shots": home_shots or 0,
                "away_shots": away_shots or 0,
                "home_sot": home_sot or 0,
                "away_sot": away_sot or 0,
                "home_corners": home_corners or 0,
                "away_corners": away_corners or 0,
                "total_corners": (home_corners or 0) + (away_corners or 0),
                "source": "api-football",
                "fixture_id": fixture_id,
            }
            matched_latest = fixture_date

    return results, {
        "error": None,
        "requests_used": requests_used,
        "api_football_latest": matched_latest,
        "api_football_count": len(results),
        "max_requests": max_requests,
    }
