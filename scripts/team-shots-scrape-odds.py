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
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = ROOT / "data" / "team-shots" / "inbox"
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

LIVE_LEAGUES = ["epl", "serie-a", "la-liga", "bundesliga"]

# Account selection can be changed from the odds-api.io dashboard/API.
DEFAULT_BOOKMAKERS = "Bet365,Unibet,William Hill,Skybet"
BOOKMAKER_RETRY_FALLBACK = ["Bet365", "Unibet", "William Hill", "Skybet"]

OUTPUT_FIELDS = [
    "captured_at", "match_date", "event_id", "kickoff_at",
    "snapshot_kind", "bookmaker", "competition",
    "home_team", "away_team", "team", "market",
    "line", "side", "odds_decimal", "source", "notes",
]


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
    if "on target" in text or "shots on target" in text:
        return False
    if "shot" in text and ("total" in text or "over" in text or "under" in text or "team" in text):
        return True
    if re.search(r"\bshots?\b", text) and re.search(r"\b(o/?u|over|under|total)\b", text):
        return True
    if "team shots" in text:
        return True
    if "total shots" in text:
        return True
    return False


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


def scrape_odds_api(
    api_key: str,
    league_key: str,
    bookmakers_str: str,
    days_ahead: int = 3,
) -> List[dict]:
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

    print(f"  [odds-api.io] Discovering events for {config['label']}...")
    try:
        resp = requests.get(f"{BASE_URL_ODDS_API}/events", params=params, timeout=30)
        resp.raise_for_status()
        events = resp.json()
    except requests.HTTPError as exc:
        status_code = getattr(exc.response, "status_code", None)
        if status_code != 500:
            raise

        # odds-api.io intermittently 500s when `status=pending` is supplied.
        # Retry the broader query and keep the existing date window / league
        # filtering client-side so the daily pipeline remains usable.
        fallback_params = {
            "apiKey": api_key,
            "sport": "football",
            "from": from_iso,
            "to": to_iso,
        }
        print("  [odds-api.io] /events with status=pending returned 500; retrying without status filter.")
        fallback_resp = requests.get(f"{BASE_URL_ODDS_API}/events", params=fallback_params, timeout=30)
        fallback_resp.raise_for_status()
        events = fallback_resp.json()

    if not isinstance(events, list):
        events = []

    matched = [e for e in events if _looks_like_league(e.get("league") or {}, config)]
    print(f"  [odds-api.io] {len(matched)} events found")
    if not matched:
        return []

    rows: List[dict] = []
    captured = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    event_ids = [str(e["id"]) for e in matched]
    payload = _fetch_odds_api_payload(api_key, event_ids, bookmakers_str)
    rows = _extract_odds_api_rows(payload, config, captured)

    if not rows:
        requested = [book.strip() for book in bookmakers_str.split(",") if book.strip()]
        fallback_books = [book for book in BOOKMAKER_RETRY_FALLBACK if book not in requested]
        if fallback_books:
            retry_books = ",".join(requested + fallback_books)
            print(f"  [odds-api.io] No team shots found for {config['label']} with {bookmakers_str}; retrying {retry_books}.")
            retry_payload = _fetch_odds_api_payload(api_key, event_ids, retry_books)
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

    return rows


def _fetch_odds_api_payload(api_key: str, event_ids: List[str], bookmakers_str: str) -> List[dict]:
    payload: List[dict] = []
    for i in range(0, len(event_ids), 10):
        chunk = event_ids[i : i + 10]
        chunk_payload = _fetch_odds_api_multi_chunk(api_key, chunk, bookmakers_str)
        if isinstance(chunk_payload, list):
            payload.extend(chunk_payload)
    return payload


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


def _fetch_odds_api_multi_chunk(api_key: str, event_ids: List[str], bookmakers_str: str) -> List[dict]:
    params = {"apiKey": api_key, "eventIds": ",".join(event_ids), "bookmakers": bookmakers_str}
    response = requests.get(f"{BASE_URL_ODDS_API}/odds/multi", params=params, timeout=30)
    try:
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []
    except requests.HTTPError:
        bookmakers = [book.strip() for book in bookmakers_str.split(",") if book.strip()]
        if response.status_code != 403 or len(bookmakers) <= 1:
            raise

        print(f"  [odds-api.io] Multi-book request blocked for {bookmakers_str}; retrying per bookmaker.")
        fallback_payloads: List[dict] = []
        for bookmaker in bookmakers:
            try:
                single_resp = requests.get(
                    f"{BASE_URL_ODDS_API}/odds/multi",
                    params={"apiKey": api_key, "eventIds": ",".join(event_ids), "bookmakers": bookmaker},
                    timeout=30,
                )
                single_resp.raise_for_status()
                single_payload = single_resp.json()
                if isinstance(single_payload, list):
                    fallback_payloads.extend(single_payload)
            except requests.HTTPError as exc:
                print(f"  [odds-api.io] Skipping blocked bookmaker {bookmaker}: {exc}")
            except requests.RequestException as exc:
                print(f"  [odds-api.io] Error fetching bookmaker {bookmaker}: {exc}")

        if fallback_payloads:
            return _merge_event_payloads(fallback_payloads)
        print(f"  [odds-api.io] No accessible bookmaker payloads for requested chunk: {', '.join(bookmakers)}")
        return []


def scrape_betsapi(
    api_key: str,
    league_key: str,
    days_ahead: int = 3,
) -> List[dict]:
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

    return rows


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
    resp = requests.get(
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
    parser.add_argument("--days-ahead", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--discover-bookmakers", action="store_true",
                        help="List all bookmakers available on your account and exit")
    args = parser.parse_args()

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

    total_written = 0
    for league in leagues:
        config = LEAGUE_CONFIGS[league]
        print(f"\n  League: {config['label']}")

        rows: List[dict] = []

        if args.source in ("auto", "odds-api") and odds_api_key:
            print("  Source: Odds-API.io")
            rows = scrape_odds_api(odds_api_key, league, args.bookmakers, args.days_ahead)
            if rows:
                print(f"  Team shots rows from odds-api.io: {len(rows)}")

        if not rows and args.source in ("auto", "betsapi") and betsapi_key:
            print("  Source: BetsAPI (bet365)")
            rows = scrape_betsapi(betsapi_key, league, args.days_ahead)
            if rows:
                print(f"  Team shots rows from betsapi: {len(rows)}")

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
    print("\n  Done.\n")


if __name__ == "__main__":
    main()
