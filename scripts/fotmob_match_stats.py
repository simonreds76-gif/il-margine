#!/usr/bin/env python3
"""
Fetch recent finished football match stats from FotMob.

This is a settlement fallback for football props when Football-Data season CSVs
lag behind current fixtures. It extracts full-time team shots, shots on target,
corners, and fouls from FotMob's post-match page payload.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Dict, Iterable, Optional

import requests
from settlement_utils import normalize_team_name

MATCHES_URL = "https://www.fotmob.com/api/data/matches"
MATCH_URL = "https://www.fotmob.com/api/data/match"
WEB_BASE = "https://www.fotmob.com"
NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>')
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.fotmob.com/",
}

LEAGUE_CONFIGS = {
    "serie-a": {"league_id": 55, "label": "Serie A"},
    "epl": {"league_id": 47, "label": "Premier League"},
    "la-liga": {"league_id": 87, "label": "La Liga"},
    "bundesliga": {"league_id": 54, "label": "Bundesliga"},
    "ligue-1": {"league_id": 53, "label": "Ligue 1"},
}

def _safe_int(value: object) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        text = str(value).strip()
        if not text:
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _fetch_json(url: str, params: dict) -> dict:
    response = requests.get(url, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


def _fetch_text(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def _extract_next_payload(html_text: str) -> dict:
    match = NEXT_DATA_RE.search(html_text)
    if not match:
        raise ValueError("Could not find __NEXT_DATA__ payload on FotMob page")
    return json.loads(match.group(1))


def _fetch_page_props(match_id: int) -> dict:
    match_payload = _fetch_json(MATCH_URL, {"id": match_id})
    page_url = str(match_payload.get("pageUrl") or "").strip()
    if not page_url:
        raise ValueError(f"Missing pageUrl for match {match_id}")
    next_payload = _extract_next_payload(_fetch_text(f"{WEB_BASE}{page_url}"))
    return next_payload.get("props", {}).get("pageProps", {}) or {}


def _extract_stat_pair(stats_payload: dict, key: str) -> Optional[tuple[int, int]]:
    periods = (stats_payload or {}).get("Periods") or {}
    all_period = periods.get("All") or {}
    sections = all_period.get("stats") or []
    for section in sections:
        for item in section.get("stats", []) or []:
            if item.get("key") != key:
                continue
            values = item.get("stats") or []
            if len(values) != 2:
                continue
            left = _safe_int(values[0])
            right = _safe_int(values[1])
            if left is None or right is None:
                continue
            return left, right
    return None


def _fixture_targeted(match: dict, iso_date: str, target_fixtures: Optional[Iterable[dict]]) -> bool:
    if target_fixtures is None:
        return True
    home = normalize_team_name(str((match.get("home") or {}).get("longName") or (match.get("home") or {}).get("name") or ""))
    away = normalize_team_name(str((match.get("away") or {}).get("longName") or (match.get("away") or {}).get("name") or ""))
    return any(
        str(target.get("date") or "")[:10] == iso_date
        and normalize_team_name(str(target.get("home_team") or "")) == home
        and normalize_team_name(str(target.get("away_team") or "")) == away
        for target in target_fixtures
    )


def fetch_fotmob_recent_results(
    league_key: str,
    target_dates: Iterable[str],
    target_fixtures: Optional[Iterable[dict]] = None,
) -> Dict[str, dict]:
    """
    Return {date|home|away -> shots/corners result dict} for finished matches
    on the requested dates.
    """
    config = LEAGUE_CONFIGS.get(league_key)
    if not config:
        return {}

    results: Dict[str, dict] = {}
    for iso_date in sorted({(d or "").strip()[:10] for d in target_dates if (d or "").strip()}):
        try:
            fotmob_date = datetime.strptime(iso_date, "%Y-%m-%d").strftime("%Y%m%d")
        except ValueError:
            continue

        try:
            matches_payload = _fetch_json(
                MATCHES_URL,
                {"date": fotmob_date, "timezone": "Europe/London", "ccode3": "GBR"},
            )
        except Exception as exc:
            print(f"  [WARN] FotMob matches {league_key} {iso_date}: {exc}")
            continue

        league = next(
            (entry for entry in (matches_payload.get("leagues") or []) if entry.get("id") == config["league_id"]),
            None,
        )
        if not league:
            continue

        for match in league.get("matches", []) or []:
            status = match.get("status", {}) or {}
            if not status.get("finished"):
                continue
            # A date can contain dozens of matches. Fetching detail pages for
            # every match made targeted settlement unbounded; only request the
            # fixtures present in the permanent pending ledgers.
            if not _fixture_targeted(match, iso_date, target_fixtures):
                continue
            match_id = _safe_int(match.get("id"))
            if not match_id:
                continue

            try:
                page_props = _fetch_page_props(match_id)
            except Exception as exc:
                print(f"  [WARN] FotMob match {match_id}: {exc}")
                continue

            general = page_props.get("general", {}) or {}
            content = page_props.get("content", {}) or {}
            stats_payload = content.get("stats") or {}

            shots = _extract_stat_pair(stats_payload, "total_shots")
            shots_on_target = _extract_stat_pair(stats_payload, "ShotsOnTarget")
            corners = _extract_stat_pair(stats_payload, "corners")
            fouls = _extract_stat_pair(stats_payload, "fouls")
            if shots is None and shots_on_target is None and corners is None and fouls is None:
                continue

            home_team = str(
                general.get("homeTeam", {}).get("name")
                or match.get("home", {}).get("longName")
                or match.get("home", {}).get("name")
                or ""
            ).strip()
            away_team = str(
                general.get("awayTeam", {}).get("name")
                or match.get("away", {}).get("longName")
                or match.get("away", {}).get("name")
                or ""
            ).strip()
            match_date = str(general.get("matchTimeUTCDate") or status.get("utcTime") or "").strip()[:10]
            if not home_team or not away_team or not match_date:
                continue

            key = f"{match_date}|{normalize_team_name(home_team)}|{normalize_team_name(away_team)}"
            results[key] = {
                "home_shots": shots[0] if shots else None,
                "away_shots": shots[1] if shots else None,
                "home_sot": shots_on_target[0] if shots_on_target else None,
                "away_sot": shots_on_target[1] if shots_on_target else None,
                "home_corners": corners[0] if corners else None,
                "away_corners": corners[1] if corners else None,
                "total_corners": (corners[0] + corners[1]) if corners else None,
                "home_fouls": fouls[0] if fouls else None,
                "away_fouls": fouls[1] if fouls else None,
                "total_fouls": (fouls[0] + fouls[1]) if fouls else None,
                "source": "fotmob",
                "match_id": match_id,
            }

    return results
