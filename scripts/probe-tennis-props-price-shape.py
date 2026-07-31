#!/usr/bin/env python3
"""Run three bounded Odds-API requests to diagnose missing tennis under prices."""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "https://api.odds-api.io/v3/odds"
DEFAULT_INBOX = ROOT / "data" / "tennis-props" / "inbox"
PROP_MARKET_TOKENS = ("ace", "double fault")
VARIANTS: tuple[tuple[str, dict[str, str]], ...] = (
    ("baseline", {}),
    ("include_all", {"include": "all"}),
    (
        "player_props_full_ladder",
        {"hide_main_liner": "false", "markets": "player_props"},
    ),
)


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


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def select_event_id(rows: list[dict[str, str]], as_of: str) -> str:
    candidates: list[tuple[str, str]] = []
    for row in rows:
        event_id = str(row.get("event_id") or "").strip()
        event_date = str(row.get("date") or "").strip()
        market = str(row.get("raw_market_name") or row.get("market") or "").lower()
        if not event_id or not event_date or event_date < as_of:
            continue
        if not any(token in market for token in PROP_MARKET_TOKENS):
            continue
        candidates.append((event_date, event_id))
    if not candidates:
        return ""
    return sorted(candidates)[0][1]


def payload_events(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def summarize_payload(payload: Any) -> dict[str, object]:
    market_names: set[str] = set()
    prop_market_count = 0
    rung_count = 0
    two_way_count = 0
    over_only_count = 0
    under_only_count = 0
    for event in payload_events(payload):
        for markets in (event.get("bookmakers") or {}).values():
            for market in markets or []:
                name = str(market.get("name") or "")
                market_names.add(name)
                if not any(token in name.lower() for token in PROP_MARKET_TOKENS):
                    continue
                prop_market_count += 1
                for rung in market.get("odds") or market.get("outcomes") or []:
                    if not isinstance(rung, dict):
                        continue
                    rung_count += 1
                    has_over = rung.get("over") not in (None, "")
                    has_under = rung.get("under") not in (None, "")
                    if has_over and has_under:
                        two_way_count += 1
                    elif has_over:
                        over_only_count += 1
                    elif has_under:
                        under_only_count += 1
    return {
        "market_names": sorted(market_names),
        "ace_df_markets": prop_market_count,
        "rungs": rung_count,
        "two_way_rungs": two_way_count,
        "over_only_rungs": over_only_count,
        "under_only_rungs": under_only_count,
    }


def run_probe(
    api_key: str,
    event_id: str,
    *,
    bookmaker: str = "Bet365",
    requester: Any = requests.get,
) -> dict[str, object]:
    results: list[dict[str, object]] = []
    for label, extra in VARIANTS:
        params = {
            "apiKey": api_key,
            "eventId": event_id,
            "bookmakers": bookmaker,
            **extra,
        }
        try:
            response = requester(BASE_URL, params=params, timeout=30)
            status = int(response.status_code)
            if status < 400:
                summary = summarize_payload(response.json())
            else:
                summary = {"error": "http_error"}
        except (requests.RequestException, ValueError) as exc:
            status = 0
            summary = {"error": type(exc).__name__}
        results.append({"variant": label, "status": status, **summary})
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event_id": event_id,
        "bookmaker": bookmaker,
        "request_count": len(VARIANTS),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--lines", default="")
    parser.add_argument("--event-id", default="")
    parser.add_argument("--bookmaker", default="Bet365")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    load_env()
    api_key = os.environ.get("ODDS_API_KEY") or os.environ.get("ODDS_API_IO_KEY")
    if not api_key:
        print("Odds-API credential unavailable; probe not run.")
        return 2

    lines_path = (
        Path(args.lines)
        if args.lines
        else DEFAULT_INBOX / f"bet365-lines-{args.date}.csv"
    )
    event_id = str(args.event_id or "").strip() or select_event_id(
        read_rows(lines_path), args.date
    )
    if not event_id:
        print(f"No eligible ace/DF event ID found in {lines_path}; probe not run.")
        return 3

    payload = run_probe(api_key, event_id, bookmaker=args.bookmaker)
    out = (
        Path(args.out)
        if args.out
        else DEFAULT_INBOX / f"bet365-price-shape-probe-{args.date}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"Price-shape probe saved: {out} | "
        f"event={event_id} requests={payload['request_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
