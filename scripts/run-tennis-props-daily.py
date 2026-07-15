#!/usr/bin/env python3
"""Refresh the tennis aces/double-fault research board.

This is intentionally local-first because the match schedule comes from the
OnCourt MDB export. If an odds-api.io key is available locally, the script also
captures Bet365 aces/DF lines and writes the comparison file.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROPS_DIR = ROOT / "data" / "tennis-props"


def load_env() -> None:
    for name in (".env.local", "env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            raw_line = raw_line.strip()
            if raw_line and not raw_line.startswith("#") and "=" in raw_line:
                key, value = raw_line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def run(cmd: list[str], label: str, *, fatal: bool = True) -> int:
    print(f"\n=== {label} ===")
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        msg = f"{label} failed with exit {result.returncode}"
        if fatal:
            raise SystemExit(msg)
        print(f"WARNING: {msg}")
    return result.returncode


def has_odds_key() -> bool:
    return bool(os.environ.get("ODDS_API_KEY") or os.environ.get("ODDS_API_IO_KEY"))


def lines_file(as_of: str) -> Path:
    return PROPS_DIR / "inbox" / f"bet365-lines-{as_of}.csv"


def has_market_rows(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        return sum(1 for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()) > 1
    except OSError:
        return False


def run_comparison(as_of: str) -> None:
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "tennis-props-compare-bet365.py"),
            "--date",
            as_of,
        ],
        "Compare Bet365 lines with projections",
        fatal=False,
    )


def run_shadow_tracking(as_of: str) -> None:
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "tennis-props-build-price-history.py"),
        ],
        "Consolidate append-only Bet365 price history",
        fatal=False,
    )
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "tennis-props-market-observations.py"),
            "--comparison",
            str(PROPS_DIR / f"comparison-{as_of}.csv"),
        ],
        "Update all-main-line Bet365 observation benchmark",
        fatal=False,
    )
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "tennis-props-shadow-tracker.py"),
            "--date",
            as_of,
        ],
        "Append tennis props shadow signals",
        fatal=False,
    )
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "tennis-props-settle-shadow.py"),
        ],
        "Settle tennis props shadow signals",
        fatal=False,
    )
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "tennis-props-model-report.py"),
        ],
        "Build tennis props model monitor report",
        fatal=False,
    )
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "tennis-derivatives-evidence-report.py"),
        ],
        "Refresh tennis derivative evidence gates",
        fatal=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build tennis aces/DF projections and optional Bet365 comparison")
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=date.today().year)
    parser.add_argument("--refresh-sackmann", action="store_true", help="Download fresh ATP/WTA Sackmann CSVs first")
    parser.add_argument("--skip-odds", action="store_true", help="Do not scrape Bet365 lines even if a key is configured")
    parser.add_argument("--require-odds", action="store_true", help="Fail if the Bet365 odds scrape cannot run")
    parser.add_argument("--days-ahead", type=int, default=2)
    parser.add_argument("--max-events", type=int, default=64)
    args = parser.parse_args()

    load_env()
    PROPS_DIR.mkdir(parents=True, exist_ok=True)

    if args.refresh_sackmann:
        run(
            [
                sys.executable,
                str(ROOT / "scripts" / "sackmann-refresh-data.py"),
                "--tour",
                "both",
                "--start-year",
                str(args.start_year),
                "--end-year",
                str(args.end_year),
            ],
            "Refresh Sackmann ATP/WTA snapshots",
            fatal=False,
        )

    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "sackmann-compute-slam-venue-factors.py"),
            "--start-year",
            str(args.start_year),
            "--end-year",
            str(max(args.start_year, args.end_year - 1)),
        ],
        "Compute tennis props venue factors",
        fatal=True,
    )
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "tennis-props-baseline.py"),
            "--as-of",
            args.as_of,
            "--start-year",
            str(args.start_year),
            "--end-year",
            str(args.end_year),
        ],
        "Build player aces/DF baselines",
        fatal=True,
    )
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "build-tennis-props-board.py"),
            "--as-of",
            args.as_of,
        ],
        "Build tennis props projection board",
        fatal=True,
    )

    if args.skip_odds:
        print("\nBet365 scrape skipped by --skip-odds.")
        if has_market_rows(lines_file(args.as_of)):
            print("Hosted/local Bet365 lines file exists; refreshing comparison.")
            run_comparison(args.as_of)
        run_shadow_tracking(args.as_of)
        return 0
    if not has_odds_key():
        if has_market_rows(lines_file(args.as_of)):
            print("\nLocal odds key missing, but today's hosted Bet365 lines file exists; refreshing comparison.")
            run_comparison(args.as_of)
            run_shadow_tracking(args.as_of)
            return 0
        msg = "No local ODDS_API_KEY / ODDS_API_IO_KEY configured; projections refreshed, Bet365 scrape skipped."
        if args.require_odds:
            raise SystemExit(msg)
        print(f"\nWARNING: {msg}")
        run_shadow_tracking(args.as_of)
        return 0

    scrape_exit = run(
        [
            sys.executable,
            str(ROOT / "scripts" / "tennis-props-scrape-bet365.py"),
            "--date",
            args.as_of,
            "--days-ahead",
            str(args.days_ahead),
            "--max-events",
            str(args.max_events),
            "--bookmakers",
            "Bet365",
        ],
        "Scrape Bet365 aces/DF lines",
        fatal=args.require_odds,
    )
    if scrape_exit == 0:
        run_comparison(args.as_of)
    run_shadow_tracking(args.as_of)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
