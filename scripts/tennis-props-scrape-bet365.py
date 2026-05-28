#!/usr/bin/env python3
"""Scrape Bet365 tennis aces/double-fault lines from odds-api.io.

This is intentionally narrow and credit-conscious:
  - tennis only
  - Bet365 by default
  - optional --max-events cap
  - outputs the same inbox format consumed by tennis-props-compare-bet365.py

The odds-api.io tennis market naming is not guaranteed, so the parser accepts
several common shapes and writes a market-audit CSV when requested.
"""

from __future__ import annotations

import argparse
import csv
import html
import os
import re
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "https://api.odds-api.io/v3"
OUT_DIR = ROOT / "data" / "tennis-props" / "inbox"
DEFAULT_BOOKMAKERS = "Bet365"
SLAM_KEYWORDS = (
    "roland garros",
    "french open",
    "wimbledon",
    "australian open",
    "us open",
    "u.s. open",
)
ZERO_ROW_PROBE_PARAMS: tuple[tuple[str, dict[str, str]], ...] = (
    ("baseline", {}),
    ("markets=Player Props", {"markets": "Player Props"}),
    ("markets=player_props", {"markets": "player_props"}),
    ("market=player_props", {"market": "player_props"}),
    ("markets=Player Aces", {"markets": "Player Aces"}),
    ("markets=Aces", {"markets": "Aces"}),
    ("markets=Player Double Faults", {"markets": "Player Double Faults"}),
    ("markets=Double Faults", {"markets": "Double Faults"}),
    ("include=all", {"include": "all"}),
    ("include=all;markets=player_props", {"include": "all", "markets": "player_props"}),
    ("hide_main_liner=false;markets=player_props", {"hide_main_liner": "false", "markets": "player_props"}),
    ("source=bet365", {"source": "bet365"}),
)
OUTPUT_FIELDS = [
    "date",
    "tour",
    "tournament",
    "player",
    "opponent",
    "market",
    "line",
    "over_odds",
    "under_odds",
]
AUDIT_FIELDS = [
    "captured_at",
    "event_id",
    "kickoff_at",
    "bookmaker",
    "league",
    "home",
    "away",
    "market_name",
    "odds_count",
    "sample_labels",
]


def load_env() -> None:
    for name in (".env.local", "env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip('"').strip("'")


def norm(value: object) -> str:
    text = html.unescape(str(value or "")).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def clean_player(value: object) -> str:
    text = html.unescape(str(value or "")).strip()
    if "," in text:
        last, first = text.split(",", 1)
        if last.strip() and first.strip():
            text = f"{first.strip()} {last.strip()}"
    text = re.sub(r"\s*\(\d+\)\s*", " ", text)
    text = re.sub(r"\b(over|under|aces?|double faults?|dfs?|df)\b", " ", text, flags=re.I)
    text = re.sub(r"\d+\.?\d*", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -:|")


def parse_decimal(value: object) -> float | None:
    if value is None:
        return None
    try:
        val = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return val if val > 1.0 else None


def parse_line(*values: object) -> float | None:
    for value in values:
        text = str(value or "")
        m = re.search(r"(\d+\.5|\d+)", text)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                continue
    return None


def identify_market(name: str) -> str | None:
    text = norm(name)
    if "double fault" in text or re.search(r"\bdfs?\b", text):
        return "double_faults"
    if "ace" in text and "race" not in text:
        return "aces"
    return None


def opponent_for(player: str, home: str, away: str) -> str:
    p = norm(player)
    home_norm = norm(home)
    away_norm = norm(away)
    if p and (p == home_norm or p in home_norm or home_norm in p):
        return away
    if p and (p == away_norm or p in away_norm or away_norm in p):
        return home
    return away if home else ""


def tour_from_event(event: dict[str, Any]) -> str:
    league = norm((event.get("league") or {}).get("name") or event.get("league") or "")
    haystack = " ".join(
        [
            league,
            norm(event.get("home")),
            norm(event.get("away")),
            norm(event.get("name")),
        ]
    )
    if "wta" in haystack or "women" in haystack:
        return "WTA"
    return "ATP"


def tournament_from_event(event: dict[str, Any]) -> str:
    league = str((event.get("league") or {}).get("name") or event.get("league") or "").strip()
    haystack = f"{league} {event.get('name') or ''}".lower()
    if "roland" in haystack or "french open" in haystack:
        return "Roland Garros"
    if "wimbledon" in haystack:
        return "Wimbledon"
    if "australian open" in haystack:
        return "Australian Open"
    if "us open" in haystack or "u.s. open" in haystack:
        return "US Open"
    return league or "Tennis"


def event_text(event: dict[str, Any]) -> str:
    league = str((event.get("league") or {}).get("name") or event.get("league") or "")
    return " ".join(
        [
            league,
            str(event.get("name") or ""),
            str(event.get("home") or ""),
            str(event.get("away") or ""),
        ]
    ).lower()


def is_slam_event(event: dict[str, Any]) -> bool:
    text = event_text(event)
    return any(keyword in text for keyword in SLAM_KEYWORDS)


def is_singles_event(event: dict[str, Any]) -> bool:
    home = str(event.get("home") or event.get("home_team") or "")
    away = str(event.get("away") or event.get("away_team") or "")
    return "/" not in home and "/" not in away


def extract_rows(event: dict[str, Any], bookmaker: str, market: dict[str, Any]) -> list[dict[str, str]]:
    market_name = str(market.get("name") or "")
    market_key = identify_market(market_name)
    if not market_key:
        return []

    kickoff = str(event.get("date") or "")
    event_date = kickoff[:10]
    home = str(event.get("home") or event.get("home_team") or "")
    away = str(event.get("away") or event.get("away_team") or "")
    tour = tour_from_event(event)
    tournament = tournament_from_event(event)
    grouped: dict[tuple[str, str, float], dict[str, float]] = defaultdict(dict)

    for prop in market.get("odds") or market.get("outcomes") or []:
        label = str(prop.get("label") or prop.get("name") or "").strip()
        line = parse_line(prop.get("hdp"), prop.get("point"), label, market_name)
        if line is None:
            continue

        # Shape A: one prop carries both over and under.
        over_price = parse_decimal(prop.get("over"))
        under_price = parse_decimal(prop.get("under"))
        player_name = clean_player(prop.get("player") or prop.get("participant") or label or market_name)
        if over_price or under_price:
            if not player_name:
                player_name = clean_player(market_name)
            key = (player_name, opponent_for(player_name, home, away), line)
            if over_price:
                grouped[key]["over_odds"] = over_price
            if under_price:
                grouped[key]["under_odds"] = under_price
            continue

        # Shape B: one prop per side.
        price = None
        for price_key in ("odds", "value", "price", "decimal", "back"):
            price = parse_decimal(prop.get(price_key))
            if price is not None:
                break
        if price is None:
            continue

        lower = norm(label)
        if "over" in lower:
            side = "over_odds"
        elif "under" in lower:
            side = "under_odds"
        else:
            continue
        player_name = clean_player(prop.get("player") or prop.get("participant") or label or market_name)
        if not player_name:
            player_name = clean_player(market_name)
        key = (player_name, opponent_for(player_name, home, away), line)
        grouped[key][side] = price

    rows: list[dict[str, str]] = []
    for (player, opponent, line), prices in grouped.items():
        if not prices.get("over_odds") and not prices.get("under_odds"):
            continue
        rows.append(
            {
                "date": event_date,
                "tour": tour,
                "tournament": tournament,
                "player": player,
                "opponent": clean_player(opponent),
                "market": market_key,
                "line": f"{line:.1f}",
                "over_odds": f"{prices['over_odds']:.4f}" if prices.get("over_odds") else "",
                "under_odds": f"{prices['under_odds']:.4f}" if prices.get("under_odds") else "",
            }
        )
    return rows


def fetch_json(path: str, params: dict[str, Any]) -> Any:
    response = requests.get(f"{BASE_URL}/{path.lstrip('/')}", params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_multi(api_key: str, event_ids: list[str], bookmakers: str) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for i in range(0, len(event_ids), 10):
        chunk = event_ids[i : i + 10]
        data = fetch_json(
            "odds/multi",
            {"apiKey": api_key, "eventIds": ",".join(chunk), "bookmakers": bookmakers},
        )
        if isinstance(data, list):
            payload.extend(data)
        time.sleep(0.35)
    return payload


def summarize_market_names(data: Any) -> str:
    if isinstance(data, dict):
        events = [data]
    elif isinstance(data, list):
        events = data
    else:
        return f"unexpected:{type(data).__name__}"

    counts: dict[str, int] = defaultdict(int)
    for event in events:
        for markets in (event.get("bookmakers") or {}).values():
            for market in markets or []:
                counts[str(market.get("name") or "<blank>")] += 1
    if not counts:
        return "none"
    return ", ".join(f"{name}:{count}" for name, count in sorted(counts.items()))


def probe_request(path: str, params: dict[str, Any]) -> tuple[int | str, str]:
    try:
        response = requests.get(f"{BASE_URL}/{path.lstrip('/')}", params=params, timeout=30)
    except requests.RequestException as exc:
        return "request_error", repr(exc)
    try:
        data: Any = response.json()
    except ValueError:
        data = response.text[:220]
    if response.status_code >= 400:
        if isinstance(data, dict):
            message = data.get("message") or data.get("error") or str(data)[:220]
        else:
            message = str(data)[:220]
        return response.status_code, message
    return response.status_code, summarize_market_names(data)


def run_zero_row_market_probe(api_key: str, events: list[dict[str, Any]], bookmakers: str) -> None:
    if not events:
        return
    event = events[0]
    event_id = str(event.get("id") or "")
    if not event_id:
        return
    league = str((event.get("league") or {}).get("name") or event.get("league") or "")
    print("odds-api.io zero-row market probe:")
    print(f"  event={event_id} | {league} | {event.get('home')} vs {event.get('away')}")

    bookmaker_variants = []
    for value in [bookmakers.split(",")[0].strip(), "Bet365", "bet365"]:
        if value and value not in bookmaker_variants:
            bookmaker_variants.append(value)

    for bookmaker in bookmaker_variants:
        labels = ZERO_ROW_PROBE_PARAMS if bookmaker == bookmaker_variants[0] else ZERO_ROW_PROBE_PARAMS[:3]
        print(f"  bookmaker_probe={bookmaker}")
        for label, extra in labels:
            params = {"apiKey": api_key, "eventId": event_id, "bookmakers": bookmaker}
            params.update(extra)
            status, summary = probe_request("odds", params)
            print(f"    /odds {label}: status={status}; markets={summary}")
            time.sleep(0.2)

    status, summary = probe_request(
        "odds/multi",
        {"apiKey": api_key, "eventIds": event_id, "bookmakers": bookmakers, "markets": "player_props"},
    )
    print(f"    /odds/multi markets=player_props: status={status}; markets={summary}")

    status, summary = probe_request(
        "value-bets",
        {"apiKey": api_key, "bookmaker": bookmakers.split(",")[0].strip(), "sport": "tennis", "includeEventDetails": "true", "limit": "20"},
    )
    print(f"    /value-bets tennis Bet365 sample: status={status}; markets={summary}")


def write_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Bet365 tennis aces/DF lines from odds-api.io")
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--days-ahead", type=int, default=2)
    parser.add_argument("--bookmakers", default=DEFAULT_BOOKMAKERS)
    parser.add_argument("--max-events", type=int, default=64)
    parser.add_argument("--out", default="")
    parser.add_argument("--audit-out", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_env()
    api_key = os.environ.get("ODDS_API_KEY") or os.environ.get("ODDS_API_IO_KEY")
    if not api_key:
        raise SystemExit("Set ODDS_API_KEY or ODDS_API_IO_KEY in .env.local to use odds-api.io.")

    now = datetime.now(timezone.utc)
    from_iso = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    to_iso = (now + timedelta(days=args.days_ahead)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    events = fetch_json(
        "events",
        {"apiKey": api_key, "sport": "tennis", "status": "pending", "from": from_iso, "to": to_iso},
    )
    if not isinstance(events, list):
        events = []

    raw_event_count = len(events)
    events = [event for event in events if is_slam_event(event) and is_singles_event(event)]
    events = events[: max(0, args.max_events)] if args.max_events else events
    print(f"odds-api.io tennis events returned: {raw_event_count}; Slam singles selected: {len(events)}")
    if not events:
        return

    payload = fetch_multi(api_key, [str(event.get("id")) for event in events if event.get("id")], args.bookmakers)
    rows: list[dict[str, str]] = []
    audit_rows: list[dict[str, str]] = []
    captured_at = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    for event in payload:
        for bookmaker, markets in (event.get("bookmakers") or {}).items():
            for market in markets or []:
                market_name = str(market.get("name") or "")
                odds_list = market.get("odds") or market.get("outcomes") or []
                labels = [
                    str(prop.get("label") or prop.get("name") or prop.get("player") or "") for prop in odds_list[:6]
                ]
                audit_rows.append(
                    {
                        "captured_at": captured_at,
                        "event_id": str(event.get("id") or ""),
                        "kickoff_at": str(event.get("date") or ""),
                        "bookmaker": bookmaker,
                        "league": str((event.get("league") or {}).get("name") or event.get("league") or ""),
                        "home": str(event.get("home") or ""),
                        "away": str(event.get("away") or ""),
                        "market_name": market_name,
                        "odds_count": str(len(odds_list)),
                        "sample_labels": " | ".join(labels),
                    }
                )
                rows.extend(extract_rows(event, bookmaker, market))

    out = Path(args.out) if args.out else OUT_DIR / f"bet365-lines-{args.date}.csv"
    audit_out = Path(args.audit_out) if args.audit_out else OUT_DIR / f"bet365-tennis-market-audit-{args.date}.csv"
    print(f"parsed aces/DF rows: {len(rows)}")
    if not rows:
        run_zero_row_market_probe(api_key, events, args.bookmakers)
    if args.dry_run:
        for row in rows[:20]:
            print(row)
        print(f"dry-run only; would write {out}")
        return
    write_rows(audit_out, audit_rows, AUDIT_FIELDS)
    if rows:
        write_rows(out, rows, OUTPUT_FIELDS)
        print(f"Saved lines: {out}")
    else:
        print("No aces/DF rows parsed; skipped writing lines file.")
    print(f"Saved audit: {audit_out}")


if __name__ == "__main__":
    main()
