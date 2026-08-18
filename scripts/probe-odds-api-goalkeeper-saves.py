#!/usr/bin/env python3
"""Bounded Odds-API.io probe for Bet365 goalkeeper-save markets.

The probe performs at most one event-discovery request and one multi-odds
request. It records market structure only and never writes signals or data to
Supabase.
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
DEFAULT_JSON = ROOT / "data" / "goalkeeper-saves" / "gk-saves-market-probe.json"
DEFAULT_REPORT = ROOT / "data" / "goalkeeper-saves" / "gk-saves-market-probe.md"


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


def goalkeeper_save_markets(payload: list[dict[str, Any]]) -> dict[str, Any]:
    labels: set[str] = set()
    events: set[str] = set()
    paired_lines: list[dict[str, Any]] = []
    structures: list[dict[str, Any]] = []
    for event in payload:
        event_id = str(event.get("id") or "")
        for bookmaker, markets in (event.get("bookmakers") or {}).items():
            for market in markets or []:
                name = str(market.get("name") or "").strip()
                if classify_market(name) != "player_saves":
                    continue
                labels.add(f"{bookmaker}: {name}")
                events.add(event_id)
                sides_by_line = market_line_sides(market)
                props = market.get("odds") or []
                structures.append(
                    {
                        "event_id": event_id,
                        "bookmaker": str(bookmaker),
                        "market_name": name,
                        "odds_count": len(props),
                        "prop_keys": sorted({str(key) for prop in props for key in prop.keys()}),
                        "sample_labels": [
                            str(prop.get("label") or prop.get("name") or "").strip()
                            for prop in props[:6]
                            if str(prop.get("label") or prop.get("name") or "").strip()
                        ],
                    }
                )
                for line, sides in sides_by_line.items():
                    if {"over", "under"}.issubset(sides):
                        paired_lines.append(
                            {
                                "event_id": event_id,
                                "bookmaker": str(bookmaker),
                                "market_name": name,
                                "line": line,
                            }
                        )
    return {
        "market_labels": sorted(labels),
        "events_with_goalkeeper_saves": len(events),
        "paired_lines": paired_lines,
        "structures": structures,
    }


def render(payload: dict[str, Any]) -> str:
    observed = payload["observed"]
    lines = [
        "# Goalkeeper Saves Market Probe",
        "",
        f"Generated: {payload['generated_at']}",
        f"Status: **{payload['status']}**",
        f"Bookmaker: {payload['bookmaker']}",
        f"Events probed: {payload['events_probed']}",
        f"HTTP requests: {payload['requests_used']} / 2 maximum",
        "",
        "## Returned labels",
        "",
    ]
    labels = observed.get("market_labels") or []
    lines.extend(f"- {label}" for label in labels)
    if not labels:
        lines.append("- None in this bounded sample.")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- {payload['decision']}",
            "- This probe does not authorize signals, stakes, ROI claims or CLV claims.",
            "",
        ]
    )
    return "\n".join(lines)


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    load_env(args.env_file)
    api_key = (os.environ.get("ODDS_API_KEY") or os.environ.get("ODDS_API_IO_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("Set ODDS_API_KEY or ODDS_API_IO_KEY; the key is never written to output.")

    requests_used = 0
    event_ids = [str(value).strip() for value in args.event_id if str(value).strip()]
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
                    "to": (now + timedelta(days=max(1, args.days_ahead)))
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "limit": 5000,
                },
            )
            requests_used += 1
            events = discovered if isinstance(discovered, list) else []
            event_ids = [str(event.get("id")) for event in events if event.get("id")][
                : max(1, min(10, args.max_events))
            ]

        odds_payload: list[dict[str, Any]] = []
        if event_ids:
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
        observed = goalkeeper_save_markets(odds_payload)
        if observed["paired_lines"]:
            status = "PAIRED_GOALKEEPER_SAVE_PRICES_RETURNED"
            decision = "Implement prospective capture and settlement after player identity and line scope are verified."
        elif observed["market_labels"]:
            status = "GOALKEEPER_SAVE_MARKET_UNPAIRED"
            decision = "Market labels exist, but paired over/under lines are unproven; the market gate remains blocked."
        elif not event_ids:
            status = "NO_PENDING_EVENTS"
            decision = "No pending fixtures were available; rerun the bounded probe during an active fixture window."
        else:
            status = "NO_GOALKEEPER_SAVE_MARKET_RETURNED"
            decision = "Bet365 goalkeeper-save prices were not returned in this sample; the market gate remains blocked."
        error = None
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        status = f"HTTP_{status_code or 'ERROR'}"
        observed = goalkeeper_save_markets([])
        decision = "API access failed; do not infer market availability or authorize signals."
        error = f"HTTP {status_code}" if status_code else type(exc).__name__

    if requests_used > 2:
        raise RuntimeError(f"Request budget breached: {requests_used}/2")
    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "endpoint": "/v3/odds/multi",
        "bookmaker": args.bookmaker,
        "events_probed": len(event_ids[:10]),
        "requests_used": requests_used,
        "status": status,
        "observed": observed,
        "decision": decision,
        "error": error,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bookmaker", default="Bet365")
    parser.add_argument("--days-ahead", type=int, default=3)
    parser.add_argument("--max-events", type=int, default=10)
    parser.add_argument("--event-id", action="append", default=[])
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    try:
        payload = run_probe(args)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report_out.write_text(render(payload), encoding="utf-8")
    print(
        f"Goalkeeper saves market probe: {payload['status']}; "
        f"events={payload['events_probed']}; requests={payload['requests_used']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
