#!/usr/bin/env python3
"""Refresh the tennis aces/double-fault research board.

This is intentionally local-first because the match schedule comes from the
OnCourt MDB export. If an odds-api.io key is available locally, the script also
captures Bet365 aces/DF lines and writes the comparison file.
"""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
from datetime import date, timedelta
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


def run(
    cmd: list[str],
    label: str,
    *,
    fatal: bool = True,
    timeout_seconds: int | None = None,
) -> int:
    print(f"\n=== {label} ===")
    try:
        result = subprocess.run(cmd, cwd=str(ROOT), timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        msg = f"{label} timed out after {timeout_seconds}s"
        if fatal:
            raise SystemExit(msg)
        print(f"WARNING: {msg}")
        return 124
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


def market_event_dates(path: Path) -> set[str]:
    if not has_market_rows(path):
        return set()
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return {
                str(row.get("date") or "").strip()
                for row in csv.DictReader(handle)
                if str(row.get("date") or "").strip()
            }
    except (OSError, csv.Error):
        return set()


def select_market_file(as_of: str, lookback_days: int = 3) -> Path | None:
    exact = lines_file(as_of)
    if has_market_rows(exact):
        return exact
    target = date.fromisoformat(as_of)
    for offset in range(1, max(0, lookback_days) + 1):
        candidate = lines_file((target - timedelta(days=offset)).isoformat())
        if has_market_rows(candidate) and any(day >= as_of for day in market_event_dates(candidate)):
            return candidate
    return None


def run_comparison(as_of: str, market_file: Path) -> bool:
    comparison = PROPS_DIR / f"comparison-{as_of}.csv"
    # A failed rebuild must not leave a same-date file that looks current.
    if comparison.exists():
        comparison.unlink()
    exit_code = run(
        [
            sys.executable,
            str(ROOT / "scripts" / "tennis-props-compare-bet365.py"),
            "--date",
            as_of,
            "--lines",
            str(market_file),
        ],
        "Compare Bet365 lines with projections",
        fatal=False,
    )
    return exit_code == 0 and has_market_rows(comparison)


def run_shadow_tracking(as_of: str) -> None:
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "tennis-props-build-price-history.py"),
        ],
        "Consolidate append-only Bet365 price history",
        fatal=False,
    )
    comparison = PROPS_DIR / f"comparison-{as_of}.csv"
    if has_market_rows(comparison):
        run(
            [
                sys.executable,
                str(ROOT / "scripts" / "tennis-props-market-observations.py"),
                "--comparison",
                str(comparison),
            ],
            "Update all-main-line Bet365 observation benchmark",
            fatal=False,
            timeout_seconds=300,
        )
        run(
            [
                sys.executable,
                str(ROOT / "scripts" / "tennis-props-shadow-tracker.py"),
                "--date",
                as_of,
                "--comparison",
                str(comparison),
                "--allow-medium",
            ],
            "Append tennis props shadow signals",
            fatal=False,
        )
    else:
        print(f"WARNING: exact-date comparison missing; shadow append skipped: {comparison}")
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


def write_pipeline_health(as_of: str, market_file: Path | None, *, strict: bool = False) -> int:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "tennis-props-pipeline-health.py"),
        "--date",
        as_of,
        "--lines",
        str(market_file or lines_file(as_of)),
        "--comparison",
        str(PROPS_DIR / f"comparison-{as_of}.csv"),
    ]
    if strict:
        cmd.append("--strict")
    return run(cmd, "Write tennis props pipeline health", fatal=False)


def sync_hosted_captures(as_of: str, lookback_days: int) -> None:
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "sync-tennis-props-hosted-captures.py"),
            "--as-of",
            as_of,
            "--lookback-days",
            str(lookback_days),
        ],
        "Sync hosted Bet365 tennis-props captures",
        fatal=False,
        timeout_seconds=120,
    )


def run_comparison_only(as_of: str, *, skip_sync: bool, lookback_days: int) -> int:
    if not skip_sync:
        sync_hosted_captures(as_of, lookback_days)
    market_file = select_market_file(as_of)
    if market_file is None:
        print(f"WARNING: no hosted/local Bet365 capture contains {as_of} events.")
        return write_pipeline_health(as_of, None)
    print(f"Using hosted/local Bet365 capture: {market_file}")
    if not run_comparison(as_of, market_file):
        return write_pipeline_health(as_of, market_file, strict=True)
    run_shadow_tracking(as_of)
    return write_pipeline_health(as_of, market_file, strict=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build tennis aces/DF projections and optional Bet365 comparison")
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=date.today().year)
    parser.add_argument("--refresh-sackmann", action="store_true", help="Download fresh ATP/WTA Sackmann CSVs first")
    parser.add_argument("--skip-odds", action="store_true", help="Do not scrape Bet365 lines even if a key is configured")
    parser.add_argument("--require-odds", action="store_true", help="Fail if the Bet365 odds scrape cannot run")
    parser.add_argument("--comparison-only", action="store_true", help="Sync hosted prices and refresh comparison/tracking without rebuilding projections")
    parser.add_argument("--skip-hosted-sync", action="store_true", help="Do not sync captures from the golden data branch")
    parser.add_argument("--hosted-lookback-days", type=int, default=7)
    parser.add_argument("--days-ahead", type=int, default=2)
    parser.add_argument("--max-events", type=int, default=64)
    args = parser.parse_args()

    load_env()
    PROPS_DIR.mkdir(parents=True, exist_ok=True)

    if args.comparison_only:
        return run_comparison_only(
            args.as_of,
            skip_sync=args.skip_hosted_sync,
            lookback_days=args.hosted_lookback_days,
        )

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

    if not args.skip_hosted_sync:
        sync_hosted_captures(args.as_of, args.hosted_lookback_days)

    if args.skip_odds:
        print("\nBet365 scrape skipped by --skip-odds.")
        market_file = select_market_file(args.as_of)
        if market_file:
            print(f"Using hosted/local Bet365 capture: {market_file}")
            run_comparison(args.as_of, market_file)
        run_shadow_tracking(args.as_of)
        return write_pipeline_health(args.as_of, market_file, strict=bool(market_file))
    if not has_odds_key():
        market_file = select_market_file(args.as_of)
        if market_file:
            print(f"\nLocal odds key missing; using hosted Bet365 capture: {market_file}")
            run_comparison(args.as_of, market_file)
            run_shadow_tracking(args.as_of)
            health_exit = write_pipeline_health(args.as_of, market_file, strict=True)
            if health_exit != 0:
                return health_exit
            return 0
        msg = "No local ODDS_API_KEY / ODDS_API_IO_KEY configured; projections refreshed, Bet365 scrape skipped."
        write_pipeline_health(args.as_of, None)
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
    market_file = select_market_file(args.as_of)
    if scrape_exit == 0:
        market_file = lines_file(args.as_of) if has_market_rows(lines_file(args.as_of)) else market_file
        if market_file:
            run_comparison(args.as_of, market_file)
    run_shadow_tracking(args.as_of)
    health_exit = write_pipeline_health(args.as_of, market_file, strict=bool(market_file))
    if health_exit != 0:
        return health_exit

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
