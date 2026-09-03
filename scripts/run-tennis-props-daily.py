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
MOST_ACES_DIRECT_BOARD = PROPS_DIR / "shadow" / "most-aces-direct-1x2-board.csv"
VENUE_ACE_V1_BOARD = PROPS_DIR / "shadow" / "venue-ace-factor-v1-projection-board.csv"


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


def betsbk_lines_file(as_of: str) -> Path:
    return PROPS_DIR / "inbox" / f"betsbk-lines-{as_of}.csv"


def combined_lines_file(as_of: str) -> Path:
    return PROPS_DIR / "inbox" / f"tennis-props-lines-{as_of}.csv"


def most_aces_lines_file(as_of: str) -> Path:
    return PROPS_DIR / "inbox" / f"betmgm-most-aces-1x2-{as_of}.csv"


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


def build_combined_market_file(as_of: str) -> Path | None:
    sources = [path for path in (lines_file(as_of), betsbk_lines_file(as_of)) if has_market_rows(path)]
    if not sources:
        return None
    rows: list[dict[str, str]] = []
    fields: list[str] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for path in sources:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for field in reader.fieldnames or []:
                if field not in fields:
                    fields.append(field)
            for raw_row in reader:
                row = {str(key): str(value or "") for key, value in raw_row.items() if key is not None}
                key = tuple(sorted(row.items()))
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
    if not rows or not fields:
        return None
    out = combined_lines_file(as_of)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(
        f"Combined tennis props prices: {len(rows)} rows from "
        f"{', '.join(path.name for path in sources)} -> {out.name}"
    )
    return out


def select_market_file(as_of: str, lookback_days: int = 3) -> Path | None:
    exact = build_combined_market_file(as_of)
    if exact is not None:
        return exact
    target = date.fromisoformat(as_of)
    for offset in range(1, max(0, lookback_days) + 1):
        candidate_date = (target - timedelta(days=offset)).isoformat()
        candidate = build_combined_market_file(candidate_date)
        if candidate is not None and any(day >= as_of for day in market_event_dates(candidate)):
            return candidate
    return None


def select_most_aces_file(as_of: str, lookback_days: int = 3) -> Path | None:
    exact = most_aces_lines_file(as_of)
    if has_market_rows(exact):
        return exact
    target = date.fromisoformat(as_of)
    for offset in range(1, max(0, lookback_days) + 1):
        candidate = most_aces_lines_file((target - timedelta(days=offset)).isoformat())
        if has_market_rows(candidate) and any(day >= as_of for day in market_event_dates(candidate)):
            return candidate
    return None


def refresh_derived_ace_boards(as_of: str) -> None:
    """Rebuild every ace board that depends on the main projection artifact."""
    run(
        [sys.executable, str(ROOT / "scripts" / "tennis-props-v3-live.py")],
        "Build v3 ATP ace prospective shadow board",
        fatal=False,
    )
    run(
        [sys.executable, str(ROOT / "scripts" / "build-tennis-most-aces-board.py")],
        "Build correlated Most Aces 1X2 fair board",
        fatal=False,
        timeout_seconds=180,
    )
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "tennis-most-aces-direct-live.py"),
            "--as-of",
            as_of,
        ],
        "Build direct Most Aces 1X2 prospective shadow board",
        fatal=False,
        timeout_seconds=180,
    )


def run_most_aces_shadow(as_of: str, capture: Path | None = None) -> None:
    forecast_cmd = [
        sys.executable,
        str(ROOT / "scripts" / "tennis-most-aces-forecast.py"),
    ]
    if has_market_rows(MOST_ACES_DIRECT_BOARD):
        forecast_cmd.extend(["--additional-board", str(MOST_ACES_DIRECT_BOARD)])
    run(
        forecast_cmd,
        "Register and score A0 plus Direct Most Aces 1X2 forecasts",
        fatal=False,
        timeout_seconds=240,
    )
    cmd = [sys.executable, str(ROOT / "scripts" / "tennis-most-aces-shadow.py")]
    if has_market_rows(MOST_ACES_DIRECT_BOARD):
        cmd.extend(["--additional-board", str(MOST_ACES_DIRECT_BOARD)])
    selected = capture or select_most_aces_file(as_of)
    if selected and has_market_rows(selected):
        cmd.extend(["--capture", str(selected)])
    run(cmd, "Update BetMGM Most Aces 1X2 shadow evidence", fatal=False)


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
    v3_board = PROPS_DIR / "shadow" / "aces-v3-projection-board.csv"
    if has_market_rows(v3_board):
        run(
            [
                sys.executable,
                str(ROOT / "scripts" / "tennis-props-compare-bet365.py"),
                "--date", as_of,
                "--lines", str(market_file),
                "--board", str(v3_board),
                "--out", str(PROPS_DIR / f"comparison-v3-aces-{as_of}.csv"),
                "--unmatched-out", str(PROPS_DIR / f"comparison-v3-aces-{as_of}-unmatched.csv"),
                "--market-filter", "aces,ace,player_aces,match_aces",
            ],
            "Compare v3 ATP ace shadow projections with Bet365",
            fatal=False,
        )
    if has_market_rows(VENUE_ACE_V1_BOARD):
        run(
            [
                sys.executable,
                str(ROOT / "scripts" / "tennis-props-compare-bet365.py"),
                "--date", as_of,
                "--lines", str(market_file),
                "--board", str(VENUE_ACE_V1_BOARD),
                "--out", str(PROPS_DIR / f"comparison-venue-ace-v1-{as_of}.csv"),
                "--unmatched-out", str(PROPS_DIR / f"comparison-venue-ace-v1-{as_of}-unmatched.csv"),
                "--market-filter", "aces,ace,player_aces,match_aces",
            ],
            "Compare venue ace factor v1 shadow projections with Bet365",
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
    run_most_aces_shadow(as_of)
    v3_comparison = PROPS_DIR / f"comparison-v3-aces-{as_of}.csv"
    if has_market_rows(v3_comparison):
        run(
            [
                sys.executable,
                str(ROOT / "scripts" / "tennis-props-shadow-tracker.py"),
                "--date", as_of,
                "--comparison", str(v3_comparison),
                "--signals", str(PROPS_DIR / "shadow" / "aces-v3-shadow-signals.csv"),
                "--performance", str(PROPS_DIR / "shadow" / "aces-v3-shadow-performance.txt"),
                "--allow-medium", "--allow-notes", "--allow-watch",
            ],
            "Append v3 ATP ace prospective shadow signals",
            fatal=True,
        )
        run(
            [
                sys.executable,
                str(ROOT / "scripts" / "tennis-props-settle-shadow.py"),
                "--signals", str(PROPS_DIR / "shadow" / "aces-v3-shadow-signals.csv"),
                "--performance", str(PROPS_DIR / "shadow" / "aces-v3-shadow-performance.txt"),
            ],
            "Settle v3 ATP ace prospective shadow signals",
            fatal=True,
        )
    venue_comparison = PROPS_DIR / f"comparison-venue-ace-v1-{as_of}.csv"
    if has_market_rows(venue_comparison):
        venue_signals = PROPS_DIR / "shadow" / "venue-ace-factor-v1-observations.csv"
        venue_performance = PROPS_DIR / "shadow" / "venue-ace-factor-v1-performance.txt"
        run(
            [
                sys.executable,
                str(ROOT / "scripts" / "tennis-venue-ace-factor-v1-observations.py"),
                "--date", as_of,
                "--comparison", str(venue_comparison),
                "--observations", str(venue_signals),
            ],
            "Append paired venue ace factor v1 control/candidate observations",
            fatal=False,
        )
        run(
            [
                sys.executable,
                str(ROOT / "scripts" / "tennis-props-settle-shadow.py"),
                "--signals", str(venue_signals),
                "--performance", str(venue_performance),
            ],
            "Settle venue ace factor v1 prospective shadow observations",
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
            str(ROOT / "scripts" / "tennis-venue-ace-factor-v1-report.py"),
        ],
        "Build venue ace factor v1 shadow gate report",
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
    # Optional v4 research must never delay the core append/settle/report path.
    v4_cmd = [
        sys.executable,
        str(ROOT / "scripts" / "tennis-props-aces-over-v4.py"),
    ]
    if has_market_rows(v3_comparison):
        v4_cmd.extend(["--comparison", str(v3_comparison)])
    run(
        v4_cmd,
        "Register and score ATP ace-over v4 challenger",
        fatal=False,
        timeout_seconds=180,
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


def capture_market_prices(args: argparse.Namespace) -> int:
    """Capture prices before the slow projection build can hit its timeout."""
    if args.skip_odds:
        print("\nMarket capture skipped by --skip-odds.")
        return 0
    source_exits: list[int] = []
    if has_odds_key():
        source_exits.append(
            run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "tennis-props-scrape-bet365.py"),
                    "--date", args.as_of,
                    "--days-ahead", str(args.days_ahead),
                    "--max-events", str(args.max_events),
                    "--bookmakers", "Bet365",
                ],
                "Capture Bet365 tennis count lines before projections",
                fatal=False,
                timeout_seconds=180,
            )
        )
        run(
            [
                sys.executable,
                str(ROOT / "scripts" / "tennis-most-aces-capture.py"),
                "--date", args.as_of,
                "--days-ahead", str(args.days_ahead),
                "--max-events", str(args.max_events),
                "--bookmakers", "BetMGM",
            ],
            "Capture BetMGM Most Aces 1X2 before projections",
            fatal=False,
            timeout_seconds=180,
        )
    else:
        print("\nWARNING: no local odds-api key; Bet365/BetMGM capture skipped.")

    if os.name == "nt" and not args.skip_bet365_direct:
        source_exits.append(
            run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "tennis-props-scrape-bet365-direct.py"),
                    "--date", args.as_of,
                    "--max-events", str(min(args.max_events, 40)),
                ],
                "Capture direct Bet365 service-break totals",
                fatal=False,
                timeout_seconds=480,
            )
        )

    if not args.skip_betsbk:
        source_exits.append(
            run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "tennis-props-scrape-betsbk.py"),
                    "--date", args.as_of,
                    "--days-ahead", str(args.days_ahead),
                    "--max-events", str(args.max_events),
                ],
                "Capture BetsBK US Open aces/DF fallback",
                fatal=False,
                timeout_seconds=900,
            )
        )
    if args.require_odds and build_combined_market_file(args.as_of) is None:
        raise SystemExit("No supported tennis props prices were captured from Bet365 or BetsBK.")
    return 0 if any(exit_code == 0 for exit_code in source_exits) else (source_exits[0] if source_exits else 0)


def run_comparison_only(
    as_of: str,
    *,
    skip_sync: bool,
    lookback_days: int,
    skip_derived_boards: bool = False,
) -> int:
    if not skip_sync:
        sync_hosted_captures(as_of, lookback_days)
    market_file = select_market_file(as_of)
    if market_file is None:
        print(f"WARNING: no hosted/local Bet365 capture contains {as_of} events.")
        return write_pipeline_health(as_of, None)
    if not skip_derived_boards:
        refresh_derived_ace_boards(as_of)
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
    parser.add_argument("--skip-betsbk", action="store_true", help="Skip the local public BetsBK US Open props fallback")
    parser.add_argument("--skip-bet365-direct", action="store_true", help="Skip the Windows-local direct Bet365 service-break fallback")
    parser.add_argument("--require-odds", action="store_true", help="Fail if the Bet365 odds scrape cannot run")
    parser.add_argument("--comparison-only", action="store_true", help="Sync hosted prices and refresh comparison/tracking without rebuilding projections")
    parser.add_argument("--skip-derived-boards", action="store_true", help="Skip slow derived ace boards during a fast comparison pass")
    parser.add_argument("--capture-only", action="store_true", help="Capture bookmaker tennis count prices without rebuilding projections")
    parser.add_argument("--skip-hosted-sync", action="store_true", help="Do not sync captures from the golden data branch")
    parser.add_argument("--hosted-lookback-days", type=int, default=7)
    parser.add_argument("--days-ahead", type=int, default=3)
    parser.add_argument("--max-events", type=int, default=128)
    args = parser.parse_args()

    load_env()
    PROPS_DIR.mkdir(parents=True, exist_ok=True)

    if args.capture_only:
        return capture_market_prices(args)

    if args.comparison_only:
        return run_comparison_only(
            args.as_of,
            skip_sync=args.skip_hosted_sync,
            lookback_days=args.hosted_lookback_days,
            skip_derived_boards=args.skip_derived_boards,
        )

    # Capture first. The projection board can take several minutes and is
    # deliberately timeout-bounded by the scheduled task; prices must not be
    # lost merely because that independent research build runs long.
    early_scrape_exit = capture_market_prices(args)

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
            str(ROOT / "scripts" / "tennis-props-activity.py"),
            "--as-of",
            args.as_of,
            "--start-year",
            str(args.start_year),
            "--end-year",
            str(args.end_year),
        ],
        "Build coverage-inclusive tennis props activity",
        fatal=True,
    )
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "build-tennis-props-board.py"),
            "--as-of",
            args.as_of,
            "--days-ahead",
            str(args.days_ahead),
        ],
        "Build tennis props projection board",
        fatal=True,
    )
    refresh_derived_ace_boards(args.as_of)

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

    scrape_exit = early_scrape_exit
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
