#!/usr/bin/env python3
"""Capture public BetsBK US Open aces and double-fault prices.

Odds-API does not currently return those markets for US Open qualifying. BetsBK
publishes the same pre-match prices on its public event pages, so this local-only
fallback reads the public event hierarchy and renders each relevant event in one
headless browser session. It does not log in or write to Supabase.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "tennis-props" / "inbox"
API_BASE = "https://api.betsbk.com"
WEB_BASE = "https://betsbk.com"
US_OPEN_CATEGORIES = {
    "ATP": "41830091",
    "WTA": "41830097",
}
OUTPUT_FIELDS = [
    "event_id",
    "date",
    "tour",
    "tournament",
    "bookmaker",
    "player",
    "opponent",
    "market",
    "line",
    "over_odds",
    "under_odds",
    "capture_ts",
    "match_start_utc",
    "raw_market_name",
    "raw_outcome_count",
    "raw_label_sample",
]
AUDIT_FIELDS = [
    "captured_at",
    "event_id",
    "date",
    "tour",
    "match",
    "start_utc",
    "status",
    "markets_captured",
    "detail",
]


def fetch_json(path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    query = f"?{urlencode(params)}" if params else ""
    request = Request(
        f"{API_BASE}{path}{query}",
        headers={"Accept": "application/json", "User-Agent": "IlMargine/1.0 public-market-audit"},
    )
    with urlopen(request, timeout=25) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def event_scope(event: dict[str, Any]) -> str:
    event_type = event.get("type")
    if isinstance(event_type, dict):
        return str(event_type.get("scope") or "")
    return str(event_type or "")


def discover_events(as_of: str, days_ahead: int) -> list[dict[str, str]]:
    start = date.fromisoformat(as_of)
    allowed_dates = {(start + timedelta(days=offset)).isoformat() for offset in range(max(0, days_ahead) + 1)}
    discovered: list[dict[str, str]] = []
    for tour, category_id in US_OPEN_CATEGORIES.items():
        payload = fetch_json(
            "/x0/events/",
            {
                "with_new_type": "true",
                "platform": "sbk",
                "jurisdiction": "UKGC",
                "parent_id": category_id,
                "limit": "200",
            },
        )
        for raw_event in payload.get("events") or []:
            if not isinstance(raw_event, dict):
                continue
            if event_scope(raw_event) not in {"single_event", "tennis_match"}:
                continue
            event_date = str(raw_event.get("start_date") or "")
            if event_date not in allowed_dates:
                continue
            if not raw_event.get("bettable") or str(raw_event.get("state") or "").lower() != "upcoming":
                continue
            event_id = str(raw_event.get("id") or "")
            name = str(raw_event.get("name") or "").strip()
            if not event_id or " vs " not in name.lower():
                continue
            discovered.append(
                {
                    "event_id": event_id,
                    "date": event_date,
                    "tour": tour,
                    "name": name,
                    "start_utc": str(raw_event.get("start_datetime") or ""),
                }
            )
    return sorted(discovered, key=lambda row: (row["start_utc"], row["event_id"]))


def split_match(name: str) -> tuple[str, str] | None:
    parts = re.split(r"\s+vs\s+", name.strip(), maxsplit=1, flags=re.I)
    if len(parts) != 2 or not all(part.strip() for part in parts):
        return None
    return parts[0].strip(), parts[1].strip()


def parse_price_buttons(button_texts: list[str]) -> tuple[str, str, str] | None:
    parsed: dict[str, tuple[str, str]] = {}
    for raw_text in button_texts:
        text = " ".join(str(raw_text or "").split())
        match = re.fullmatch(r"(OVER|UNDER)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)", text, flags=re.I)
        if not match:
            continue
        side, line, odds = match.groups()
        try:
            if float(odds) <= 1.0:
                continue
        except ValueError:
            continue
        parsed[side.upper()] = (line, odds)
    if "OVER" not in parsed or "UNDER" not in parsed:
        return None
    over_line, over_odds = parsed["OVER"]
    under_line, under_odds = parsed["UNDER"]
    if over_line != under_line:
        return None
    return over_line, over_odds, under_odds


def browser_executable() -> Path | None:
    candidates = (
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    )
    return next((path for path in candidates if path.exists()), None)


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_rows(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def output_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(str(row.get(field) or "").strip() for field in OUTPUT_FIELDS)


def merge_snapshot(path: Path, new_rows: list[dict[str, str]]) -> int:
    existing = read_rows(path)
    refreshed_events = {row["event_id"] for row in new_rows if row.get("event_id")}
    retained = [
        row
        for row in existing
        if not (
            str(row.get("bookmaker") or "").strip().lower() == "betsbk"
            and str(row.get("event_id") or "") in refreshed_events
        )
    ]
    combined = retained + new_rows
    write_rows(path, combined, OUTPUT_FIELDS)
    return len(new_rows)


def append_history(path: Path, new_rows: list[dict[str, str]]) -> int:
    existing = read_rows(path)
    seen = {output_key(row) for row in existing}
    added = 0
    for row in new_rows:
        key = output_key(row)
        if key in seen:
            continue
        existing.append(row)
        seen.add(key)
        added += 1
    write_rows(path, existing, OUTPUT_FIELDS)
    return added


def extract_market(page: Any, heading: str, timeout_ms: int) -> tuple[str, str, str, list[str]] | None:
    locator = page.get_by_text(heading, exact=True).first
    if locator.count() == 0:
        return None
    target = locator.locator("xpath=..").get_attribute("aria-controls")
    if not target:
        return None
    region = page.locator(f"#{target}")
    region.get_by_role("button").first.wait_for(state="attached", timeout=min(timeout_ms, 5000))
    button_texts = region.get_by_role("button").all_inner_texts()
    parsed = parse_price_buttons(button_texts)
    if parsed is None:
        return None
    line, over_odds, under_odds = parsed
    return line, over_odds, under_odds, button_texts


def capture_events(
    events: list[dict[str, str]],
    *,
    timeout_seconds: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is not installed for this Python interpreter") from exc

    executable = browser_executable()
    if executable is None:
        raise RuntimeError("Microsoft Edge or Google Chrome was not found")

    captured_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows: list[dict[str, str]] = []
    audit: list[dict[str, str]] = []
    timeout_ms = max(5, timeout_seconds) * 1000
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=str(executable))
        context = browser.new_context(locale="en-GB", timezone_id="Europe/London")
        page = context.new_page()

        def route_handler(route: Any) -> None:
            if route.request.resource_type in {"image", "media", "font"}:
                route.abort()
            else:
                route.continue_()

        page.route("**/*", route_handler)
        for index, event in enumerate(events, start=1):
            pair = split_match(event["name"])
            if pair is None:
                continue
            player1, player2 = pair
            event_rows: list[dict[str, str]] = []
            detail = ""
            try:
                page.goto(
                    f"{WEB_BASE}/event/{event['event_id']}/",
                    wait_until="domcontentloaded",
                    timeout=timeout_ms,
                )
                try:
                    page.get_by_text(re.compile(r"(?:Aces|Double Faults)$")).first.wait_for(
                        state="attached",
                        timeout=timeout_ms,
                    )
                except PlaywrightTimeoutError:
                    status = "NO_ACES_DF_MARKETS"
                    raise LookupError("No full-match aces or double-fault market headings loaded")
                for player, opponent in ((player1, player2), (player2, player1)):
                    for market, suffix in (("aces", "Aces"), ("double_faults", "Double Faults")):
                        heading = f"{player} {suffix}"
                        try:
                            result = extract_market(page, heading, timeout_ms)
                        except PlaywrightTimeoutError:
                            result = None
                        if result is None:
                            continue
                        line, over_odds, under_odds, labels = result
                        event_rows.append(
                            {
                                "event_id": event["event_id"],
                                "date": event["date"],
                                "tour": event["tour"],
                                "tournament": "US Open",
                                "bookmaker": "BetsBK",
                                "player": player,
                                "opponent": opponent,
                                "market": market,
                                "line": line,
                                "over_odds": over_odds,
                                "under_odds": under_odds,
                                "capture_ts": captured_at,
                                "match_start_utc": event["start_utc"],
                                "raw_market_name": heading,
                                "raw_outcome_count": str(len(labels)),
                                "raw_label_sample": " | ".join(" ".join(label.split()) for label in labels),
                            }
                        )
                status = "CAPTURED" if event_rows else "NO_ACES_DF_MARKETS"
            except LookupError as exc:
                detail = str(exc)
            except Exception as exc:  # Browser/network failures must remain visible per event.
                status = "PAGE_ERROR"
                detail = f"{type(exc).__name__}: {exc}"[:300]
            rows.extend(event_rows)
            audit.append(
                {
                    "captured_at": captured_at,
                    "event_id": event["event_id"],
                    "date": event["date"],
                    "tour": event["tour"],
                    "match": event["name"],
                    "start_utc": event["start_utc"],
                    "status": status,
                    "markets_captured": str(len(event_rows)),
                    "detail": detail,
                }
            )
            print(f"[{index}/{len(events)}] {status}: {event['name']} ({len(event_rows)} rows)", flush=True)
        context.close()
        browser.close()
    return rows, audit


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture public BetsBK US Open aces/DF prices")
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--days-ahead", type=int, default=2)
    parser.add_argument("--max-events", type=int, default=64)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--event-id", default="", help="Capture one discovered event for diagnosis")
    parser.add_argument("--out", default="")
    parser.add_argument("--history-out", default="")
    parser.add_argument("--audit-out", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        events = discover_events(args.date, args.days_ahead)
    except Exception as exc:
        print(f"BetsBK discovery failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    if args.event_id:
        events = [event for event in events if event["event_id"] == args.event_id]
    if args.max_events:
        events = events[: max(0, args.max_events)]
    print(f"BetsBK US Open events selected: {len(events)}")
    if not events:
        return 0

    try:
        rows, audit_rows = capture_events(events, timeout_seconds=args.timeout_seconds)
    except Exception as exc:
        print(f"BetsBK browser capture unavailable: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3

    out = Path(args.out) if args.out else OUT_DIR / f"betsbk-lines-{args.date}.csv"
    month = args.date[:7]
    history_out = Path(args.history_out) if args.history_out else OUT_DIR / f"betsbk-lines-history-{month}.csv"
    audit_out = Path(args.audit_out) if args.audit_out else OUT_DIR / f"betsbk-tennis-market-audit-{args.date}.csv"
    print(f"BetsBK supported rows: {len(rows)}")
    if args.dry_run:
        for row in rows[:20]:
            print(row)
        return 0
    write_rows(audit_out, audit_rows, AUDIT_FIELDS)
    if rows:
        merge_snapshot(out, rows)
        history_added = append_history(history_out, rows)
        print(f"Merged lines: {out}")
        print(f"Price history: added {history_added}, file={history_out}")
    else:
        print("No BetsBK aces/DF rows captured; existing lines file left unchanged.")
    print(f"Saved audit: {audit_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
