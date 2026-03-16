"""
Run Pinnacle scraper then fair-odds pipeline in sequence.
Optionally runs strict policy reporting (base production mode by default)
with side-by-side base/overlay tracking.

Usage:
  python scripts/run-daily-odds.py
  python scripts/run-daily-odds.py --strict-policy-mode overlay
  python scripts/run-daily-odds.py --skip-strict-report
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def run_cmd(cmd: list[str], label: str, fatal: bool = True) -> int:
    print(f"\n=== {label} ===\n")
    r = subprocess.run(cmd, cwd=str(ROOT), env=os.environ.copy())
    if r.returncode != 0:
        msg = f"{label} failed (exit {r.returncode})."
        if fatal:
            print(f"\n{msg} Stopping.")
            sys.exit(r.returncode)
        print(f"\nWARNING: {msg} Continuing.")
    return r.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily odds pipeline: Pinnacle -> fair odds -> strict report")
    parser.add_argument("--skip-strict-report", action="store_true", help="Skip strict policy report step")
    parser.add_argument("--strict-policy-mode", choices=("base", "overlay"), default=os.environ.get("STRICT_POLICY_PRODUCTION_MODE", "base"))
    parser.add_argument("--strict-report-date", default="", help="Optional UTC date YYYY-MM-DD passed to strict report")
    parser.add_argument("--strict-report-output", default=str(ROOT / "data" / "backtest" / "strict-signals.csv"))
    parser.add_argument("--strict-compare-output", default=str(ROOT / "data" / "backtest" / "strict-signals-overlay-compare.csv"))

    parser.add_argument("--overlay-policy-file", default=str(ROOT / "data" / "backtest" / "tournament-segment-roi.csv"))
    parser.add_argument("--overlay-window", default=os.environ.get("STRICT_OVERLAY_WINDOW", "prior_editions"))
    parser.add_argument("--overlay-family", choices=("seed", "entry"), default=os.environ.get("STRICT_OVERLAY_FAMILY", "seed"))
    parser.add_argument("--overlay-min-n", type=int, default=int(os.environ.get("STRICT_OVERLAY_MIN_N", "50")))
    parser.add_argument("--overlay-min-roi-pct", type=float, default=float(os.environ.get("STRICT_OVERLAY_MIN_ROI_PCT", "-5")))
    parser.add_argument("--overlay-missing-mode", choices=("skip", "allow"), default=os.environ.get("STRICT_OVERLAY_MISSING_MODE", "skip"))

    parser.add_argument(
        "--strict-compare-overlay",
        dest="strict_compare_overlay",
        action="store_true",
        help="Write side-by-side base/overlay comparison rows",
    )
    parser.add_argument(
        "--no-strict-compare-overlay",
        dest="strict_compare_overlay",
        action="store_false",
        help="Disable side-by-side comparison rows",
    )
    parser.set_defaults(strict_compare_overlay=_env_bool("STRICT_POLICY_COMPARE_OVERLAY", True))
    args = parser.parse_args()

    run_cmd(
        [sys.executable, str(ROOT / "scripts" / "pinnacle-scrape-odds.py"), "--active-leagues-only"],
        label="1/4 Pinnacle scraper (writes to bookmaker_odds_snapshot)",
        fatal=True,
    )

    run_cmd(
        [sys.executable, str(ROOT / "scripts" / "oncourt-compute-fair-odds.py"), "--skip-handicap-values"],
        label="2/4 Fair odds pipeline",
        fatal=True,
    )

    run_cmd(
        [sys.executable, str(ROOT / "scripts" / "compute-handicap-values.py")],
        label="3/4 Handicap values (spread edge)",
        fatal=False,
    )

    if not args.skip_strict_report:
        strict_cmd = [
            sys.executable,
            str(ROOT / "scripts" / "strict-policy-report.py"),
            "--append",
            "--output",
            args.strict_report_output,
            "--policy-mode",
            args.strict_policy_mode,
            "--overlay-policy-file",
            args.overlay_policy_file,
            "--overlay-window",
            args.overlay_window,
            "--overlay-family",
            args.overlay_family,
            "--overlay-min-n",
            str(args.overlay_min_n),
            "--overlay-min-roi-pct",
            str(args.overlay_min_roi_pct),
            "--overlay-missing-mode",
            args.overlay_missing_mode,
        ]
        if args.strict_report_date:
            strict_cmd.extend(["--date", args.strict_report_date])
        if args.strict_compare_overlay:
            strict_cmd.extend(["--compare-overlay", "--compare-output", args.strict_compare_output])

        run_cmd(
            strict_cmd,
            label=f"4/4 Strict report (production mode: {args.strict_policy_mode}; compare: {args.strict_compare_overlay})",
            fatal=False,
        )
    else:
        print("\n=== 4/4 Strict report skipped (--skip-strict-report) ===")

    print("\nDone. Pinnacle snapshot + daily_fair_odds updated.")
    if not args.skip_strict_report:
        print(f"Strict signals updated at {args.strict_report_output}.")
        if args.strict_compare_overlay:
            print(f"Overlay comparison rows updated at {args.strict_compare_output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
