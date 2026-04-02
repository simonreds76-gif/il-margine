#!/usr/bin/env python3
"""
Scrape league-specific anytime-goalscorer prices from odds-api.io.

This is the preferred live source when an Odds-API.io key is configured,
because it can return soft-book prices like Bet365 and Ladbrokes.
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
from typing import Dict, Iterable, List, Optional

import requests


BASE_URL = "https://api.odds-api.io/v3"
DEFAULT_OUT_DIR = "data/goalscorer/inbox"
DEFAULT_BOOKMAKERS = "Bet365,Ladbrokes"

LEAGUE_CONFIGS = {
    "serie-a": {
        "label": "Serie A",
        "slug": "italy-serie-a",
        "name_variants": {"italy - serie a", "serie a"},
        "competition": "Serie A",
    },
    "epl": {
        "label": "Premier League",
        "slug": "england-premier-league",
        "name_variants": {"england - premier league", "premier league"},
        "competition": "Premier League",
    },
    "la-liga": {
        "label": "La Liga",
        "slug": "spain-la-liga",
        "slug_variants": {"spain-laliga", "spain-la-liga-ea-sports", "spain-primera-division"},
        "name_variants": {
            "spain - la liga",
            "la liga",
            "laliga",
            "laliga ea sports",
            "spain - laliga",
            "spain - la liga ea sports",
            "spain - primera division",
            "primera division",
        },
        "competition": "La Liga",
    },
    "bundesliga": {
        "label": "Bundesliga",
        "slug": "germany-bundesliga",
        "name_variants": {"germany - bundesliga", "bundesliga"},
        "competition": "Bundesliga",
    },
    "ligue-1": {
        "label": "Ligue 1",
        "slug": "france-ligue-1",
        "name_variants": {"france - ligue 1", "ligue 1", "ligue 1 mcdonalds"},
        "competition": "Ligue 1",
    },
}


def _norm_league_text(value: str) -> str:
    normalized = html.unescape((value or "").strip().lower())
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    cleaned = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", cleaned).strip()


def load_env() -> None:
    root = Path(__file__).resolve().parent.parent
    for name in (".env.local", "env.local"):
        path = root / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip('"').strip("'")


def _parse_decimal(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_decimal(*values) -> Optional[float]:
    for value in values:
        decimal = _parse_decimal(value)
        if decimal is not None and decimal > 1.0:
            return decimal
    return None


def _looks_like_league(league: dict, config: dict) -> bool:
    name = _norm_league_text(str(league.get("name") or ""))
    slug = _norm_league_text(str(league.get("slug") or ""))
    slug_variants = {_norm_league_text(config["slug"])} | {
        _norm_league_text(value) for value in config.get("slug_variants", set())
    }
    name_variants = {_norm_league_text(value) for value in config["name_variants"]}
    return slug in slug_variants or name in name_variants


def _debug_candidate_leagues(events: list, league_key: str) -> list[str]:
    hints = {
        "la-liga": ("spain", "liga", "laliga", "primera"),
        "serie-a": ("italy", "serie"),
        "epl": ("england", "premier"),
        "bundesliga": ("germany", "bundesliga"),
        "ligue-1": ("france", "ligue"),
    }
    wanted = hints.get(league_key, tuple())
    seen: list[str] = []
    for event in events or []:
        league = event.get("league") or {}
        name = str(league.get("name") or "").strip()
        slug = str(league.get("slug") or "").strip()
        haystack = _norm_league_text(f"{name} {slug}")
        if wanted and not any(token in haystack for token in wanted):
            continue
        label = f"name={name or '-'} | slug={slug or '-'}"
        if label not in seen:
            seen.append(label)
    return seen[:10]


def _market_is_atgs(name: str) -> bool:
    text = (name or "").strip().lower()
    if "anytime" in text and "goal" in text:
        return True
    if re.search(r"\bto score\b", text) and "first" not in text and "last" not in text:
        return True
    return False


def _extract_player_from_market_name(name: str) -> str:
    text = (name or "").strip()
    text = re.sub(r"\bAnytime Goalscorer\b", "", text, flags=re.I).strip(" -:")
    text = re.sub(r"\bTo Score\b", "", text, flags=re.I).strip(" -:")
    return text


def _extract_atgs_rows_for_market(bookmaker: str, event: dict, market: dict, competition_label: str) -> List[dict]:
    rows: List[dict] = []
    market_name = str(market.get("name") or "")
    odds_list = market.get("odds") or []
    kickoff_at = str(event.get("date") or "")
    captured_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if not _market_is_atgs(market_name):
        return rows

    # Shape A: market name = "Anytime Goalscorer", props are selections by player.
    if "anytime" in market_name.lower():
        for prop in odds_list:
            player_name = str(prop.get("label") or prop.get("name") or "").strip()
            odds_decimal = _first_decimal(
                prop.get("odds"),
                prop.get("value"),
                prop.get("price"),
                prop.get("decimal"),
                prop.get("back"),
                prop.get("over"),
                prop.get("yes"),
            )
            if not player_name or odds_decimal is None:
                continue
            rows.append(
                {
                    "captured_at": captured_at,
                    "match_date": str(event.get("date") or "")[:10],
                    "event_id": str(event.get("id") or ""),
                    "kickoff_at": kickoff_at,
                    "minutes_to_kickoff": "",
                    "snapshot_kind": "live_capture",
                    "bookmaker": bookmaker,
                    "competition": str((event.get("league") or {}).get("name") or competition_label),
                    "market": "ATGS",
                    "home_team": str(event.get("home") or ""),
                    "away_team": str(event.get("away") or ""),
                    "player_name": player_name,
                    "player_team": "",
                    "odds_decimal": f"{odds_decimal:.4f}",
                    "source": "odds_api_io",
                    "notes": f"event_id={event.get('id')};market={market_name}",
                }
            )
        return rows

    # Shape B: market name = "<Player> To Score", odds array contains Yes/No.
    player_name = _extract_player_from_market_name(market_name)
    yes_row = next(
        (
            prop
            for prop in odds_list
            if str(prop.get("label") or prop.get("name") or "").strip().lower() in {"yes", "to score", "over"}
        ),
        None,
    )
    if yes_row is None and len(odds_list) == 1:
        yes_row = odds_list[0]
    odds_decimal = _first_decimal(
        (yes_row or {}).get("odds"),
        (yes_row or {}).get("value"),
        (yes_row or {}).get("price"),
        (yes_row or {}).get("decimal"),
        (yes_row or {}).get("back"),
    )
    if player_name and odds_decimal is not None:
        rows.append(
            {
                "captured_at": captured_at,
                "match_date": str(event.get("date") or "")[:10],
                "event_id": str(event.get("id") or ""),
                "kickoff_at": kickoff_at,
                "minutes_to_kickoff": "",
                "snapshot_kind": "live_capture",
                "bookmaker": bookmaker,
                "competition": str((event.get("league") or {}).get("name") or competition_label),
                "market": "ATGS",
                "home_team": str(event.get("home") or ""),
                "away_team": str(event.get("away") or ""),
                "player_name": player_name,
                "player_team": "",
                "odds_decimal": f"{odds_decimal:.4f}",
                "source": "odds_api_io",
                "notes": f"event_id={event.get('id')};market={market_name}",
            }
        )
    return rows


def write_rows(
    rows: List[dict],
    out_dir: str,
    out_file: str = "",
    dry_run: bool = False,
    file_tag: str = "atgs",
) -> Optional[str]:
    fieldnames = [
        "captured_at",
        "match_date",
        "event_id",
        "kickoff_at",
        "minutes_to_kickoff",
        "snapshot_kind",
        "bookmaker",
        "competition",
        "market",
        "home_team",
        "away_team",
        "player_name",
        "player_team",
        "odds_decimal",
        "source",
        "notes",
    ]
    if dry_run:
        return None
    os.makedirs(out_dir, exist_ok=True)
    target = out_file or os.path.join(
        out_dir,
        f"odds-api-{file_tag}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv",
    )
    with open(target, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return target


def fetch_json(path: str, params: dict) -> dict | list:
    response = requests.get(f"{BASE_URL}/{path.lstrip('/')}", params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def chunked(values: List[str], size: int) -> Iterable[List[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def parse_bookmakers(raw: str) -> List[str]:
    seen = set()
    bookmakers: List[str] = []
    for value in (raw or "").split(","):
        bookmaker = value.strip()
        if not bookmaker:
            continue
        key = bookmaker.lower()
        if key in seen:
            continue
        seen.add(key)
        bookmakers.append(bookmaker)
    return bookmakers


def discover_league_events(
    api_key: str,
    league_key: str,
    league_config: dict,
    bookmakers: List[str],
    now: datetime,
    days_ahead: int,
) -> List[dict]:
    base_params = {
        "apiKey": api_key,
        "sport": "football",
        "status": "pending",
        "from": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "to": (now + timedelta(days=days_ahead)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    discovered: Dict[str, dict] = {}

    for bookmaker in bookmakers:
        params = {**base_params, "bookmaker": bookmaker}
        events = fetch_json("events", params)
        if not isinstance(events, list):
            continue
        for event in events:
            if not _looks_like_league(event.get("league") or {}, league_config):
                continue
            event_id = str(event.get("id") or "")
            if event_id:
                discovered[event_id] = event

    if discovered:
        return list(discovered.values())

    events = fetch_json("events", base_params)
    if not isinstance(events, list):
        return []
    matched = [event for event in events if _looks_like_league(event.get("league") or {}, league_config)]
    if not matched:
        candidates = _debug_candidate_leagues(events, league_key)
        if candidates:
            print("  Nearby league labels from source feed:")
            for label in candidates:
                print(f"    {label}")
    return matched


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape league ATGS prices from odds-api.io")
    parser.add_argument("--league", choices=sorted(LEAGUE_CONFIGS), default="serie-a")
    parser.add_argument("--bookmakers", default=DEFAULT_BOOKMAKERS)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-file", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--days-ahead", type=int, default=3)
    args = parser.parse_args()

    load_env()
    api_key = os.environ.get("ODDS_API_KEY") or os.environ.get("ODDS_API_IO_KEY")
    if not api_key:
        raise SystemExit("Set ODDS_API_KEY or ODDS_API_IO_KEY in .env.local to use odds-api.io.")
    league_config = LEAGUE_CONFIGS[args.league]

    print("\n" + "=" * 64)
    print("  IL MARGINE - Odds-API Goalscorer Scraper")
    print("=" * 64)
    print(f"  League: {league_config['label']}")

    now = datetime.now(timezone.utc)
    bookmakers = parse_bookmakers(args.bookmakers)
    if not bookmakers:
        raise SystemExit("Provide at least one bookmaker name via --bookmakers.")
    print(f"  Event discovery books: {', '.join(bookmakers)}")

    target_events = discover_league_events(api_key, args.league, league_config, bookmakers, now, args.days_ahead)
    print(f"  {league_config['label']} events found: {len(target_events):,}")
    if not target_events:
        print(f"  No {league_config['label']} events returned from the current source feed.")
        return

    all_rows: List[dict] = []
    bookmaker_list = ",".join(bookmakers)
    for event_ids in chunked([str(event["id"]) for event in target_events], 10):
        odds_payload = fetch_json(
            "odds/multi",
            {"apiKey": api_key, "eventIds": ",".join(event_ids), "bookmakers": bookmaker_list},
        )
        if not isinstance(odds_payload, list):
            continue
        for event in odds_payload:
            bookmakers = event.get("bookmakers") or {}
            for bookmaker, markets in bookmakers.items():
                for market in markets or []:
                    all_rows.extend(
                        _extract_atgs_rows_for_market(
                            bookmaker,
                            event,
                            market,
                            league_config["competition"],
                        )
                    )

    print(f"  ATGS rows scraped: {len(all_rows):,}")
    if all_rows:
        sample = all_rows[0]
        print(
            "  Sample: "
            f"{sample['home_team']} vs {sample['away_team']} | "
            f"{sample['player_name']} @ {sample['odds_decimal']} ({sample['bookmaker']})"
        )

    if args.dry_run:
        print("  Dry run only; no file written.")
        print("\n  Done.\n")
        return

    output = write_rows(
        all_rows,
        args.out_dir,
        out_file=args.out_file,
        dry_run=False,
        file_tag=f"{args.league}-atgs",
    )
    print(f"  Saved: {output}")
    print("\n  Done.\n")


if __name__ == "__main__":
    main()
