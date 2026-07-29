#!/usr/bin/env python3
"""Capture BetMGM Most Aces 1X2 prices from odds-api.io."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "data" / "tennis-props" / "inbox"
COMMON_PATH = ROOT / "scripts" / "tennis-props-scrape-bet365.py"
FIELDS = [
    "event_id", "date", "tour", "tournament", "bookmaker", "player1", "player2",
    "player1_odds", "draw_odds", "player2_odds", "capture_ts", "match_start_utc",
    "raw_market_name", "raw_outcome_count", "raw_label_sample",
]
AUDIT_FIELDS = [
    "captured_at", "event_id", "kickoff_at", "bookmaker", "tour", "tournament",
    "player1", "player2", "market_name", "recognized_most_aces", "odds_count",
    "sample_labels",
]


def norm_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def load_common():
    spec = importlib.util.spec_from_file_location("tennis_props_odds_common", COMMON_PATH)
    if not spec or not spec.loader:
        raise RuntimeError(f"Cannot load {COMMON_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def decimal(value: object) -> float | None:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 1.0 else None


def is_most_aces_market(name: object) -> bool:
    text = norm_name(name)
    return "ace" in text and (
        "most ace" in text
        or "serve most" in text
        or "highest ace" in text
        or "ace match bet" in text
    )


def outcome_price(outcome: dict[str, Any]) -> float | None:
    for key in ("odds", "value", "price", "decimal", "back"):
        price = decimal(outcome.get(key))
        if price is not None:
            return price
    return None


def outcome_label(outcome: dict[str, Any]) -> str:
    for key in ("label", "name", "player", "participant", "competitor", "runner", "team"):
        value = str(outcome.get(key) or "").strip()
        if value:
            return value
    return ""


def classify_label(label: object, player1: str, player2: str) -> str | None:
    text = norm_name(label)
    if text in {"draw", "tie", "equal", "same number", "same amount"} or "draw" in text or "tie" in text:
        return "DRAW"
    first = norm_name(player1)
    second = norm_name(player2)
    if text and (text == first or text in first or first in text):
        return "P1"
    if text and (text == second or text in second or second in text):
        return "P2"
    return None


def extract_market_prices(
    market: dict[str, Any], player1: str, player2: str
) -> tuple[float, float, float] | None:
    prices: dict[str, float] = {}
    direct = {
        "P1": decimal(market.get("home") or market.get("player1")),
        "DRAW": decimal(market.get("draw") or market.get("tie")),
        "P2": decimal(market.get("away") or market.get("player2")),
    }
    prices.update({key: value for key, value in direct.items() if value is not None})
    for outcome in market.get("odds") or market.get("outcomes") or []:
        nested = {
            "P1": decimal(outcome.get("home") or outcome.get("player1")),
            "DRAW": decimal(outcome.get("draw") or outcome.get("tie")),
            "P2": decimal(outcome.get("away") or outcome.get("player2")),
        }
        prices.update({key: value for key, value in nested.items() if value is not None})
        price = outcome_price(outcome)
        side = classify_label(outcome_label(outcome), player1, player2)
        if price is not None and side:
            prices[side] = price
    if set(prices) != {"P1", "DRAW", "P2"}:
        return None
    return prices["P1"], prices["DRAW"], prices["P2"]


def extract_rows(payload: list[dict[str, Any]], captured_at: str, common) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for event in payload:
        player1 = common.clean_player(event.get("home") or event.get("home_team") or "")
        player2 = common.clean_player(event.get("away") or event.get("away_team") or "")
        if not player1 or not player2:
            continue
        for bookmaker, markets in (event.get("bookmakers") or {}).items():
            for market in markets or []:
                market_name = str(market.get("name") or "")
                if not is_most_aces_market(market_name):
                    continue
                prices = extract_market_prices(market, player1, player2)
                if not prices:
                    continue
                outcomes = market.get("odds") or market.get("outcomes") or []
                rows.append({
                    "event_id": str(event.get("id") or ""),
                    "date": str(event.get("date") or "")[:10],
                    "tour": common.tour_from_event(event),
                    "tournament": common.tournament_from_event(event),
                    "bookmaker": bookmaker,
                    "player1": player1,
                    "player2": player2,
                    "player1_odds": f"{prices[0]:.4f}",
                    "draw_odds": f"{prices[1]:.4f}",
                    "player2_odds": f"{prices[2]:.4f}",
                    "capture_ts": captured_at,
                    "match_start_utc": str(event.get("date") or ""),
                    "raw_market_name": market_name,
                    "raw_outcome_count": str(len(outcomes)),
                    "raw_label_sample": " | ".join(outcome_label(row) for row in outcomes[:5]),
                })
    return rows


def extract_audit_rows(
    payload: list[dict[str, Any]], captured_at: str, common
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for event in payload:
        player1 = common.clean_player(event.get("home") or event.get("home_team") or "")
        player2 = common.clean_player(event.get("away") or event.get("away_team") or "")
        for bookmaker, markets in (event.get("bookmakers") or {}).items():
            for market in markets or []:
                market_name = str(market.get("name") or "")
                outcomes = market.get("odds") or market.get("outcomes") or []
                rows.append({
                    "captured_at": captured_at,
                    "event_id": str(event.get("id") or ""),
                    "kickoff_at": str(event.get("date") or ""),
                    "bookmaker": bookmaker,
                    "tour": common.tour_from_event(event),
                    "tournament": common.tournament_from_event(event),
                    "player1": player1,
                    "player2": player2,
                    "market_name": market_name,
                    "recognized_most_aces": "yes" if is_most_aces_market(market_name) else "no",
                    "odds_count": str(len(outcomes)),
                    "sample_labels": " | ".join(outcome_label(row) for row in outcomes[:5]),
                })
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def append_history(path: Path, rows: list[dict[str, str]]) -> int:
    existing: list[dict[str, str]] = []
    if path.exists():
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            existing = [dict(row) for row in csv.DictReader(handle)]
    key_fields = ("event_id", "bookmaker", "capture_ts", "player1_odds", "draw_odds", "player2_odds")
    seen = {tuple(row.get(field, "") for field in key_fields) for row in existing}
    added = 0
    for row in rows:
        key = tuple(row.get(field, "") for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        existing.append(row)
        added += 1
    write_csv(path, existing)
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--days-ahead", type=int, default=2)
    parser.add_argument("--max-events", type=int, default=64)
    parser.add_argument("--bookmakers", default="BetMGM")
    parser.add_argument("--out", default="")
    parser.add_argument("--history-out", default="")
    parser.add_argument("--audit-out", default="")
    args = parser.parse_args()
    common = load_common()
    common.load_env()
    api_key = common.os.environ.get("ODDS_API_KEY") or common.os.environ.get("ODDS_API_IO_KEY")
    if not api_key:
        raise SystemExit("Set ODDS_API_KEY or ODDS_API_IO_KEY to capture BetMGM Most Aces.")
    now = datetime.now(timezone.utc)
    from_iso = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    to_iso = (now + timedelta(days=args.days_ahead)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    events = common.fetch_json("events", {
        "apiKey": api_key, "sport": "tennis", "status": "pending",
        "from": from_iso, "to": to_iso,
    })
    events = [
        event for event in (events if isinstance(events, list) else [])
        if common.is_supported_tournament_event(event) and common.is_singles_event(event)
    ][:args.max_events]
    payload = common.fetch_multi(api_key, [str(event.get("id")) for event in events], args.bookmakers)
    captured_at = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows = extract_rows(payload, captured_at, common)
    audit_rows = extract_audit_rows(payload, captured_at, common)
    output = Path(args.out) if args.out else INBOX / f"betmgm-most-aces-1x2-{args.date}.csv"
    history = Path(args.history_out) if args.history_out else INBOX / f"betmgm-most-aces-history-{args.date[:7]}.csv"
    audit = Path(args.audit_out) if args.audit_out else INBOX / f"betmgm-tennis-market-audit-{args.date}.csv"
    write_csv(output, rows)
    audit.parent.mkdir(parents=True, exist_ok=True)
    with audit.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=AUDIT_FIELDS)
        writer.writeheader()
        writer.writerows(audit_rows)
    added = append_history(history, rows)
    print(f"BetMGM Most Aces: {len(rows)} current rows; {added} history rows added")
    print(f"BetMGM markets audited: {len(audit_rows)}")
    print(f"Current: {output}")
    print(f"History: {history}")
    print(f"Audit: {audit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
