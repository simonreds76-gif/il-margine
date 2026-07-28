#!/usr/bin/env python3
"""Summarise complete Pinnacle tennis derivative pairs with one weekly REST read."""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import unicodedata
from collections import Counter
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "vnext" / "tennis-derivatives-pinnacle-coverage.json"
LOCAL_HISTORY = ROOT / "data" / "pinnacle-history"
HTTP_TIMEOUT = 30


def load_env() -> None:
    for name in (".env.local", "env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def rest_config() -> tuple[str, dict[str, str]]:
    load_env()
    base = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/")
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
        or ""
    )
    if not base or not key:
        raise RuntimeError("Missing Supabase REST credentials")
    return f"{base}/rest/v1", {"apikey": key, "Authorization": f"Bearer {key}"}


def fetch_rows(start_date: date, end_date: date) -> list[dict[str, Any]]:
    base, headers = rest_config()
    fields = (
        "capture_date,captured_at,capture_mode,league,player1_name,player2_name,"
        "spread_line,spread_odds1,spread_odds2,ou_line,ou_over,ou_under,match_date,kickoff_iso"
    )
    fallback_fields = fields.replace(",match_date,kickoff_iso", "")
    rows: list[dict[str, Any]] = []
    offset = 0
    limit = 1000
    use_fields = fields
    while True:
        params = [
            ("select", use_fields),
            ("bookmaker", "eq.Pinnacle"),
            ("capture_date", f"gte.{start_date.isoformat()}"),
            ("capture_date", f"lte.{end_date.isoformat()}"),
            ("order", "captured_at.asc"),
            ("limit", str(limit)),
            ("offset", str(offset)),
        ]
        response = requests.get(
            f"{base}/bookmaker_odds_history",
            headers=headers,
            params=params,
            timeout=HTTP_TIMEOUT,
        )
        if not response.ok and use_fields == fields and (
            "match_date" in response.text or "kickoff_iso" in response.text
        ):
            use_fields = fallback_fields
            offset = 0
            rows = []
            continue
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return rows


def _date_from_path(path: Path) -> str:
    match = re.search(r"(20\d{2})-?(\d{2})-?(\d{2})", path.stem)
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}" if match else ""


def load_local_rows(start_date: date, end_date: date) -> list[dict[str, Any]]:
    """Load tracked daily snapshots plus optional ignored high-frequency history."""
    paths = list((ROOT / "data").glob("pinnacle-odds-20*.csv"))
    if LOCAL_HISTORY.exists():
        paths.extend(LOCAL_HISTORY.glob("pinnacle-history-*.csv"))
    rows: list[dict[str, Any]] = []
    for path in sorted(set(paths)):
        fallback_date = _date_from_path(path)
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    capture_date = str(row.get("capture_date") or fallback_date)[:10]
                    try:
                        parsed_date = date.fromisoformat(capture_date)
                    except ValueError:
                        continue
                    if parsed_date < start_date or parsed_date > end_date:
                        continue
                    normalized = dict(row)
                    normalized["capture_date"] = capture_date
                    normalized.setdefault("captured_at", str(row.get("captured_at") or ""))
                    normalized.setdefault("capture_mode", str(row.get("capture_mode") or "local_snapshot"))
                    normalized.setdefault("bookmaker", str(row.get("bookmaker") or "Pinnacle"))
                    normalized["_coverage_source"] = "local"
                    rows.append(normalized)
        except (OSError, csv.Error) as exc:
            print(f"WARNING: skipping unreadable local capture {path}: {exc}")
    return rows


def merge_rows(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows_by_key: dict[tuple[str, ...], dict[str, Any]] = {}
    for rows in groups:
        for row in rows:
            key = (
                str(row.get("captured_at") or row.get("capture_date") or ""),
                str(row.get("league") or ""),
                text_key(row.get("player1_name")),
                text_key(row.get("player2_name")),
                str(row.get("spread_line") or ""),
                str(row.get("spread_odds1") or ""),
                str(row.get("spread_odds2") or ""),
                str(row.get("ou_line") or ""),
                str(row.get("ou_over") or ""),
                str(row.get("ou_under") or ""),
            )
            rows_by_key[key] = row
    return list(rows_by_key.values())


def text_key(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def complete_pair(row: dict[str, Any], market: str) -> bool:
    if market == "spread":
        values = (row.get("spread_line"), row.get("spread_odds1"), row.get("spread_odds2"))
    else:
        values = (row.get("ou_line"), row.get("ou_over"), row.get("ou_under"))
    try:
        line, price1, price2 = (float(value) for value in values)
    except (TypeError, ValueError):
        return False
    return abs(line) < 100 and price1 > 1.0 and price2 > 1.0


def summarise(rows: list[dict[str, Any]], start_date: date, end_date: date) -> dict[str, Any]:
    captures = sorted(str(row.get("captured_at") or "") for row in rows if row.get("captured_at"))
    league_rows = Counter(str(row.get("league") or "unknown") for row in rows)
    result: dict[str, Any] = {
        "version": "tennis-derivative-coverage-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_start": start_date.isoformat(),
        "window_end": end_date.isoformat(),
        "snapshot_rows": len(rows),
        "first_capture_at": captures[0] if captures else None,
        "last_capture_at": captures[-1] if captures else None,
        "league_snapshot_rows": dict(league_rows),
        "snapshot_rows_by_source": dict(
            Counter(str(row.get("_coverage_source") or "supabase") for row in rows)
        ),
    }
    for market in ("spread", "total"):
        complete = [row for row in rows if complete_pair(row, market)]
        offers: set[tuple[str, ...]] = set()
        matches: set[tuple[str, ...]] = set()
        close_offers: set[tuple[str, ...]] = set()
        by_league: Counter[str] = Counter()
        offers_by_league: dict[str, set[tuple[str, ...]]] = defaultdict(set)
        matches_by_league: dict[str, set[tuple[str, ...]]] = defaultdict(set)
        for row in complete:
            names = sorted((text_key(row.get("player1_name")), text_key(row.get("player2_name"))))
            match_date = str(row.get("match_date") or row.get("capture_date") or "")[:10]
            league = str(row.get("league") or "unknown")
            line = str(row.get("spread_line") if market == "spread" else row.get("ou_line"))
            match_key = (league, match_date, *names)
            offer_key = (*match_key, line)
            offers.add(offer_key)
            matches.add(match_key)
            offers_by_league[league].add(offer_key)
            matches_by_league[league].add(match_key)
            by_league[league] += 1
            if str(row.get("capture_mode") or "").lower() == "close":
                close_offers.add(offer_key)
        result[market] = {
            "complete_snapshot_rows": len(complete),
            "unique_line_offers": len(offers),
            "unique_matches": len(matches),
            "unique_close_offers": len(close_offers),
            "complete_snapshots_by_league": dict(by_league),
            "unique_line_offers_by_league": {league: len(values) for league, values in sorted(offers_by_league.items())},
            "unique_matches_by_league": {league: len(values) for league, values in sorted(matches_by_league.items())},
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default="2026-03-01")
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--allow-missing-creds", action="store_true")
    parser.add_argument("--local-only", action="store_true")
    parser.add_argument("--no-local", action="store_true")
    args = parser.parse_args()
    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date)
    remote_rows: list[dict[str, Any]] = []
    if not args.local_only:
        try:
            remote_rows = fetch_rows(start_date, end_date)
            for row in remote_rows:
                row["_coverage_source"] = "supabase"
        except (RuntimeError, requests.RequestException) as exc:
            if not args.allow_missing_creds:
                raise
            print(f"WARNING: Supabase coverage unavailable; continuing with local captures: {exc}")
    local_rows = [] if args.no_local else load_local_rows(start_date, end_date)
    rows = merge_rows(remote_rows, local_rows)
    if not rows and args.allow_missing_creds:
        print("WARNING: no Pinnacle coverage rows available")
        return 0
    payload = summarise(rows, start_date, end_date)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}: {len(rows)} snapshots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
