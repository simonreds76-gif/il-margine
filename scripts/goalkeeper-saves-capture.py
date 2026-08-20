#!/usr/bin/env python3
"""Capture real Bet365 goalkeeper-save lines with a hard two-request budget."""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from football_count_markets import classify_market, normalize_market_name
from goalkeeper_saves_live import ROOT, league_key, parse_float


BASE_URL = "https://api.odds-api.io/v3"
DEFAULT_HISTORY = ROOT / "data" / "goalkeeper-saves" / "gk-saves-odds-history.csv"
DEFAULT_STATUS = ROOT / "data" / "goalkeeper-saves" / "gk-saves-capture-status.json"
FIELDS = [
    "captured_at", "match_date", "event_id", "kickoff_at", "capture_mode",
    "bookmaker", "competition", "league", "home_team", "away_team", "player",
    "line", "side", "odds_decimal", "under_odds_decimal", "home_price",
    "draw_price", "away_price", "source",
]


def load_env() -> None:
    for path in (ROOT / ".env.local", ROOT / "env.local"):
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def request_json(path: str, params: dict[str, Any]) -> Any:
    response = requests.get(f"{BASE_URL}{path}", params=params, timeout=45)
    response.raise_for_status()
    return response.json()


def event_league(event: dict[str, Any]) -> str:
    value = event.get("league") or ""
    if isinstance(value, dict):
        return str(value.get("name") or value.get("slug") or "").strip()
    return str(value).strip()


def supported_events(
    events: list[dict[str, Any]],
    *,
    max_events: int,
    kickoff_within_minutes: int,
    now: datetime,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for event in events:
        if not event.get("id") or not league_key(event_league(event)):
            continue
        kickoff_text = str(event.get("date") or event.get("startTime") or "")
        try:
            kickoff = datetime.fromisoformat(kickoff_text.replace("Z", "+00:00"))
        except ValueError:
            continue
        if kickoff_within_minutes > 0:
            delta = (kickoff - now).total_seconds() / 60.0
            if delta < -15 or delta > kickoff_within_minutes:
                continue
        candidates.append(event)
    candidates.sort(key=lambda item: str(item.get("date") or item.get("startTime") or ""))
    return candidates[: max(1, max_events)]


def decimal_price(prop: dict[str, Any]) -> float | None:
    for key in ("odds", "value", "price", "decimal"):
        value = parse_float(prop.get(key))
        if value and value > 1.0:
            return value
    return None


def three_way_prices(event: dict[str, Any], bookmaker_name: str) -> tuple[float | None, float | None, float | None]:
    home = str(event.get("home") or "").casefold()
    away = str(event.get("away") or "").casefold()
    for bookmaker, markets in (event.get("bookmakers") or {}).items():
        if str(bookmaker).casefold() != bookmaker_name.casefold():
            continue
        for market in markets or []:
            name = normalize_market_name(market.get("name"))
            if not any(token in name for token in ("fulltime result", "full time result", "match result", "1x2", "moneyline")):
                continue
            prices: dict[str, float] = {}
            for prop in market.get("odds") or []:
                label = str(prop.get("label") or prop.get("name") or "").strip().casefold()
                price = decimal_price(prop)
                if not price:
                    continue
                if label in {"1", "home", home} or (home and home in label):
                    prices["home"] = price
                elif label in {"x", "draw", "tie"}:
                    prices["draw"] = price
                elif label in {"2", "away", away} or (away and away in label):
                    prices["away"] = price
            if {"home", "draw", "away"}.issubset(prices):
                return prices["home"], prices["draw"], prices["away"]
    return None, None, None


def extract_rows(
    payload: list[dict[str, Any]],
    event_meta: dict[str, dict[str, Any]],
    *,
    bookmaker_name: str,
    captured_at: str,
    capture_mode: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in payload:
        event_id = str(event.get("id") or "")
        meta = event_meta.get(event_id, {})
        home_team = str(event.get("home") or meta.get("home") or "")
        away_team = str(event.get("away") or meta.get("away") or "")
        kickoff = str(event.get("date") or meta.get("date") or meta.get("startTime") or "")
        competition = event_league(meta) or event_league(event)
        home_price, draw_price, away_price = three_way_prices(event, bookmaker_name)
        for bookmaker, markets in (event.get("bookmakers") or {}).items():
            if str(bookmaker).casefold() != bookmaker_name.casefold():
                continue
            for market in markets or []:
                if classify_market(market.get("name")) != "player_saves":
                    continue
                for prop in market.get("odds") or []:
                    line = parse_float(prop.get("hdp"))
                    over = parse_float(prop.get("over"))
                    under = parse_float(prop.get("under"))
                    player = str(prop.get("label") or prop.get("name") or "").strip()
                    has_over = over is not None and over > 1.0
                    has_under = under is not None and under > 1.0
                    if not player or line is None or not (has_over or has_under):
                        continue
                    base_row = {
                            "captured_at": captured_at,
                            "match_date": kickoff[:10],
                            "event_id": event_id,
                            "kickoff_at": kickoff,
                            "capture_mode": capture_mode,
                            "bookmaker": str(bookmaker),
                            "competition": competition,
                            "league": league_key(competition),
                            "home_team": home_team,
                            "away_team": away_team,
                            "player": player,
                            "line": f"{line:g}",
                            "under_odds_decimal": f"{under:.4f}" if under and under > 1.0 else "",
                            "home_price": f"{home_price:.4f}" if home_price else "",
                            "draw_price": f"{draw_price:.4f}" if draw_price else "",
                            "away_price": f"{away_price:.4f}" if away_price else "",
                            "source": "odds_api_io",
                        }
                    if has_over:
                        rows.append({**base_row, "side": "over", "odds_decimal": f"{over:.4f}"})
                    if has_under:
                        rows.append({**base_row, "side": "under", "odds_decimal": f"{under:.4f}"})
    return rows


def append_rows(path: Path, rows: list[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: set[tuple[str, ...]] = set()
    if path.exists():
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                existing.add(tuple(str(row.get(key) or "") for key in ("captured_at", "event_id", "player", "line", "side")))
    mode = "a" if path.exists() and path.stat().st_size else "w"
    added = 0
    with path.open(mode, newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore", lineterminator="\n")
        if mode == "w":
            writer.writeheader()
        for row in rows:
            key = tuple(str(row.get(field) or "") for field in ("captured_at", "event_id", "player", "line", "side"))
            if key in existing:
                continue
            writer.writerow(row)
            existing.add(key)
            added += 1
    return added


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture Bet365 goalkeeper saves prices")
    parser.add_argument("--bookmaker", default="Bet365")
    parser.add_argument("--days-ahead", type=int, default=7)
    parser.add_argument("--max-events", type=int, default=10)
    parser.add_argument("--kickoff-within-minutes", type=int, default=0)
    parser.add_argument("--capture-mode", choices=("publication", "close"), default="publication")
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    args = parser.parse_args()

    load_env()
    api_key = (os.environ.get("ODDS_API_KEY") or os.environ.get("ODDS_API_IO_KEY") or "").strip()
    if not api_key:
        raise SystemExit("Set ODDS_API_KEY or ODDS_API_IO_KEY")
    now = datetime.now(UTC).replace(microsecond=0)
    discovered = request_json(
        "/events",
        {
            "apiKey": api_key,
            "sport": "football",
            "status": "pending",
            "from": now.isoformat().replace("+00:00", "Z"),
            "to": (now + timedelta(days=max(1, args.days_ahead))).isoformat().replace("+00:00", "Z"),
            "limit": 5000,
        },
    )
    events = supported_events(
        discovered if isinstance(discovered, list) else [],
        max_events=args.max_events,
        kickoff_within_minutes=args.kickoff_within_minutes,
        now=now,
    )
    event_ids = [str(event["id"]) for event in events]
    payload: list[dict[str, Any]] = []
    if event_ids:
        result = request_json(
            "/odds/multi",
            {"apiKey": api_key, "eventIds": ",".join(event_ids), "bookmakers": args.bookmaker},
        )
        payload = result if isinstance(result, list) else []
    captured_at = now.isoformat().replace("+00:00", "Z")
    rows = extract_rows(
        payload,
        {str(event["id"]): event for event in events},
        bookmaker_name=args.bookmaker,
        captured_at=captured_at,
        capture_mode=args.capture_mode,
    )
    added = append_rows(args.history, rows)
    status = {
        "generated_at": captured_at,
        "status": "CAPTURED" if rows else "NO_GOALKEEPER_SAVE_LINES",
        "requests_used": 1 + int(bool(event_ids)),
        "request_budget": 2,
        "events_selected": len(event_ids),
        "events_with_lines": len({row["event_id"] for row in rows}),
        "rows_observed": len(rows),
        "rows_added": added,
        "capture_mode": args.capture_mode,
    }
    args.status.parent.mkdir(parents=True, exist_ok=True)
    args.status.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(status, sort_keys=True))


if __name__ == "__main__":
    main()
