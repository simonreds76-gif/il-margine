#!/usr/bin/env python3
"""
Run the current goalscorer workflow end to end.

This keeps the user-facing workflow small:
  1. refresh the historical model outputs
  2. optionally import any new ATGS odds CSVs from an inbox
  3. compare archived odds to the model

Example:
  python scripts/run-goalscorer-pipeline.py
  python scripts/run-goalscorer-pipeline.py --bookmaker bet365
  python scripts/run-goalscorer-pipeline.py --odds-input data/goalscorer/manual/*.csv --supabase
  python scripts/run-goalscorer-pipeline.py --fetch-odds-api --bookmaker Bet365
  python scripts/run-goalscorer-pipeline.py --fetch-pinnacle --bookmaker Pinnacle
  python scripts/run-goalscorer-pipeline.py --historical-backtest --selection target_before_kickoff --target-minutes-before 60
"""

from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_GLOB = "data/goalscorer/serie-a-player-match-logs-*.csv"
DEFAULT_ODDS_INPUT = "data/goalscorer/inbox/*.csv"
DEFAULT_PENALTY_HIERARCHY = "data/goalscorer/serie-a-penalty-takers.json"
DEFAULT_CONFIRMED_LINEUPS = "data/goalscorer/confirmed-lineups.json"
DEFAULT_SHADOW_SIGNALS = "data/goalscorer/goalscorer-shadow-signals.csv"
DEFAULT_SHADOW_SUMMARY = "data/goalscorer/goalscorer-shadow-performance.txt"

LEAGUE_CONFIGS = {
    "serie-a": {
        "label": "Serie A",
        "data_glob": DEFAULT_DATA_GLOB,
        "penalty_hierarchy": DEFAULT_PENALTY_HIERARCHY,
        "lineups": DEFAULT_CONFIRMED_LINEUPS,
        "player_log": "data/goalscorer/serie-a-player-match-logs-2025-2026.csv",
        "league_id": 55,
        "shadow_signals": DEFAULT_SHADOW_SIGNALS,
        "shadow_summary": DEFAULT_SHADOW_SUMMARY,
        "live_out_dir": "data/goalscorer",
    },
    "epl": {
        "label": "Premier League",
        "data_glob": "data/goalscorer/epl-player-match-logs-*.csv",
        "penalty_hierarchy": "data/goalscorer/epl-penalty-takers.json",
        "lineups": "data/goalscorer/epl-confirmed-lineups.json",
        "player_log": "data/goalscorer/epl-player-match-logs-2025-2026.csv",
        "league_id": 47,
        "shadow_signals": "data/goalscorer/epl-shadow-signals.csv",
        "shadow_summary": "data/goalscorer/epl-shadow-performance.txt",
        "live_out_dir": "data/goalscorer/epl",
    },
    "la-liga": {
        "label": "La Liga",
        "data_glob": "data/goalscorer/la-liga-player-match-logs-*.csv",
        "penalty_hierarchy": "data/goalscorer/la-liga-penalty-takers.json",
        "lineups": "data/goalscorer/la-liga-confirmed-lineups.json",
        "player_log": "data/goalscorer/la-liga-player-match-logs-2025-2026.csv",
        "league_id": 87,
        "shadow_signals": "data/goalscorer/la-liga-shadow-signals.csv",
        "shadow_summary": "data/goalscorer/la-liga-shadow-performance.txt",
        "live_out_dir": "data/goalscorer/la-liga",
    },
    "bundesliga": {
        "label": "Bundesliga",
        "data_glob": "data/goalscorer/bundesliga-player-match-logs-*.csv",
        "penalty_hierarchy": "data/goalscorer/bundesliga-penalty-takers.json",
        "lineups": "data/goalscorer/bundesliga-confirmed-lineups.json",
        "player_log": "data/goalscorer/bundesliga-player-match-logs-2025-2026.csv",
        "league_id": 54,
        "shadow_signals": "data/goalscorer/bundesliga-shadow-signals.csv",
        "shadow_summary": "data/goalscorer/bundesliga-shadow-performance.txt",
        "live_out_dir": "data/goalscorer/bundesliga",
    },
}


def _expand_paths(paths: Iterable[str]) -> List[str]:
    expanded: List[str] = []
    for path in paths:
        if "*" in path or "?" in path:
            expanded.extend(glob.glob(path))
        else:
            expanded.append(path)
    return [path for path in expanded if os.path.exists(path)]


def _run(cmd: List[str]) -> None:
    print("  >", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the goalscorer model + odds comparison pipeline")
    parser.add_argument("--league", choices=sorted(LEAGUE_CONFIGS), default="serie-a", help="League to run")
    parser.add_argument("--data", nargs="+", default=None, help="Historical player-log CSVs or globs")
    parser.add_argument(
        "--odds-input",
        nargs="+",
        default=[DEFAULT_ODDS_INPUT],
        help="Optional ATGS odds CSVs or globs to import before comparison",
    )
    parser.add_argument("--bookmaker", default="", help="Optional bookmaker filter for the comparison summary")
    parser.add_argument("--supabase", action="store_true", help="Upload imported odds rows to Supabase")
    parser.add_argument("--fetch-odds-api", action="store_true", help="Fetch live league ATGS prices from odds-api.io into the inbox first")
    parser.add_argument("--odds-api-bookmakers", default="Bet365,William Hill", help="Comma-separated bookmakers for odds-api.io")
    parser.add_argument("--fetch-pinnacle", action="store_true", help="Fetch live Pinnacle ATGS prices into the inbox first")
    parser.add_argument("--fetch-lineups", action="store_true", help="Fetch confirmed league lineups from FotMob before live compare")
    parser.add_argument("--historical-backtest", action="store_true", help="Run goalscorer-historical-backtest.py after compare")
    parser.add_argument("--live-only", action="store_true", help="Skip historical model/compare work and run only the live odds + lineup refresh path")
    parser.add_argument(
        "--selection",
        default="target_before_kickoff",
        choices=["target_before_kickoff", "closing", "opening", "all"],
        help="Historical backtest capture-selection strategy",
    )
    parser.add_argument("--target-minutes-before", type=int, default=60, help="Historical backtest target lead time")
    parser.add_argument("--skip-model", action="store_true", help="Skip goalscorer-model.py")
    parser.add_argument("--skip-odds-import", action="store_true", help="Skip goalscorer-odds-archive.py")
    parser.add_argument("--skip-compare", action="store_true", help="Skip goalscorer-compare-odds.py")
    parser.add_argument("--lineups", default="", help="Optional confirmed-lineup JSON for live penalty-transfer detection")
    parser.add_argument("--penalty-hierarchy", default="", help="Penalty taker hierarchy JSON")
    parser.add_argument("--track-shadow", action="store_true", help="Append/settle private stacked-signal shadow picks after live compare")
    parser.add_argument("--settle-shadow", action="store_true", help="Run shadow-settlement/summary only")
    parser.add_argument("--shadow-output", default="", help="Shadow signals CSV path")
    parser.add_argument("--shadow-summary", default="", help="Shadow performance summary TXT path")
    args = parser.parse_args()
    league_config = LEAGUE_CONFIGS[args.league]

    print("\n" + "=" * 64)
    print("  IL MARGINE - Goalscorer Pipeline")
    print("=" * 64)
    print(f"  League: {league_config['label']}")

    data_inputs = args.data or [league_config["data_glob"]]
    data_paths = _expand_paths(data_inputs)
    if not data_paths:
        raise SystemExit("No goalscorer data files found. Scrape Understat seasons first.")

    odds_paths = _expand_paths(args.odds_input)
    model_script = str(ROOT / "scripts" / "goalscorer-model.py")
    archive_script = str(ROOT / "scripts" / "goalscorer-odds-archive.py")
    compare_script = str(ROOT / "scripts" / "goalscorer-compare-odds.py")
    historical_backtest_script = str(ROOT / "scripts" / "goalscorer-historical-backtest.py")
    live_compare_script = str(ROOT / "scripts" / "goalscorer-live-compare.py")
    shadow_tracker_script = str(ROOT / "scripts" / "goalscorer-shadow-tracker.py")
    odds_api_script = str(ROOT / "scripts" / "odds-api-scrape-goalscorer.py")
    pinnacle_script = str(ROOT / "scripts" / "pinnacle-scrape-goalscorer.py")
    fotmob_lineups_script = str(ROOT / "scripts" / "fotmob-fetch-lineups.py")

    if not args.skip_model and not args.live_only:
        _run([sys.executable, model_script, "--data", *data_paths])

    if args.fetch_odds_api:
        _run(
            [
                sys.executable,
                odds_api_script,
                "--league",
                args.league,
                "--bookmakers",
                args.odds_api_bookmakers,
                "--out-dir",
                str(ROOT / "data" / "goalscorer" / "inbox"),
            ]
        )
        odds_paths = _expand_paths(args.odds_input)

    if args.fetch_pinnacle:
        _run([sys.executable, pinnacle_script, "--out-dir", str(ROOT / "data" / "goalscorer" / "inbox")])
        odds_paths = _expand_paths(args.odds_input)

    lineups_path = args.lineups
    if args.fetch_lineups:
        lineups_path = lineups_path or str(ROOT / league_config["lineups"])
        _run(
            [
                sys.executable,
                fotmob_lineups_script,
                "--league-id",
                str(league_config["league_id"]),
                "--player-log",
                str(ROOT / league_config["player_log"]),
                "--out",
                lineups_path,
            ]
        )

    if not args.skip_odds_import and odds_paths:
        cmd = [sys.executable, archive_script, "--input", *odds_paths]
        if args.supabase:
            cmd.append("--supabase")
        _run(cmd)
    elif not args.skip_odds_import:
        print("  No odds input files found. Skipping archive import.")

    archive_path = ROOT / "data" / "goalscorer" / "goalscorer-odds-history.csv"
    if not args.skip_compare:
        if archive_path.exists():
            if not args.live_only:
                cmd = [sys.executable, compare_script]
                if args.bookmaker:
                    cmd.extend(["--bookmaker", args.bookmaker])
                _run(cmd)
                if args.historical_backtest:
                    historical_cmd = [
                        sys.executable,
                        historical_backtest_script,
                        "--selection",
                        args.selection,
                        "--target-minutes-before",
                        str(args.target_minutes_before),
                    ]
                    if args.bookmaker:
                        historical_cmd.extend(["--bookmaker", args.bookmaker])
                    _run(historical_cmd)
            live_cmd = [sys.executable, live_compare_script]
            live_cmd.extend(["--league", args.league])
            if args.bookmaker:
                live_cmd.extend(["--bookmaker", args.bookmaker])
            live_cmd.extend(["--data", *data_paths])
            live_cmd.extend(["--out-dir", str(ROOT / league_config["live_out_dir"])])
            if lineups_path:
                live_cmd.extend(["--lineups", lineups_path])
            penalty_hierarchy = args.penalty_hierarchy or str(ROOT / league_config["penalty_hierarchy"])
            if penalty_hierarchy:
                live_cmd.extend(["--penalty-hierarchy", penalty_hierarchy])
            _run(live_cmd)

            if args.track_shadow or args.settle_shadow:
                shadow_output = args.shadow_output or league_config["shadow_signals"]
                shadow_summary = args.shadow_summary or league_config["shadow_summary"]
                shadow_cmd = [
                    sys.executable,
                    shadow_tracker_script,
                    "--output",
                    str(ROOT / shadow_output),
                    "--summary",
                    str(ROOT / shadow_summary),
                    "--odds-archive",
                    str(archive_path),
                ]
                if not args.settle_shadow:
                    shadow_cmd.extend(
                        [
                            "--live-compare",
                            str(ROOT / league_config["live_out_dir"] / "goalscorer-live-comparison.csv"),
                        ]
                    )
                else:
                    shadow_cmd.append("--settle-only")
                shadow_cmd.extend(["--data", *data_paths])
                _run(shadow_cmd)
        else:
            print("  No goalscorer odds archive found. Skipping comparison.")

    print("\n  Done.\n")


if __name__ == "__main__":
    main()
