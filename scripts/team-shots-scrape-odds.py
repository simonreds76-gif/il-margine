#!/usr/bin/env python3
"""
Scrape team total shots over/under odds (bet365-style markets).

Source priority:
  1. Odds-API.io (ODDS_API_KEY / ODDS_API_IO_KEY)
  2. BetsAPI (BETS_API_KEY)

The Odds API (the-odds-api.com) does NOT list team total shots for soccer --
only player_shots / player_shots_on_target. Team shots live on bet365 feeds.

The scraper matches market names like "Team Total Shots", "Total Shots", etc.

Usage:
  python scripts/team-shots-scrape-odds.py
  python scripts/team-shots-scrape-odds.py --league epl --bookmakers Bet365
  python scripts/team-shots-scrape-odds.py --source betsapi --league serie-a
  python scripts/team-shots-scrape-odds.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests

from football_count_markets import (
    append_control_odds_rows,
    append_market_inventory,
    build_control_odds_rows,
    build_market_inventory_rows,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = ROOT / "data" / "team-shots" / "inbox"
RUN_STATUS_PATH = ROOT / "data" / "team-shots" / "team-shots-scrape-last-run.json"
DEFAULT_MATCH_ODDS_HISTORY = ROOT / "data" / "football-form" / "football-1x2-odds-history.csv"
DEFAULT_MATCH_SHOTS_HISTORY = ROOT / "data" / "team-shots" / "match-shots-odds-history.csv"
DEFAULT_BET365_CORNERS_HISTORY = ROOT / "data" / "corners-ou" / "bet365-corners-odds-history.csv"
BASE_URL_ODDS_API = "https://api.odds-api.io/v3"
BASE_URL_BETSAPI = "https://api.b365api.com"

LEAGUE_CONFIGS = {
    "epl": {
        "label": "Premier League",
        "slug": "england-premier-league",
        "name_variants": {"england - premier league", "premier league"},
        "competition": "Premier League",
        "betsapi_league_id": 148,
    },
    "serie-a": {
        "label": "Serie A",
        "slug": "italy-serie-a",
        "name_variants": {"italy - serie a", "serie a"},
        "competition": "Serie A",
        "betsapi_league_id": 207,
    },
    "la-liga": {
        "label": "La Liga",
        "slug": "spain-la-liga",
        "name_variants": {
            "spain - la liga", "la liga", "laliga",
            "spain - laliga", "spain - la liga ea sports",
        },
        "competition": "La Liga",
        "betsapi_league_id": 302,
    },
    "bundesliga": {
        "label": "Bundesliga",
        "slug": "germany-bundesliga",
        "name_variants": {"germany - bundesliga", "bundesliga"},
        "competition": "Bundesliga",
        "betsapi_league_id": 96,
    },
    "ligue-1": {
        "label": "Ligue 1",
        "slug": "france-ligue-1",
        "name_variants": {"france - ligue 1", "ligue 1"},
        "competition": "Ligue 1",
        "betsapi_league_id": 176,
    },
}

LIVE_LEAGUES = ["epl", "serie-a", "la-liga", "bundesliga", "ligue-1"]

# Account selection can be changed from the odds-api.io dashboard/API.
# Live account check on 2026-04-18 showed only Bet365 returning 200 for the
# team-shots football markets we query. The others force /odds/multi into a
# 403 fallback path without adding coverage.
DEFAULT_BOOKMAKERS = "Bet365"
BOOKMAKER_RETRY_FALLBACK = ["Bet365"]

OUTPUT_FIELDS = [
    "captured_at", "match_date", "event_id", "kickoff_at",
    "snapshot_kind", "bookmaker", "competition",
    "home_team", "away_team", "team", "market",
    "line", "side", "odds_decimal", "source", "notes",
]

RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2.0
_ODDS_API_HTTP_REQUEST_LIMIT = 0
_ODDS_API_HTTP_REQUEST_COUNT = 0


def configure_odds_api_http_budget(limit: int) -> None:
    """Set a process-wide hard ceiling, including retries and fallbacks."""
    global _ODDS_API_HTTP_REQUEST_LIMIT, _ODDS_API_HTTP_REQUEST_COUNT
    _ODDS_API_HTTP_REQUEST_LIMIT = max(int(limit), 0)
    _ODDS_API_HTTP_REQUEST_COUNT = 0


def odds_api_get(url: str, **kwargs: object) -> requests.Response:
    global _ODDS_API_HTTP_REQUEST_COUNT
    if (
        _ODDS_API_HTTP_REQUEST_LIMIT > 0
        and _ODDS_API_HTTP_REQUEST_COUNT >= _ODDS_API_HTTP_REQUEST_LIMIT
    ):
        raise RuntimeError(
            "Odds-API.io HTTP request budget exhausted "
            f"({_ODDS_API_HTTP_REQUEST_COUNT}/{_ODDS_API_HTTP_REQUEST_LIMIT})"
        )
    _ODDS_API_HTTP_REQUEST_COUNT += 1
    return requests.get(url, **kwargs)


def inclusive_days_to_iso(days_ahead: int) -> str:
    target_day = datetime.now(timezone.utc).date() + timedelta(days=max(days_ahead, 0))
    horizon = datetime.combine(target_day, datetime.max.time(), tzinfo=timezone.utc)
    return horizon.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_kickoff(value: object) -> Optional[datetime]:
    """Parse provider ISO timestamps or Unix seconds into UTC."""
    if value is None:
        return None
    if isinstance(value, (int, float)) or str(value).strip().isdigit():
        try:
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
        except (OverflowError, OSError, TypeError, ValueError):
            return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def within_kickoff_window(
    value: object,
    max_minutes: int,
    *,
    now: Optional[datetime] = None,
) -> bool:
    """Return true when kickoff is upcoming and inside the requested window."""
    if max_minutes <= 0:
        return True
    kickoff = parse_kickoff(value)
    if kickoff is None:
        return False
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    minutes = (kickoff - current.astimezone(timezone.utc)).total_seconds() / 60.0
    return 0.0 < minutes <= float(max_minutes)


def load_env() -> None:
    for name in (".env.local", "env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            raw_line = raw_line.strip()
            if raw_line and not raw_line.startswith("#") and "=" in raw_line:
                key, value = raw_line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip('"').strip("'")


def _norm(text: str) -> str:
    normalized = html.unescape((text or "").strip().lower())
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


def _is_team_shots_market(name: str) -> bool:
    text = (name or "").strip().lower()
    if "player" in text or "on target" in text or "shots on target" in text:
        return False
    return bool(
        re.search(r"\bshots?\b", text)
        and re.search(r"\b(team|home|away)\b", text)
    )


def _extract_line_and_side(prop: dict, market_name: str) -> List[dict]:
    """
    Returns a list of {line, side, odds_decimal} dicts (0, 1, or 2 entries).

    Handles two prop shapes from odds-api.io:
      A) {hdp: 12.5, over: "1.800", under: "1.909"}  — one object, both sides
      B) {label: "Over 12.5", odds: "1.800"}          — one object, one side
    """
    results = []

    # Shape A: hdp + over/under in same prop object
    hdp = prop.get("hdp")
    if hdp is not None:
        try:
            line = float(hdp)
        except (TypeError, ValueError):
            line = None
        if line is not None:
            for side, key in (("over", "over"), ("under", "under")):
                raw = prop.get(key)
                if raw is not None:
                    try:
                        odds_val = float(raw)
                        if odds_val > 1.0:
                            results.append({"line": line, "side": side, "odds_decimal": odds_val})
                    except (TypeError, ValueError):
                        pass
        if results:
            return results

    # Shape B: single selection with label + scalar odds field
    label = str(prop.get("label") or prop.get("name") or "").strip()
    odds_val = None
    for key in ("odds", "value", "price", "decimal", "back"):
        raw = prop.get(key)
        if raw is not None:
            try:
                odds_val = float(raw)
                if odds_val > 1.0:
                    break
            except (TypeError, ValueError):
                continue
    if odds_val is None or odds_val <= 1.0:
        return []

    line_match = re.search(r"(\d+\.?\d*)", label)
    if line_match:
        line = float(line_match.group(1))
    else:
        line_match = re.search(r"(\d+\.?\d*)", market_name)
        if line_match:
            line = float(line_match.group(1))
        else:
            return []

    lower = label.lower()
    if "over" in lower or "+" in lower:
        side = "over"
    elif "under" in lower or "-" in lower:
        side = "under"
    elif "yes" in lower:
        side = "over"
    elif "no" in lower:
        side = "under"
    else:
        return []

    return [{"line": line, "side": side, "odds_decimal": odds_val}]


def _extract_team_from_market(market_name: str, home_team: str, away_team: str) -> str:
    text = (market_name or "").strip()
    home_norm = _norm(home_team)
    away_norm = _norm(away_team)
    text_norm = _norm(text)

    if home_norm and home_norm in text_norm:
        return home_team
    if away_norm and away_norm in text_norm:
        return away_team

    lower = text.lower()
    if "home" in lower:
        return home_team
    if "away" in lower:
        return away_team

    return ""


def _looks_like_league(league: dict, config: dict) -> bool:
    name = _norm(str(league.get("name") or ""))
    slug = _norm(str(league.get("slug") or ""))
    target_slug = _norm(config["slug"])
    name_variants = {_norm(v) for v in config["name_variants"]}
    return slug == target_slug or name in name_variants


def _run_url_from_env() -> Optional[str]:
    server = os.environ.get("GITHUB_SERVER_URL")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if server and repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return None


def _write_run_status(payload: dict) -> None:
    RUN_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUN_STATUS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def scrape_odds_api(
    api_key: str,
    league_key: str,
    bookmakers_str: str,
    days_ahead: int = 3,
    kickoff_within_minutes: int = 0,
    market_inventory: Optional[List[dict]] = None,
    control_odds: Optional[List[dict]] = None,
    max_events: int = 0,
    max_odds_requests: int = 0,
) -> tuple[list[dict], int, list[str]]:
    config = LEAGUE_CONFIGS[league_key]
    now = datetime.now(timezone.utc)
    from_iso = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    to_iso = (now + timedelta(days=days_ahead)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    params = {
        "apiKey": api_key,
        "sport": "football",
        "status": "pending",
        "from": from_iso,
        "to": to_iso,
    }

    provider_errors: List[str] = []
    print(f"  [odds-api.io] Discovering events for {config['label']}...")
    try:
        resp = None
        for attempt in range(RETRY_ATTEMPTS):
            resp = odds_api_get(f"{BASE_URL_ODDS_API}/events", params=params, timeout=30)
            try:
                resp.raise_for_status()
                events = resp.json()
                break
            except requests.HTTPError as exc:
                status_code = getattr(exc.response, "status_code", None)
                if status_code is None or status_code // 100 != 5:
                    raise
                if attempt < RETRY_ATTEMPTS - 1:
                    time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                events = None
        if events is None:
            raise requests.HTTPError("odds-api.io /events failed after retries", response=resp)
    except requests.HTTPError as exc:
        status_code = getattr(exc.response, "status_code", None)
        if status_code is None or status_code // 100 != 5:
            raise

        provider_errors.append(f"odds-api.io /events 5xx ({status_code}) -> fallback without status filter")
        # odds-api.io intermittently 5xx when `status=pending` is supplied.
        # Retry the broader query and keep the existing date window / league
        # filtering client-side so the daily pipeline remains usable.
        fallback_params = {
            "apiKey": api_key,
            "sport": "football",
            "from": from_iso,
            "to": to_iso,
        }
        print("  [odds-api.io] /events with status=pending returned 5xx; retrying without status filter.")
        fallback_resp = odds_api_get(f"{BASE_URL_ODDS_API}/events", params=fallback_params, timeout=30)
        fallback_resp.raise_for_status()
        events = fallback_resp.json()

    if not isinstance(events, list):
        events = []

    matched = [e for e in events if _looks_like_league(e.get("league") or {}, config)]
    league_events = len(matched)
    if kickoff_within_minutes > 0:
        matched = [
            event
            for event in matched
            if within_kickoff_window(event.get("date"), kickoff_within_minutes, now=now)
        ]
        print(
            f"  [odds-api.io] {len(matched)}/{league_events} events within "
            f"{kickoff_within_minutes}m of kickoff"
        )
    else:
        print(f"  [odds-api.io] {len(matched)} events found")
    matched.sort(key=lambda event: str(event.get("date") or ""))
    if max_events > 0:
        matched = matched[:max_events]
    if not matched:
        return [], 0, provider_errors

    rows: List[dict] = []
    captured = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    event_ids = [str(e["id"]) for e in matched]
    payload, payload_errors = _fetch_odds_api_payload(
        api_key,
        event_ids,
        bookmakers_str,
        max_requests=max_odds_requests,
    )
    provider_errors.extend(payload_errors)
    rows = _extract_odds_api_rows(payload, config, captured)

    if not rows:
        requested = [book.strip() for book in bookmakers_str.split(",") if book.strip()]
        fallback_books = [book for book in BOOKMAKER_RETRY_FALLBACK if book not in requested]
        if fallback_books:
            retry_books = ",".join(requested + fallback_books)
            print(f"  [odds-api.io] No team shots found for {config['label']} with {bookmakers_str}; retrying {retry_books}.")
            retry_payload, retry_errors = _fetch_odds_api_payload(
                api_key,
                event_ids,
                retry_books,
                max_requests=max_odds_requests,
            )
            provider_errors.extend(retry_errors)
            rows = _extract_odds_api_rows(retry_payload, config, captured)
            if rows:
                payload = retry_payload

    if not rows:
        sample_markets: set[str] = set()
        for event in payload:
            for bookmaker, markets in (event.get("bookmakers") or {}).items():
                for market in markets or []:
                    name = str(market.get("name") or "")
                    if name:
                        sample_markets.add(f"{bookmaker}: {name}")
        if sample_markets:
            print("  [odds-api.io] Markets available (no team shots found):")
            for mn in sorted(sample_markets)[:30]:
                shots_flag = " <-- possible?" if "shot" in mn.lower() else ""
                print(f"    - {mn}{shots_flag}")

    if market_inventory is not None:
        market_inventory.extend(build_market_inventory_rows(payload, config["competition"], captured))
    if control_odds is not None:
        control_odds.extend(build_control_odds_rows(payload, config["competition"], captured))

    return rows, len(matched), provider_errors


def _fetch_odds_api_payload(
    api_key: str,
    event_ids: List[str],
    bookmakers_str: str,
    max_requests: int = 0,
) -> tuple[list[dict], list[str]]:
    payload: List[dict] = []
    errors: List[str] = []
    chunks = [event_ids[i : i + 10] for i in range(0, len(event_ids), 10)]
    if max_requests > 0:
        chunks = chunks[:max_requests]
    for chunk in chunks:
        chunk_payload, chunk_errors = _fetch_odds_api_multi_chunk(api_key, chunk, bookmakers_str)
        errors.extend(chunk_errors)
        if isinstance(chunk_payload, list):
            payload.extend(chunk_payload)
    return payload, errors


def _extract_odds_api_rows(payload: List[dict], config: dict, captured: str) -> List[dict]:
    rows: List[dict] = []
    for event in payload:
        home = str(event.get("home") or "")
        away = str(event.get("away") or "")
        event_id = str(event.get("id") or "")
        kickoff = str(event.get("date") or "")

        for bookmaker, markets in (event.get("bookmakers") or {}).items():
            for market in markets or []:
                market_name = str(market.get("name") or "")
                if not _is_team_shots_market(market_name):
                    continue

                team = _extract_team_from_market(market_name, home, away)
                if not team:
                    continue
                for prop in market.get("odds") or []:
                    for parsed in _extract_line_and_side(prop, market_name):
                        rows.append({
                        "captured_at": captured,
                        "match_date": kickoff[:10],
                        "event_id": event_id,
                        "kickoff_at": kickoff,
                        "snapshot_kind": "live_capture",
                        "bookmaker": bookmaker,
                        "competition": config["competition"],
                        "home_team": home,
                        "away_team": away,
                        "team": team,
                        "market": "TEAM_SHOTS",
                        "line": parsed["line"],
                        "side": parsed["side"],
                        "odds_decimal": f"{parsed['odds_decimal']:.4f}",
                        "source": "odds_api_io",
                        "notes": f"market={market_name}",
                    })
    return rows


def _merge_event_payloads(payloads: List[dict]) -> List[dict]:
    merged: Dict[str, dict] = {}
    for event in payloads:
        event_id = str(event.get("id") or "")
        if not event_id:
            continue
        current = merged.get(event_id)
        if current is None:
            merged[event_id] = {
                **event,
                "bookmakers": dict(event.get("bookmakers") or {}),
            }
            continue
        current_books = current.setdefault("bookmakers", {})
        for bookmaker, markets in (event.get("bookmakers") or {}).items():
            current_books[bookmaker] = markets
    return list(merged.values())


def _fetch_odds_api_multi_chunk(api_key: str, event_ids: List[str], bookmakers_str: str) -> tuple[list[dict], list[str]]:
    params = {"apiKey": api_key, "eventIds": ",".join(event_ids), "bookmakers": bookmakers_str}
    response = None
    for attempt in range(RETRY_ATTEMPTS):
        response = odds_api_get(f"{BASE_URL_ODDS_API}/odds/multi", params=params, timeout=30)
        if response.status_code < 500:
            break
        if attempt < RETRY_ATTEMPTS - 1:
            time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))

    if response is None:
        return [], [f"odds-api.io /odds/multi failed for {bookmakers_str}"]

    if response.ok:
        payload = response.json()
        return (payload if isinstance(payload, list) else []), []

    status_code = response.status_code
    bookmakers = [book.strip() for book in bookmakers_str.split(",") if book.strip()]
    if (status_code != 403 and status_code // 100 != 5) or len(bookmakers) <= 1:
        response.raise_for_status()

    print(f"  [odds-api.io] Multi-book request failed ({status_code}) for {bookmakers_str}; retrying per bookmaker.")
    errors = [f"odds-api.io /odds/multi {status_code} -> per-bookmaker fallback"]
    fallback_payloads: List[dict] = []
    for bookmaker in bookmakers:
        for attempt in range(RETRY_ATTEMPTS):
            try:
                single_resp = odds_api_get(
                    f"{BASE_URL_ODDS_API}/odds/multi",
                    params={"apiKey": api_key, "eventIds": ",".join(event_ids), "bookmakers": bookmaker},
                    timeout=30,
                )
                single_resp.raise_for_status()
                single_payload = single_resp.json()
                if isinstance(single_payload, list):
                    fallback_payloads.extend(single_payload)
                break
            except requests.HTTPError as exc:
                status = getattr(exc.response, "status_code", None)
                if status is None or status // 100 != 5:
                    print(f"  [odds-api.io] Skipping blocked bookmaker {bookmaker}: {exc}")
                    break
                if attempt < RETRY_ATTEMPTS - 1:
                    time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                else:
                    print(f"  [odds-api.io] Error fetching bookmaker {bookmaker}: {exc}")
            except requests.RequestException as exc:
                print(f"  [odds-api.io] Error fetching bookmaker {bookmaker}: {exc}")
                break

    if fallback_payloads:
        return _merge_event_payloads(fallback_payloads), errors
    print(f"  [odds-api.io] No accessible bookmaker payloads for requested chunk: {', '.join(bookmakers)}")
    return [], errors


def scrape_betsapi(
    api_key: str,
    league_key: str,
    days_ahead: int = 3,
    kickoff_within_minutes: int = 0,
) -> tuple[list[dict], int]:
    config = LEAGUE_CONFIGS[league_key]
    print(f"  [betsapi] Discovering bet365 events for {config['label']}...")

    resp = requests.get(
        f"{BASE_URL_BETSAPI}/v3/bet365/upcoming",
        params={"token": api_key, "sport_id": 1, "league_id": config.get("betsapi_league_id", "")},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    events = data.get("results") or []
    discovered = len(events)
    if kickoff_within_minutes > 0:
        events = [
            event
            for event in events
            if within_kickoff_window(event.get("time"), kickoff_within_minutes)
        ]
        print(
            f"  [betsapi] {len(events)}/{discovered} events within "
            f"{kickoff_within_minutes}m of kickoff"
        )
    else:
        print(f"  [betsapi] {len(events)} upcoming events")

    rows: List[dict] = []
    captured = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    for event in events:
        fi = str(event.get("id") or event.get("FI") or "")
        if not fi:
            continue
        home = str(event.get("home") or event.get("home_name") or "")
        away = str(event.get("away") or event.get("away_name") or "")
        kickoff_ts = event.get("time") or ""
        try:
            kickoff = datetime.fromtimestamp(int(kickoff_ts), tz=timezone.utc).isoformat()
        except (ValueError, TypeError, OSError):
            kickoff = str(kickoff_ts)

        try:
            pm_resp = requests.get(
                f"{BASE_URL_BETSAPI}/v4/bet365/prematch",
                params={"token": api_key, "FI": fi},
                timeout=30,
            )
            pm_resp.raise_for_status()
            pm_data = pm_resp.json()
        except requests.RequestException as exc:
            print(f"  [betsapi] Error fetching prematch for FI={fi}: {exc}")
            continue

        for market_group in pm_data.get("results") or []:
            market_name = str(market_group.get("name") or market_group.get("market_name") or "")
            if not _is_team_shots_market(market_name):
                continue

            team = _extract_team_from_market(market_name, home, away)
            if not team:
                continue
            for prop in market_group.get("odds") or market_group.get("selections") or []:
                parsed = _extract_line_and_side(prop, market_name)
                if not parsed:
                    continue
                rows.append({
                    "captured_at": captured,
                    "match_date": kickoff[:10],
                    "event_id": fi,
                    "kickoff_at": kickoff,
                    "snapshot_kind": "live_capture",
                    "bookmaker": "Bet365",
                    "competition": config["competition"],
                    "home_team": home,
                    "away_team": away,
                    "team": team,
                    "market": "TEAM_SHOTS",
                    "line": parsed["line"],
                    "side": parsed["side"],
                    "odds_decimal": f"{parsed['odds_decimal']:.4f}",
                    "source": "betsapi",
                    "notes": f"market={market_name};FI={fi}",
                })

    return rows, len(events)


def write_rows(rows: List[dict], out_dir: Path, league_key: str, dry_run: bool = False) -> Optional[str]:
    if dry_run or not rows:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"team-shots-{league_key}-{ts}.csv"
    path = out_dir / filename
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


def list_available_bookmakers(api_key: str) -> None:
    """Print all bookmakers available on this odds-api.io account."""
    resp = odds_api_get(
        f"{BASE_URL_ODDS_API}/bookmakers",
        params={"apiKey": api_key},
        timeout=30,
    )
    resp.raise_for_status()
    books = resp.json()
    if not isinstance(books, list):
        print("  Unexpected response:", books)
        return
    active = sorted(b["name"] for b in books if b.get("active") and b.get("name"))
    print(f"\n  {len(active)} active bookmakers on your account:")
    for name in active:
        print(f"    - {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape team total shots odds (bet365-style feeds)")
    parser.add_argument("--league", choices=sorted(LEAGUE_CONFIGS), default=None)
    parser.add_argument("--all-leagues", action="store_true", help="Scrape all supported live leagues")
    parser.add_argument("--source", choices=["auto", "odds-api", "betsapi"], default="auto")
    parser.add_argument("--bookmakers", default=DEFAULT_BOOKMAKERS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--market-audit-out",
        type=Path,
        default=None,
        help="Append the raw market inventory returned by the existing odds call (no extra API request).",
    )
    parser.add_argument("--match-odds-history", type=Path, default=DEFAULT_MATCH_ODDS_HISTORY)
    parser.add_argument("--match-shots-history", type=Path, default=DEFAULT_MATCH_SHOTS_HISTORY)
    parser.add_argument("--bet365-corners-history", type=Path, default=DEFAULT_BET365_CORNERS_HISTORY)
    parser.add_argument("--days-ahead", type=int, default=3)
    parser.add_argument(
        "--kickoff-within-minutes",
        type=int,
        default=0,
        help="Only request detailed odds for events starting within this many minutes (0 disables).",
    )
    parser.add_argument(
        "--max-events-per-league",
        type=int,
        default=0,
        help="Hard cap on events sent to detailed odds calls for each league; 0 disables.",
    )
    parser.add_argument(
        "--max-odds-requests-per-league",
        type=int,
        default=0,
        help="Hard cap on odds/multi calls for each league; 0 disables.",
    )
    parser.add_argument(
        "--max-odds-api-http-requests",
        type=int,
        default=0,
        help="Process-wide hard cap including discovery, retries, and fallbacks; 0 disables.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--discover-bookmakers", action="store_true",
                        help="List all bookmakers available on your account and exit")
    args = parser.parse_args()
    configure_odds_api_http_budget(args.max_odds_api_http_requests)

    leagues = LIVE_LEAGUES if args.all_leagues else [args.league or "epl"]

    load_env()
    odds_api_key = os.environ.get("ODDS_API_KEY") or os.environ.get("ODDS_API_IO_KEY")
    betsapi_key = os.environ.get("BETS_API_KEY")

    if args.discover_bookmakers:
        if not odds_api_key:
            raise SystemExit("ODDS_API_KEY not set in .env.local")
        list_available_bookmakers(odds_api_key)
        return

    print("\n" + "=" * 64)
    print("  IL MARGINE - Team Total Shots Odds Scraper")
    print("=" * 64)

    run_status = {
        "run_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "leagues": leagues,
        "events_found": 0,
        "rows_scraped": 0,
        "provider_errors": [],
        "sources_used": [],
        "run_url": _run_url_from_env(),
        "success": False,
        "odds_api_http_request_limit": _ODDS_API_HTTP_REQUEST_LIMIT,
    }

    total_written = 0
    market_inventory_rows: List[dict] = []
    control_odds_rows: List[dict] = []
    try:
        for league in leagues:
            config = LEAGUE_CONFIGS[league]
            print(f"\n  League: {config['label']}")

            rows: List[dict] = []

            if args.source in ("auto", "odds-api") and odds_api_key:
                print("  Source: Odds-API.io")
                rows, events_found, provider_errors = scrape_odds_api(
                    odds_api_key,
                    league,
                    args.bookmakers,
                    args.days_ahead,
                    args.kickoff_within_minutes,
                    market_inventory_rows,
                    control_odds_rows,
                    args.max_events_per_league,
                    args.max_odds_requests_per_league,
                )
                run_status["events_found"] += events_found
                run_status["provider_errors"].extend(provider_errors)
                run_status["sources_used"].append("odds-api")
                if rows:
                    print(f"  Team shots rows from odds-api.io: {len(rows)}")

            if not rows and args.source in ("auto", "betsapi") and betsapi_key:
                print("  Source: BetsAPI (bet365)")
                rows, events_found = scrape_betsapi(
                    betsapi_key,
                    league,
                    args.days_ahead,
                    args.kickoff_within_minutes,
                )
                run_status["events_found"] += events_found
                run_status["sources_used"].append("betsapi")
                if rows:
                    print(f"  Team shots rows from betsapi: {len(rows)}")

            run_status["rows_scraped"] += len(rows)

            if not rows:
                missing = []
                if not odds_api_key:
                    missing.append("ODDS_API_KEY")
                if not betsapi_key:
                    missing.append("BETS_API_KEY")
                if missing:
                    print(f"  No API key found. Set one of: {', '.join(missing)} in .env.local")
                else:
                    print("  No team shots markets in feed for this league.")
                continue

            if args.dry_run:
                print(f"  Dry run: {len(rows)} rows would be written")
                if rows:
                    s = rows[0]
                    print(f"  Sample: {s['home_team']} vs {s['away_team']} | "
                          f"{s['team']} {s['side']} {s['line']} @ {s['odds_decimal']}")
            else:
                path = write_rows(rows, args.out_dir, league)
                print(f"  Saved: {path}")
                total_written += len(rows)

        if not args.dry_run and args.all_leagues:
            print(f"\n  Total team shots rows written: {total_written}")
        if args.market_audit_out and not args.dry_run:
            added = append_market_inventory(args.market_audit_out, market_inventory_rows)
            print(
                f"  Market inventory: {added} new rows / {len(market_inventory_rows)} observed "
                f"-> {args.market_audit_out}"
            )
        if not args.dry_run:
            control_outputs = (
                ("MATCH_ODDS", args.match_odds_history),
                ("MATCH_SHOTS", args.match_shots_history),
                ("MATCH_CORNERS", args.bet365_corners_history),
                ("MATCH_CORNERS_ALT", args.bet365_corners_history),
            )
            added_by_path: dict[Path, int] = {}
            for market_name, output_path in control_outputs:
                selected = [row for row in control_odds_rows if row.get("market") == market_name]
                added_by_path[output_path] = added_by_path.get(output_path, 0) + append_control_odds_rows(
                    output_path,
                    selected,
                )
            for output_path, added in added_by_path.items():
                print(f"  Control odds: {added} new rows -> {output_path}")
            run_status["control_odds_rows_observed"] = len(control_odds_rows)
            run_status["control_odds_rows_added"] = sum(added_by_path.values())
        print("\n  Done.\n")
        run_status["success"] = True
    except Exception as exc:
        run_status["error"] = str(exc)
        raise
    finally:
        run_status["odds_api_http_requests"] = _ODDS_API_HTTP_REQUEST_COUNT
        _write_run_status(run_status)


if __name__ == "__main__":
    main()
