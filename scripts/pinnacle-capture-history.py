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
import os
import sys
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
    resp = requests.post(url, headers=req_headers, json=rows, timeout=HTTP_TIMEOUT)
    if not resp.ok:
        raise RuntimeError(f"bookmaker_odds_history insert failed: {resp.status_code} {resp.text[:300]}")
    print(f"Appended {len(rows)} rows to bookmaker_odds_history.")


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
