#!/usr/bin/env python3
"""Bounded Odds-API.io probe for Bet365 football foul markets.

The documented REST API returns all available markets for an event; there is
no separate market selector on /odds or /odds/multi. This probe uses at most
one event-discovery request and one multi-odds request, and stores labels only.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from football_count_markets import classify_market, market_line_sides


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://api.odds-api.io/v3"
DEFAULT_JSON = ROOT / "data" / "football-form" / "football-foul-market-probe.json"
DEFAULT_REPORT = ROOT / "data" / "football-form" / "football-foul-market-probe.md"


def load_env(path: Path | None = None) -> None:
    candidates = [path] if path else [ROOT / ".env.local", ROOT / "env.local"]
    for candidate in candidates:
        if candidate is None or not candidate.exists():
            continue
        for raw_line in candidate.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def request_json(path: str, params: dict[str, Any]) -> Any:
    response = requests.get(f"{BASE_URL}{path}", params=params, timeout=45)
    response.raise_for_status()
    return response.json()


def market_labels(payload: list[dict[str, Any]]) -> dict[str, Any]:
    all_labels: set[str] = set()
    foul_labels: set[str] = set()
    card_labels: set[str] = set()
    events_with_fouls: set[str] = set()
    paired_foul_lines: list[dict[str, Any]] = []
    bookmaker_events = 0
    for event in payload:
        event_id = str(event.get("id") or "")
        bookmakers = event.get("bookmakers") or {}
        for bookmaker, markets in bookmakers.items():
            if markets:
                bookmaker_events += 1
            for market in markets or []:
                name = str(market.get("name") or "").strip()
                if not name:
                    continue
                all_labels.add(f"{bookmaker}: {name}")
                lower = name.lower()
                if "foul" in lower:
                    foul_labels.add(f"{bookmaker}: {name}")
                    events_with_fouls.add(event_id)
                    if classify_market(name) in {"team_fouls_total", "match_fouls_total"}:
                        for line, sides in market_line_sides(market).items():
                            if {"over", "under"}.issubset(sides):
                                paired_foul_lines.append(
                                    {
                                        "event_id": event_id,
                                        "bookmaker": str(bookmaker),
                                        "market_name": name,
                                        "line": line,
                                    }
                                )
                if "card" in lower or "booking" in lower:
                    card_labels.add(f"{bookmaker}: {name}")
    return {
        "bookmaker_event_payloads": bookmaker_events,
        "all_market_labels": sorted(all_labels),
        "foul_market_labels": sorted(foul_labels),
        "card_market_labels": sorted(card_labels),
        "events_with_foul_markets": len(events_with_fouls),
        "paired_foul_lines": paired_foul_lines,
    }


def render(payload: dict[str, Any]) -> str:
    labels = payload.get("labels") or {}
    lines = [
        "# Odds-API.io Football Foul Market Probe",
        "",
        f"Generated: {payload['generated_at']}",
        f"Status: **{payload['status']}**",
        f"Bookmaker: {payload['bookmaker']}",
        f"Events probed: {payload['events_probed']}",
        f"HTTP requests: {payload['requests_used']}",
        "",
        "The documented `/v3/odds/multi` endpoint returns every market available to the account for the requested bookmaker. No separate REST market selector or team-fouls tier endpoint is documented.",
        "",
        "## Foul labels",
        "",
    ]
    lines.extend(f"- {label}" for label in labels.get("foul_market_labels") or [])
    if not labels.get("foul_market_labels"):
        lines.append("- None returned in this bounded event sample.")
    if labels.get("paired_foul_lines"):
        lines.append("")
        lines.append(f"Paired team/match foul O/U lines: {len(labels['paired_foul_lines'])}.")
    lines.extend(["", "## Card / booking controls", ""])
    lines.extend(f"- {label}" for label in labels.get("card_market_labels") or [])
    if not labels.get("card_market_labels"):
        lines.append("- None returned.")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- {payload['decision']}",
            "- A market shown on Bet365's website is not automatable unless paired prices are returned by the feed.",
            "- No Team Fouls model signal is authorized by this probe.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Bet365 football foul markets using two API requests.")
    parser.add_argument("--bookmaker", default="Bet365")
    parser.add_argument("--days-ahead", type=int, default=3)
    parser.add_argument("--max-events", type=int, default=10)
    parser.add_argument("--event-id", action="append", default=[])
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    load_env(args.env_file)
    api_key = (os.environ.get("ODDS_API_KEY") or os.environ.get("ODDS_API_IO_KEY") or "").strip()
    if not api_key:
        raise SystemExit("Set ODDS_API_KEY or ODDS_API_IO_KEY; the key is never written to output.")

    requests_used = 0
    event_ids = [str(value).strip() for value in args.event_id if str(value).strip()]
    events: list[dict[str, Any]] = []
    try:
        if not event_ids:
            now = datetime.now(UTC)
            discovered = request_json(
                "/events",
                {
                    "apiKey": api_key,
                    "sport": "football",
                    "status": "pending",
                    "from": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "to": (now + timedelta(days=max(1, args.days_ahead))).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "limit": 5000,
                },
            )
            requests_used += 1
            events = discovered if isinstance(discovered, list) else []
            event_ids = [str(event.get("id")) for event in events if event.get("id")][: max(1, min(10, args.max_events))]
        if not event_ids:
            status = "NO_PENDING_EVENTS"
            odds_payload: list[dict[str, Any]] = []
        else:
            odds = request_json(
                "/odds/multi",
                {
                    "apiKey": api_key,
                    "eventIds": ",".join(event_ids[:10]),
                    "bookmakers": args.bookmaker,
                },
            )
            requests_used += 1
            odds_payload = odds if isinstance(odds, list) else [odds] if isinstance(odds, dict) else []
            observed = market_labels(odds_payload)
            status = (
                "PAIRED_FOUL_PRICES_RETURNED"
                if observed["paired_foul_lines"]
                else "FOUL_MARKETS_RETURNED_UNPAIRED"
                if observed["foul_market_labels"]
                else "NO_FOUL_MARKETS_RETURNED"
            )
        labels = market_labels(odds_payload)
        decision = (
            "Paired foul lines were returned; implement capture only after settlement scope is confirmed."
            if labels["paired_foul_lines"]
            else "Foul labels were returned without proven paired O/U prices; M0 remains blocked."
            if labels["foul_market_labels"]
            else "The configured Bet365 feed did not return a foul market in the probed events. M0 remains blocked."
        )
        error = None
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        status = f"HTTP_{status_code or 'ERROR'}"
        labels = market_labels([])
        decision = "Access failed. Check bookmaker selection/account access with Odds-API.io support; do not infer market availability."
        error = f"HTTP {status_code}" if status_code else type(exc).__name__

    payload = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "endpoint": "/v3/odds/multi",
        "bookmaker": args.bookmaker,
        "events_probed": len(event_ids[:10]),
        "requests_used": requests_used,
        "status": status,
        "labels": labels,
        "decision": decision,
        "error": error,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report_out.write_text(render(payload), encoding="utf-8")
    print(f"Football foul market probe: {status}; events={payload['events_probed']}; requests={requests_used}")
    for label in labels["foul_market_labels"]:
        print(f"  foul: {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
