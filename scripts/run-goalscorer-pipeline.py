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
import json
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, List


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_GLOB = "data/goalscorer/serie-a-player-match-logs-*.csv"
DEFAULT_ODDS_INPUT = "data/goalscorer/inbox/*.csv"
DEFAULT_PENALTY_HIERARCHY = "data/goalscorer/serie-a-penalty-takers.json"
DEFAULT_CONFIRMED_LINEUPS = "data/goalscorer/confirmed-lineups.json"
DEFAULT_SHADOW_SIGNALS = "data/goalscorer/goalscorer-shadow-signals.csv"
DEFAULT_SHADOW_SUMMARY = "data/goalscorer/goalscorer-shadow-performance.txt"
DEFAULT_PUBLIC_SIGNALS = "data/goalscorer/goalscorer-public-signals.csv"
DEFAULT_PUBLIC_SUMMARY = "data/goalscorer/goalscorer-public-performance.txt"

LEAGUE_CONFIGS = {
    "serie-a": {
        "label": "Serie A",
        "data_glob": DEFAULT_DATA_GLOB,
        "penalty_hierarchy": DEFAULT_PENALTY_HIERARCHY,
        "penalty_baseline_evidence": "data/goalscorer/penalty-baseline-evidence.json",
        "penalty_baseline_overrides": "data/goalscorer/penalty-baseline-overrides.json",
        "lineups": DEFAULT_CONFIRMED_LINEUPS,
        "league_id": 55,
        "shadow_signals": DEFAULT_SHADOW_SIGNALS,
        "shadow_summary": DEFAULT_SHADOW_SUMMARY,
        "public_signals": DEFAULT_PUBLIC_SIGNALS,
        "public_summary": DEFAULT_PUBLIC_SUMMARY,
        "live_out_dir": "data/goalscorer",
    },
    "epl": {
        "label": "Premier League",
        "data_glob": "data/goalscorer/epl-player-match-logs-*.csv",
        "penalty_hierarchy": "data/goalscorer/epl-penalty-takers.json",
        "penalty_baseline_evidence": "data/goalscorer/epl-penalty-baseline-evidence.json",
        "penalty_baseline_overrides": "data/goalscorer/epl-penalty-baseline-overrides.json",
        "lineups": "data/goalscorer/epl-confirmed-lineups.json",
        "league_id": 47,
        "shadow_signals": "data/goalscorer/epl-shadow-signals.csv",
        "shadow_summary": "data/goalscorer/epl-shadow-performance.txt",
        "public_signals": "data/goalscorer/epl-public-signals.csv",
        "public_summary": "data/goalscorer/epl-public-performance.txt",
        "live_out_dir": "data/goalscorer/epl",
    },
    "la-liga": {
        "label": "La Liga",
        "data_glob": "data/goalscorer/la-liga-player-match-logs-*.csv",
        "penalty_hierarchy": "data/goalscorer/la-liga-penalty-takers.json",
        "penalty_baseline_evidence": "data/goalscorer/la-liga-penalty-baseline-evidence.json",
        "penalty_baseline_overrides": "data/goalscorer/la-liga-penalty-baseline-overrides.json",
        "lineups": "data/goalscorer/la-liga-confirmed-lineups.json",
        "league_id": 87,
        "shadow_signals": "data/goalscorer/la-liga-shadow-signals.csv",
        "shadow_summary": "data/goalscorer/la-liga-shadow-performance.txt",
        "public_signals": "data/goalscorer/la-liga-public-signals.csv",
        "public_summary": "data/goalscorer/la-liga-public-performance.txt",
        "live_out_dir": "data/goalscorer/la-liga",
    },
    "bundesliga": {
        "label": "Bundesliga",
        "data_glob": "data/goalscorer/bundesliga-player-match-logs-*.csv",
        "penalty_hierarchy": "data/goalscorer/bundesliga-penalty-takers.json",
        "penalty_baseline_evidence": "data/goalscorer/bundesliga-penalty-baseline-evidence.json",
        "penalty_baseline_overrides": "data/goalscorer/bundesliga-penalty-baseline-overrides.json",
        "lineups": "data/goalscorer/bundesliga-confirmed-lineups.json",
        "league_id": 54,
        "shadow_signals": "data/goalscorer/bundesliga-shadow-signals.csv",
        "shadow_summary": "data/goalscorer/bundesliga-shadow-performance.txt",
        "public_signals": "data/goalscorer/bundesliga-public-signals.csv",
        "public_summary": "data/goalscorer/bundesliga-public-performance.txt",
        "live_out_dir": "data/goalscorer/bundesliga",
    },
    "ligue-1": {
        "label": "Ligue 1",
        "data_glob": "data/goalscorer/ligue-1-player-match-logs-*.csv",
        "penalty_hierarchy": "data/goalscorer/ligue-1-penalty-takers.json",
        "penalty_baseline_evidence": "data/goalscorer/ligue-1-penalty-baseline-evidence.json",
        "penalty_baseline_overrides": "data/goalscorer/ligue-1-penalty-baseline-overrides.json",
        "lineups": "data/goalscorer/ligue-1-confirmed-lineups.json",
        "league_id": 53,
        "shadow_signals": "data/goalscorer/ligue-1-shadow-signals.csv",
        "shadow_summary": "data/goalscorer/ligue-1-shadow-performance.txt",
        "public_signals": "data/goalscorer/ligue-1-public-signals.csv",
        "public_summary": "data/goalscorer/ligue-1-public-performance.txt",
        "live_out_dir": "data/goalscorer/ligue-1",
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


def _recent_capture_paths(patterns: Iterable[str], *, newer_than_ts: float) -> List[str]:
    candidates = _expand_paths(patterns)
    recent: List[str] = []
    for path in candidates:
        try:
            if os.path.getmtime(path) >= newer_than_ts:
                recent.append(path)
        except OSError:
            continue
    return sorted(recent)


def _current_season_label(today: date | None = None) -> str:
    today = today or datetime.now(timezone.utc).date()
    start_year = today.year if today.month >= 7 else today.year - 1
    return f"{start_year}-{start_year + 1}"


def _csv_has_data_rows(path: Path) -> bool:
    if not path.exists():
        return False
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        next(handle, None)
        return any(line.strip() for line in handle)


def preferred_player_log(league: str, *, today: date | None = None) -> Path:
    """Prefer the active season, falling back only while its feed is empty."""
    data_dir = ROOT / "data" / "goalscorer"
    current = data_dir / f"{league}-player-match-logs-{_current_season_label(today)}.csv"
    if _csv_has_data_rows(current):
        return current
    candidates = sorted(data_dir.glob(f"{league}-player-match-logs-*.csv"), reverse=True)
    return next((path for path in candidates if _csv_has_data_rows(path)), current)


def _run(cmd: List[str], allow_failure: bool = False) -> bool:
    print("  >", " ".join(cmd))
    result = subprocess.run(cmd, check=False, cwd=ROOT)
    if result.returncode == 0:
        return True
    if allow_failure:
        print(f"  WARNING: command failed with exit {result.returncode}; continuing.")
        return False
    raise subprocess.CalledProcessError(result.returncode, cmd)


def _write_merged_live_board() -> None:
    merged_rows = []
    leagues = []
    generated_at = ""

    for league_key, config in LEAGUE_CONFIGS.items():
        board_path = ROOT / config["live_out_dir"] / "live-board.json"
        if not board_path.exists():
            continue

        payload = json.loads(board_path.read_text(encoding="utf-8"))
        rows = payload.get("rows", [])
        if not isinstance(rows, list):
            rows = []
        merged_rows.extend(rows)

        league_generated_at = str(payload.get("generated_at") or "")
        if league_generated_at and league_generated_at > generated_at:
            generated_at = league_generated_at

        leagues.append(
            {
                "league": league_key,
                "label": config["label"],
                "path": str(board_path.relative_to(ROOT)).replace("\\", "/"),
                "row_count": len(rows),
                "generated_at": league_generated_at,
            }
        )

    output_path = ROOT / "data" / "goalscorer" / "all-leagues-live-board.json"
    payload = {
        "schema_version": 1,
        "generated_at": generated_at
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "league_count": len(leagues),
        "row_count": len(merged_rows),
        "leagues": leagues,
        "rows": merged_rows,
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  Saved: {output_path}")


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
    parser.add_argument("--odds-api-bookmakers", default="Bet365", help="Comma-separated bookmakers for odds-api.io")
    parser.add_argument(
        "--odds-api-max-http-requests",
        type=int,
        default=0,
        help="Hard per-league Odds-API HTTP request cap; 0 means unlimited.",
    )
    parser.add_argument(
        "--odds-api-days-ahead",
        type=int,
        default=3,
        help="Limit odds-api.io event discovery to this many days ahead",
    )
    parser.add_argument("--fetch-pinnacle", action="store_true", help="Fetch live Pinnacle ATGS prices into the inbox first")
    parser.add_argument("--fetch-lineups", action="store_true", help="Fetch FotMob expected/confirmed lineups before live compare")
    parser.add_argument("--lineup-days-ahead", type=int, default=3, help="Fetch FotMob lineups across this many days ahead")
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
    parser.add_argument("--penalty-baseline-evidence", default="", help="Penalty baseline evidence JSON")
    parser.add_argument("--penalty-baseline-overrides", default="", help="Manual penalty baseline overrides JSON")
    parser.add_argument("--track-shadow", action="store_true", help="Append/settle private stacked-signal shadow picks after live compare")
    parser.add_argument("--settle-shadow", action="store_true", help="Run shadow-settlement/summary only")
    parser.add_argument("--shadow-output", default="", help="Shadow signals CSV path")
    parser.add_argument("--shadow-summary", default="", help="Shadow performance summary TXT path")
    parser.add_argument("--upload-live-snapshot", action="store_true", help="Upload the current live goalscorer files snapshot to Supabase")
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
    settle_script = str(ROOT / "scripts" / "goalscorer-settle.py")
    live_snapshot_script = str(ROOT / "scripts" / "goalscorer-live-snapshot.py")
    odds_api_script = str(ROOT / "scripts" / "odds-api-scrape-goalscorer.py")
    pinnacle_script = str(ROOT / "scripts" / "pinnacle-scrape-goalscorer.py")
    fotmob_lineups_script = str(ROOT / "scripts" / "fotmob-fetch-lineups.py")
    validate_live_outputs_script = str(ROOT / "scripts" / "validate-goalscorer-live-outputs.py")

    if not args.skip_model and not args.live_only:
        _run([sys.executable, model_script, "--data", *data_paths])

    if args.fetch_odds_api:
        fetch_started_ts = datetime.now(timezone.utc).timestamp() - 1.0
        odds_fetch_ok = _run(
            [
                sys.executable,
                odds_api_script,
                "--league",
                args.league,
                "--bookmakers",
                args.odds_api_bookmakers,
                "--out-dir",
                str(ROOT / "data" / "goalscorer" / "inbox"),
                "--days-ahead",
                str(max(1, args.odds_api_days_ahead)),
                "--max-http-requests",
                str(max(0, args.odds_api_max_http_requests)),
            ],
            allow_failure=args.live_only,
        )
        if odds_fetch_ok:
            recent_patterns = [
                str(ROOT / "data" / "goalscorer" / "inbox" / f"odds-api-{args.league}-atgs-*.csv"),
                str(ROOT / "data" / "goalscorer" / "inbox" / "odds-api-atgs-*.csv"),
            ]
            recent_paths = _recent_capture_paths(recent_patterns, newer_than_ts=fetch_started_ts)
            odds_paths = recent_paths
            if not odds_paths:
                print("  No fresh Odds-API capture files were created. Skipping archive import for this fetch.")
        else:
            odds_paths = []

    if args.fetch_pinnacle:
        fetch_started_ts = datetime.now(timezone.utc).timestamp() - 1.0
        _run([sys.executable, pinnacle_script, "--out-dir", str(ROOT / "data" / "goalscorer" / "inbox")])
        recent_paths = _recent_capture_paths(
            [str(ROOT / "data" / "goalscorer" / "inbox" / "pinnacle-atgs-*.csv")],
            newer_than_ts=fetch_started_ts,
        )
        odds_paths = recent_paths
        if not odds_paths:
            print("  No fresh Pinnacle capture files were created. Skipping archive import for this fetch.")

    configured_lineups_path = str(ROOT / league_config["lineups"])
    lineups_path = args.lineups or (configured_lineups_path if os.path.exists(configured_lineups_path) else "")
    if args.fetch_lineups:
        lineups_path = lineups_path or configured_lineups_path
        _run(
            [
                sys.executable,
                fotmob_lineups_script,
                "--days-ahead",
                str(args.lineup_days_ahead),
                "--league-id",
                str(league_config["league_id"]),
                "--player-log",
                str(preferred_player_log(args.league)),
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
            penalty_baseline_evidence = args.penalty_baseline_evidence or str(ROOT / league_config["penalty_baseline_evidence"])
            if penalty_baseline_evidence:
                live_cmd.extend(["--penalty-baseline-evidence", penalty_baseline_evidence])
            penalty_baseline_overrides = args.penalty_baseline_overrides or str(ROOT / league_config["penalty_baseline_overrides"])
            if penalty_baseline_overrides:
                live_cmd.extend(["--penalty-baseline-overrides", penalty_baseline_overrides])
            _run(live_cmd)
            _write_merged_live_board()
            validate_cmd = [
                sys.executable,
                validate_live_outputs_script,
                "--league",
                args.league,
                "--live-board",
                str(ROOT / league_config["live_out_dir"] / "live-board.json"),
                "--merged-live-board",
                str(ROOT / "data" / "goalscorer" / "all-leagues-live-board.json"),
            ]
            if lineups_path:
                validate_cmd.extend(["--lineups", lineups_path])
            _run(validate_cmd)

            if args.track_shadow or args.settle_shadow:
                shadow_output = args.shadow_output or league_config["shadow_signals"]
                shadow_summary = args.shadow_summary or league_config["shadow_summary"]
                public_output = league_config.get("public_signals", DEFAULT_PUBLIC_SIGNALS)
                public_summary = league_config.get("public_summary", DEFAULT_PUBLIC_SUMMARY)
                if args.settle_shadow:
                    _run(
                        [
                            sys.executable,
                            settle_script,
                            "--league",
                            args.league,
                            "--signals",
                            str(ROOT / shadow_output),
                            "--summary",
                            str(ROOT / shadow_summary),
                        ]
                    )
                    _run(
                        [
                            sys.executable,
                            settle_script,
                            "--league",
                            args.league,
                            "--signals",
                            str(ROOT / public_output),
                            "--summary",
                            str(ROOT / public_summary),
                        ]
                    )
                else:
                    shadow_cmd = [
                        sys.executable,
                        shadow_tracker_script,
                        "--output",
                        str(ROOT / shadow_output),
                        "--summary",
                        str(ROOT / shadow_summary),
                        "--public-output",
                        str(ROOT / public_output),
                        "--public-summary",
                        str(ROOT / public_summary),
                        "--odds-archive",
                        str(archive_path),
                        "--append-only",
                        "--live-compare",
                        str(ROOT / league_config["live_out_dir"] / "goalscorer-live-comparison.csv"),
                    ]
                    shadow_cmd.extend(["--data", *data_paths])
                    _run(shadow_cmd)
        else:
            print("  No goalscorer odds archive found. Skipping comparison.")

    if args.upload_live_snapshot:
        _run([sys.executable, live_snapshot_script, "--supabase"])

    print("\n  Done.\n")


if __name__ == "__main__":
    main()
