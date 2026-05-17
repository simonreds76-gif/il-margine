#!/usr/bin/env python3
"""Scrape league-specific anytime-assist prices from odds-api.io.

Research/shadow only. This mirrors the goalscorer Odds-API scraper but targets
player assist markets and writes into data/assist-value by default.
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
from typing import Iterable, List, Optional

import requests


BASE_URL = "https://api.odds-api.io/v3"
DEFAULT_OUT_DIR = "data/assist-value/inbox"
DEFAULT_BOOKMAKERS = "Bet365"

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


def _market_is_assist(name: str) -> bool:
    text = (name or "").strip().lower()
    if "assist" not in text:
        return False
    blocked = ("team assists", "most assists", "top assist", "player assists outright", "season assists")
    return not any(token in text for token in blocked)


def _market_is_generic_assist(name: str, odds_list: list) -> bool:
    text = (name or "").strip().lower()
    if not _market_is_assist(text):
        return False
    if "score or assist" in text:
        return True
    if "anytime" in text or "player assists" in text or "to record an assist" in text:
        return True
    if len(odds_list) >= 3:
        labels = {str(prop.get("label") or prop.get("name") or "").strip().lower() for prop in odds_list[:5]}
        yes_no = {"yes", "no", "over", "under", "to assist"}
        return not labels.issubset(yes_no)
    return False


def _extract_player_from_market_name(name: str) -> str:
    text = (name or "").strip()
    patterns = [
        r"\bAnytime Assists?\b",
        r"\bPlayer Assists?\b",
        r"\bTo Record An Assist\b",
        r"\bTo Record Assist\b",
        r"\bTo Make An Assist\b",
        r"\bTo Have An Assist\b",
        r"\bTo Assist\b",
        r"\b1\+ Assists?\b",
        r"\bAssist\b",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.I)
    return text.strip(" -:|")


def _clean_assist_selection_label(label: str, market_name: str) -> str:
    """Return the player name only when the selection is explicitly assist-side.

    Bet365 exposes a mixed "Player To Score or Assist" market where the odds
    array contains both "(Score)" and "(Assist)" selections. Treating the whole
    market as assist would poison the shadow lane, so mixed markets must carry
    an explicit "(Assist)" tag per selection.
    """
    text = (label or "").strip()
    if not text:
        return ""

    market_text = (market_name or "").lower()
    mixed_score_assist = "score or assist" in market_text
    if mixed_score_assist and not re.search(r"\(\s*assist\s*\)", text, flags=re.I):
        return ""
    if re.search(r"\(\s*score\s*\)", text, flags=re.I):
        return ""

    text = re.sub(r"\s*\(\s*assist\s*\)\s*", " ", text, flags=re.I)
    text = re.sub(r"\s*\(\s*[12]\s*\)\s*$", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -:|")


def _extract_assist_rows_for_market(bookmaker: str, event: dict, market: dict, competition_label: str) -> List[dict]:
    rows: List[dict] = []
    market_name = str(market.get("name") or "")
    odds_list = market.get("odds") or []
    kickoff_at = str(event.get("date") or "")
    captured_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if not _market_is_assist(market_name):
        return rows

    # Shape A: market name is generic, props are selections by player.
    if _market_is_generic_assist(market_name, odds_list):
        for prop in odds_list:
            raw_label = str(prop.get("label") or prop.get("name") or "").strip()
            player_name = _clean_assist_selection_label(raw_label, market_name)
            if player_name.lower() in {"yes", "no", "over", "under"}:
                continue
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
                    "market": "ANYTIME_ASSIST",
                    "home_team": str(event.get("home") or ""),
                    "away_team": str(event.get("away") or ""),
                    "player_name": player_name,
                    "player_team": "",
                    "odds_decimal": f"{odds_decimal:.4f}",
                    "source": "odds_api_io",
                    "notes": f"event_id={event.get('id')};market={market_name};selection={raw_label}",
                }
            )
        return rows

    # Shape B: market name is player-specific, odds array contains Yes/No.
    player_name = _extract_player_from_market_name(market_name)
    yes_row = next(
        (
            prop
            for prop in odds_list
            if str(prop.get("label") or prop.get("name") or "").strip().lower() in {"yes", "to assist", "over"}
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
                "market": "ANYTIME_ASSIST",
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


def _audit_market_rows(bookmaker: str, event: dict, market: dict) -> list[dict]:
    odds_list = market.get("odds") or []
    sample_labels = [
        str(prop.get("label") or prop.get("name") or "").strip()
        for prop in odds_list[:8]
        if str(prop.get("label") or prop.get("name") or "").strip()
    ]
    return [
        {
            "event_id": str(event.get("id") or ""),
            "kickoff_at": str(event.get("date") or ""),
            "bookmaker": bookmaker,
            "league": str((event.get("league") or {}).get("name") or ""),
            "home_team": str(event.get("home") or ""),
            "away_team": str(event.get("away") or ""),
            "market_name": str(market.get("name") or ""),
            "is_assist_candidate": "true" if _market_is_assist(str(market.get("name") or "")) else "false",
            "odds_count": len(odds_list),
            "sample_labels": " | ".join(sample_labels),
        }
    ]


def write_rows(rows: List[dict], out_dir: str, out_file: str = "", dry_run: bool = False, file_tag: str = "assist") -> Optional[str]:
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


def write_market_audit(rows: List[dict], target: str) -> None:
    if not target:
        return
    fieldnames = [
        "event_id",
        "kickoff_at",
        "bookmaker",
        "league",
        "home_team",
        "away_team",
        "market_name",
        "is_assist_candidate",
        "odds_count",
        "sample_labels",
    ]
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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
    discovered: dict[str, dict] = {}

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
    parser = argparse.ArgumentParser(description="Scrape league anytime-assist prices from odds-api.io")
    parser.add_argument("--league", choices=sorted(LEAGUE_CONFIGS), default="epl")
    parser.add_argument("--bookmakers", default=DEFAULT_BOOKMAKERS)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-file", default="")
    parser.add_argument("--market-audit-out", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--days-ahead", type=int, default=3)
    args = parser.parse_args()

    load_env()
    api_key = os.environ.get("ODDS_API_KEY") or os.environ.get("ODDS_API_IO_KEY")
    if not api_key:
        raise SystemExit("Set ODDS_API_KEY or ODDS_API_IO_KEY in .env.local to use odds-api.io.")
    league_config = LEAGUE_CONFIGS[args.league]

    print("\n" + "=" * 64)
    print("  IL MARGINE - Odds-API Assist Scraper")
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
    market_audit_rows: List[dict] = []
    bookmaker_list = ",".join(bookmakers)
    for event_ids in chunked([str(event["id"]) for event in target_events], 10):
        payloads: List[dict] = []
        try:
            odds_payload = fetch_json(
                "odds/multi",
                {"apiKey": api_key, "eventIds": ",".join(event_ids), "bookmakers": bookmaker_list},
            )
            if isinstance(odds_payload, list):
                payloads.extend(odds_payload)
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code == 403:
                print(f"  odds/multi returned 403 for {bookmaker_list}; continuing without fresh odds for this chunk.")
                continue
            raise

        for event in payloads:
            event_bookmakers = event.get("bookmakers") or {}
            for bookmaker, markets in event_bookmakers.items():
                for market in markets or []:
                    market_audit_rows.extend(_audit_market_rows(bookmaker, event, market))
                    all_rows.extend(
                        _extract_assist_rows_for_market(
                            bookmaker,
                            event,
                            market,
                            league_config["competition"],
                        )
                    )

    if args.market_audit_out:
        write_market_audit(market_audit_rows, args.market_audit_out)
        print(f"  Market audit rows written: {len(market_audit_rows):,} -> {args.market_audit_out}")

    print(f"  Assist rows scraped: {len(all_rows):,}")
    if all_rows:
        sample = all_rows[0]
        print(
            "  Sample: "
            f"{sample['home_team']} vs {sample['away_team']} | "
            f"{sample['player_name']} @ {sample['odds_decimal']} ({sample['bookmaker']})"
        )

    if args.dry_run:
        print("  Dry run only; no assist odds file written.")
        print("\n  Done.\n")
        return

    if not all_rows:
        print("  No fresh assist rows returned; nothing written.")
        print("\n  Done.\n")
        return

    output = write_rows(
        all_rows,
        args.out_dir,
        out_file=args.out_file,
        dry_run=False,
        file_tag=f"{args.league}-assist",
    )
    print(f"  Saved: {output}")
    print("\n  Done.\n")


if __name__ == "__main__":
    main()
