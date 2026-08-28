"""
Run Pinnacle scraper then fair-odds pipeline in sequence.
Optionally runs strict policy reporting (base production mode by default)
with side-by-side base/overlay tracking plus shadow-lane appenders.

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

from signal_storage import STRICT_SIGNAL_PATHS


ROOT = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        return default
    return value if value > 0 else default


def run_cmd(
    cmd: list[str],
    label: str,
    fatal: bool = True,
    timeout_seconds: int | None = None,
    env_overrides: dict[str, str] | None = None,
) -> int:
    print(f"\n=== {label} ===\n")
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    try:
        r = subprocess.run(cmd, cwd=str(ROOT), env=env, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timeout_label = f" after {timeout_seconds}s" if timeout_seconds else ""
        msg = f"{label} timed out{timeout_label}."
        if fatal:
            print(f"\n{msg} Stopping.")
            sys.exit(124)
        print(f"\nWARNING: {msg} Continuing.")
        return 124

    if r.returncode != 0:
        msg = f"{label} failed (exit {r.returncode})."
        if fatal:
            print(f"\n{msg} Stopping.")
            sys.exit(r.returncode)
        print(f"\nWARNING: {msg} Continuing.")
    return r.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Daily odds pipeline: Pinnacle -> fair odds -> strict report + shadow profiles"
    )
    parser.add_argument("--skip-strict-report", action="store_true", help="Skip strict policy report step")
    parser.add_argument(
        "--skip-recent-activity",
        action="store_true",
        help="Skip the current-fixture form/fatigue refresh (manual diagnostics only)",
    )
    parser.add_argument("--strict-policy-mode", choices=("base", "overlay"), default=os.environ.get("STRICT_POLICY_PRODUCTION_MODE", "base"))
    parser.add_argument("--strict-report-date", default="", help="Optional UTC date YYYY-MM-DD passed to strict report")
    parser.add_argument("--strict-report-output", default=str(STRICT_SIGNAL_PATHS.live))
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
    step_timeout = _env_int("TENNIS_DAILY_ODDS_STEP_TIMEOUT_SECONDS", 900)
    os.environ.setdefault("STRICT_HARD_CALIBRATION_LIVE", "0")
    os.environ.setdefault("STRICT_HARD_CALIBRATION_PROFILES", "strict")

    if not args.skip_recent_activity:
        run_cmd(
            [sys.executable, str(ROOT / "scripts" / "oncourt-compute-recent-activity.py")],
            label="1/6 Recent activity (form/fatigue/rust inputs)",
            fatal=True,
            timeout_seconds=step_timeout,
        )
    else:
        print("\n=== 1/6 Recent activity skipped (--skip-recent-activity) ===")

    run_cmd(
        [sys.executable, str(ROOT / "scripts" / "pinnacle-scrape-odds.py"), "--active-leagues-only"],
        label="2/6 Pinnacle scraper (writes to bookmaker_odds_snapshot)",
        fatal=True,
        timeout_seconds=step_timeout,
    )

    run_cmd(
        [sys.executable, str(ROOT / "scripts" / "supplement-masters-qualifying.py")],
        label="2/6 Masters qualifying schedule coverage",
        fatal=True,
        timeout_seconds=min(step_timeout, 180),
    )

    run_cmd(
        [sys.executable, str(ROOT / "scripts" / "oncourt-compute-fair-odds.py"), "--skip-handicap-values"],
        label="3/6 Fair odds pipeline",
        fatal=True,
        timeout_seconds=step_timeout,
    )

    run_cmd(
        [sys.executable, str(ROOT / "scripts" / "compute-handicap-values.py")],
        label="4/6 Handicap values (spread edge)",
        fatal=False,
        timeout_seconds=step_timeout,
    )

    # Research-only anomaly capture. This never changes routing or stakes: it
    # freezes extreme ML gaps and the same player's real Pinnacle handicap so
    # nightly settlement can test the two hypotheses independently.
    run_cmd(
        [sys.executable, str(ROOT / "scripts" / "tennis-model-market-gap-audit.py")],
        label="4b/6 Extreme model/market gap audit (research only)",
        fatal=False,
        timeout_seconds=step_timeout,
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
            label=f"5a/6 Strict report (production mode: {args.strict_policy_mode}; compare: {args.strict_compare_overlay})",
            fatal=False,
            timeout_seconds=step_timeout,
        )

        spread_cmd = [
            sys.executable,
            str(ROOT / "scripts" / "strict-policy-report.py"),
            "--append",
            "--signal-profile",
            "spread_v1_shadow",
        ]
        if args.strict_report_date:
            spread_cmd.extend(["--date", args.strict_report_date])
        run_cmd(
            spread_cmd,
            label="5b/6 Spread v1 Shadow append",
            fatal=False,
            timeout_seconds=step_timeout,
            env_overrides={"SPREAD_V1_ENABLE_CORRECTION_ONLY": "1"},
        )

        # BO5 handicap maths is tracked separately from the BO3-calibrated
        # Spread v1 lane. It is raw, zero-stake evidence until its own real-
        # price sample passes the promotion gates.
        run_cmd(
            [
                sys.executable,
                str(ROOT / "scripts" / "compute-handicap-values.py"),
                "--bo5-only",
                "--allow-bo5",
                "--disable-calibration",
            ],
            label="5c/6 Grand Slam BO5 handicap values (research only)",
            fatal=False,
            timeout_seconds=step_timeout,
        )
        bo5_cmd = [
            sys.executable,
            str(ROOT / "scripts" / "strict-policy-report.py"),
            "--append",
            "--signal-profile",
            "slam_bo5",
        ]
        if args.strict_report_date:
            bo5_cmd.extend(["--date", args.strict_report_date])
        run_cmd(
            bo5_cmd,
            label="5d/6 Grand Slam BO5 handicap evidence append",
            fatal=False,
            timeout_seconds=step_timeout,
            env_overrides={"INTERNAL_RESEARCH_LANES": "1"},
        )

        cpi_speed_cmd = [
            sys.executable,
            str(ROOT / "scripts" / "strict-policy-report.py"),
            "--append",
            "--signal-profile",
            "cpi_speed_shadow",
        ]
        if args.strict_report_date:
            cpi_speed_cmd.extend(["--date", args.strict_report_date])
        run_cmd(
            cpi_speed_cmd,
            label="6a/6 CPI speed-regime Shadow append",
            fatal=False,
            timeout_seconds=step_timeout,
            env_overrides={"INTERNAL_RESEARCH_LANES": "1"},
        )

        run_cmd(
            [sys.executable, str(ROOT / "scripts" / "tennis-shadow-proof-report.py")],
            label="6b/6 Tennis lane proof report",
            fatal=False,
            timeout_seconds=step_timeout,
        )
    else:
        print("\n=== 5/6 Strict report skipped (--skip-strict-report) ===")
        print("=== 6/6 Shadow appenders skipped (--skip-strict-report) ===")

    print("\nDone. Pinnacle snapshot + daily_fair_odds updated.")
    if not args.skip_strict_report:
        print(f"Strict signals updated at {args.strict_report_output}.")
        if args.strict_compare_overlay:
            print(f"Overlay comparison rows updated at {args.strict_compare_output}.")
        print("Spread Shadow CSV appended.")
        print("CPI speed-regime Shadow CSV refreshed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
