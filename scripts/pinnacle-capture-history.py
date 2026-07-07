#!/usr/bin/env python3
"""
Append-only Pinnacle odds history capture.

Purpose:
- Keep the existing day-level `bookmaker_odds_snapshot` behavior unchanged.
- Also store every scrape run in `bookmaker_odds_history` so we can reconstruct
  late/close prices for CLV analysis.

Usage:
  python scripts/pinnacle-capture-history.py
  python scripts/pinnacle-capture-history.py --capture-mode close
  python scripts/pinnacle-capture-history.py --all-leagues
  python scripts/pinnacle-capture-history.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
from collections import Counter
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

# run_status helper bootstrap. The scheduler invokes this file directly,
# so we make the repo root importable before importing scripts._lib.
_RS_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RS_REPO_ROOT not in sys.path:
    sys.path.insert(0, _RS_REPO_ROOT)

from scripts._lib.run_status import run_status

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "pinnacle-history"
HTTP_TIMEOUT = 30
REST_INSERT_ATTEMPTS = max(1, int(os.environ.get("PINNACLE_HISTORY_REST_ATTEMPTS", "3")))
REST_RETRY_SECONDS = max(1.0, float(os.environ.get("PINNACLE_HISTORY_RETRY_SECONDS", "5")))
TRANSIENT_REST_STATUS = {408, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524}



def load_env() -> None:
    for name in [".env.local", "env.local"]:
        path = ROOT / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_pinnacle_module(all_leagues: bool, verbose: bool) -> Any:
    path = ROOT / "scripts" / "pinnacle-scrape-odds.py"
    module_name = "pinnacle_scrape_odds_mod"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    module.VERBOSE = verbose
    module.DRY_RUN = False
    module.INCLUDE_WTA = False
    module.PINNACLE_LEAGUES_ALL = all_leagues
    module.PINNACLE_LEAGUES_ACTIVE_ONLY = not all_leagues
    return module


def get_supabase_rest() -> tuple[str, dict[str, str]]:
    load_env()
    url = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        raise RuntimeError("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env.local")
    return f"{url}/rest/v1", {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }


def append_history_rows(rows: list[dict[str, Any]], dry_run: bool) -> None:
    if not rows:
        print("No history rows to append.")
        return
    if dry_run:
        print(f"Dry run: would append {len(rows)} rows to bookmaker_odds_history.")
        return
    base, headers = get_supabase_rest()
    url = f"{base}/bookmaker_odds_history"
    req_headers = {
        **headers,
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    strict_upload = os.environ.get("PINNACLE_HISTORY_STRICT_UPLOAD") == "1"
    captured_at = str(rows[0].get("captured_at") or "")
    last_error = "unknown error"

    for attempt in range(1, REST_INSERT_ATTEMPTS + 1):
        try:
            resp = requests.post(url, headers=req_headers, json=rows, timeout=HTTP_TIMEOUT)
            if not resp.ok and _unknown_schedule_column(resp.text):
                print("History table schedule columns unavailable; retrying without match_date/kickoff_iso.")
                rows = _strip_schedule_fields(rows)
                resp = requests.post(url, headers=req_headers, json=rows, timeout=HTTP_TIMEOUT)
            if resp.ok:
                print(f"Appended {len(rows)} rows to bookmaker_odds_history.")
                return

            last_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
            if resp.status_code not in TRANSIENT_REST_STATUS:
                raise RuntimeError(f"bookmaker_odds_history insert failed: {last_error}")
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"

        if captured_at and _history_rows_present(base, headers, captured_at):
            print("bookmaker_odds_history insert returned transient error, but captured_at is already present; treating as success.")
            return
        if attempt < REST_INSERT_ATTEMPTS:
            sleep_for = REST_RETRY_SECONDS * attempt
            print(f"bookmaker_odds_history insert transient failure ({last_error}); retrying in {sleep_for:.0f}s ({attempt}/{REST_INSERT_ATTEMPTS}).")
            time.sleep(sleep_for)

    message = f"bookmaker_odds_history insert skipped after {REST_INSERT_ATTEMPTS} attempts: {last_error}"
    if strict_upload:
        raise RuntimeError(message)
    print(f"WARNING: {message}")
    print("WARNING: local Pinnacle history CSV was written; GitHub workflow uploads it as a recovery artifact.")


def _history_rows_present(base: str, headers: dict[str, str], captured_at: str) -> bool:
    try:
        resp = requests.get(
            f"{base}/bookmaker_odds_history",
            headers=headers,
            params={"captured_at": f"eq.{captured_at}", "select": "captured_at", "limit": "1"},
            timeout=HTTP_TIMEOUT,
        )
        return resp.ok and bool(resp.json())
    except Exception:
        return False


def _strip_schedule_fields(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in row.items() if key not in {"match_date", "kickoff_iso"}}
        for row in rows
    ]


def _unknown_schedule_column(text: str) -> bool:
    lower = (text or "").lower()
    return ("match_date" in lower or "kickoff_iso" in lower) and (
        "schema cache" in lower
        or "could not find" in lower
        or "column" in lower
        or "pgrst204" in lower
    )


def save_local_csv(rows: list[dict[str, Any]], captured_at: datetime) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"pinnacle-history-{captured_at.strftime('%Y%m%d-%H%M%S')}.csv"
    fields = [
        "capture_date",
        "captured_at",
        "capture_mode",
        "bookmaker",
        "league",
        "league_name",
        "player1_name",
        "player2_name",
        "odds1",
        "odds2",
        "pinnacle_margin",
        "ou_line",
        "ou_over",
        "ou_under",
        "spread_line",
        "spread_odds1",
        "spread_odds2",
        "match_date",
        "kickoff_iso",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fields})
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Append one Pinnacle scrape run to bookmaker_odds_history.")
    parser.add_argument("--capture-mode", default="close", help="History capture tag, e.g. close, daily, intraday")
    parser.add_argument("--all-leagues", action="store_true", help="Use all=true league listing instead of active-only")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    mod = load_pinnacle_module(all_leagues=args.all_leagues, verbose=args.verbose)
    results = mod.scrape_pinnacle()
    if not results:
        print("No Pinnacle matches scraped.")
        return 0
    dated_count = sum(1 for row in results if row.get("match_date") and row.get("kickoff_iso"))
    league_counts = Counter(str(row.get("league") or "unknown") for row in results)
    spread_count = sum(1 for row in results if row.get("spread_line") is not None)
    total_count = sum(1 for row in results if row.get("ou_line") is not None)
    print(f"Schedule metadata: {dated_count}/{len(results)} rows dated.")
    print(f"Captured rows by league: {dict(league_counts)}")
    print(f"Market coverage: spreads={spread_count}/{len(results)} totals={total_count}/{len(results)}")
    if dated_count == 0:
        raise RuntimeError("Pinnacle scrape returned no match_date/kickoff_iso metadata; refusing undated history capture.")

    captured_at = datetime.now(timezone.utc)
    capture_date = captured_at.date().isoformat()
    history_rows = [
        {
            "capture_date": capture_date,
            "captured_at": captured_at.isoformat(),
            "capture_mode": args.capture_mode,
            "bookmaker": "Pinnacle",
            "league": row.get("league", "ATP"),
            "league_name": row.get("league_name"),
            "player1_name": row["player1_name"],
            "player2_name": row["player2_name"],
            "odds1": row["odds1"],
            "odds2": row["odds2"],
            "pinnacle_margin": row.get("pinnacle_margin"),
            "ou_line": row.get("ou_line"),
            "ou_over": row.get("ou_over"),
            "ou_under": row.get("ou_under"),
            "spread_line": row.get("spread_line"),
            "spread_odds1": row.get("spread_odds1"),
            "spread_odds2": row.get("spread_odds2"),
            "match_date": row.get("match_date"),
            "kickoff_iso": row.get("kickoff_iso"),
        }
        for row in results
    ]

    local_csv = save_local_csv(history_rows, captured_at)
    print(f"Local history CSV: {local_csv}")
    append_history_rows(history_rows, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    load_env()
    with run_status("pinnacle-capture-history", trigger_kind="schedule") as rs:
        exit_code = main()
    raise SystemExit(exit_code)
