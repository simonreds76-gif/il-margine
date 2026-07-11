#!/usr/bin/env python3
"""Regression checks for the read-only Fair Odds Lab CLV monitor."""

from __future__ import annotations

import csv
import hashlib
import json
import runpy
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "goalscorer-clv-monitor.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    scraper = runpy.run_path(str(ROOT / "scripts" / "odds-api-scrape-goalscorer.py"))
    snapshot_kind_for = scraper["snapshot_kind_for"]
    assert snapshot_kind_for("2026-08-15T14:55:00Z", "2026-08-15T15:00:00Z") == "pre_kickoff_5"
    assert snapshot_kind_for("2026-08-15T14:30:00Z", "2026-08-15T15:00:00Z") == "pre_kickoff_30"
    assert snapshot_kind_for("2026-08-15T12:00:00Z", "2026-08-15T15:00:00Z") == "live_capture"

    schedule = runpy.run_path(str(ROOT / "scripts" / "goalscorer-live-schedule.py"))
    effective_tier = schedule["_effective_fixture_tier"]
    now = datetime(2026, 8, 15, 14, 30, tzinfo=timezone.utc)
    common = {
        "lineup_window_before_minutes": 70,
        "lineup_grace_after_minutes": 15,
        "close_window_before_minutes": 40,
        "include_distant": False,
        "include_confirmed": False,
    }
    assert effective_tier(now, now + timedelta(minutes=30), already_confirmed=True, tracked_signal=True, **common) == "close"
    assert effective_tier(now, now + timedelta(minutes=30), already_confirmed=True, tracked_signal=False, **common) is None
    assert effective_tier(now, now + timedelta(minutes=30), already_confirmed=False, tracked_signal=False, **common) == "lineup"
    assert effective_tier(now, now + timedelta(minutes=50), already_confirmed=True, tracked_signal=True, **common) is None

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        signals = temp / "fair-odds-lab-epl-signals.csv"
        odds = temp / "odds.csv"
        live_dir = temp / "live-history"
        live_dir.mkdir()
        output = temp / "clv.csv"
        report = temp / "clv.txt"

        signal_fields = [
            "date", "kickoff", "match", "player", "player_id", "market_player_name",
            "best_bookmaker", "best_bookmaker_odds", "compared_at", "home_team", "away_team", "model_p_atgs",
        ]
        write_csv(
            signals,
            signal_fields,
            [
                {
                    "date": "2026-08-15", "kickoff": "2026-08-15T15:00:00Z", "match": "Arsenal vs Chelsea",
                    "player": "Example Player", "player_id": "101", "market_player_name": "Example Player",
                    "best_bookmaker": "Bet365", "best_bookmaker_odds": "2.50", "compared_at": "2026-08-15T12:00:00Z",
                    "home_team": "Arsenal", "away_team": "Chelsea", "model_p_atgs": "0.45",
                },
                {
                    "date": "2026-08-16", "kickoff": "2026-08-16T15:00:00Z", "match": "Liverpool vs Everton",
                    "player": "Missing Player", "player_id": "202", "market_player_name": "Missing Player",
                    "best_bookmaker": "Bet365", "best_bookmaker_odds": "3.00", "compared_at": "2026-08-16T12:00:00Z",
                    "home_team": "Liverpool", "away_team": "Everton", "model_p_atgs": "0.38",
                },
            ],
        )
        odds_fields = [
            "captured_at", "match_date", "kickoff_at", "snapshot_kind", "bookmaker", "competition", "market",
            "home_team", "away_team", "player_name", "odds_decimal", "source",
        ]
        write_csv(
            odds,
            odds_fields,
            [
                {
                    "captured_at": "2026-08-15T14:40:00Z", "match_date": "2026-08-15",
                    "kickoff_at": "2026-08-15T15:00:00Z", "snapshot_kind": "pre_kickoff_30", "bookmaker": "Bet365",
                    "competition": "England - Premier League", "market": "ATGS", "home_team": "Arsenal FC",
                    "away_team": "Chelsea FC", "player_name": "Example Player", "odds_decimal": "2.20", "source": "test",
                },
                {
                    "captured_at": "2026-08-15T15:01:00Z", "match_date": "2026-08-15",
                    "kickoff_at": "2026-08-15T15:00:00Z", "snapshot_kind": "post_kickoff", "bookmaker": "Bet365",
                    "competition": "England - Premier League", "market": "ATGS", "home_team": "Arsenal",
                    "away_team": "Chelsea", "player_name": "Example Player", "odds_decimal": "2.00", "source": "test",
                },
            ],
        )
        live_payload = {
            "rows": [
                {
                    "captured_at": "2026-08-15T11:00:00Z", "match_date": "2026-08-15", "bookmaker": "Bet365",
                    "home_team": "Arsenal", "away_team": "Chelsea", "player_name": "Example Player",
                    "player_id": "101", "odds_decimal": 2.6,
                }
            ]
        }
        live_path = live_dir / "live-board-test.json"
        live_path.write_text(json.dumps(live_payload), encoding="utf-8")

        before = {path: digest(path) for path in (signals, odds, live_path)}
        subprocess.run(
            [
                sys.executable, str(SCRIPT), "--signals-glob", str(signals), "--odds-history", str(odds),
                "--live-history-glob", str(live_dir / "*.json"), "--output", str(output), "--report", str(report),
            ],
            check=True,
            cwd=ROOT,
        )
        after = {path: digest(path) for path in before}
        assert before == after, "CLV monitor changed an input file"

        rows = list(csv.DictReader(output.open(encoding="utf-8")))
        assert len(rows) == 2, rows
        matched = rows[0]
        assert matched["close_status"] == "true_close", matched
        assert matched["close_odds"] == "2.2000", matched
        assert matched["close_lag_minutes"] == "20.0", matched
        assert abs(float(matched["published_to_close_clv"]) - ((2.5 / 2.2) - 1.0)) < 1e-6, matched
        missing = rows[1]
        assert missing["close_status"] == "missing", missing
        assert missing["missing_reason"] == "no_capture_on_match_date", missing
        report_text = report.read_text(encoding="utf-8")
        assert "Matched closes/references: 1 (50.0%)" in report_text, report_text
        assert "This report does not alter Fair Odds Lab ledgers" in report_text, report_text

    print("GOALSCORER_CLV_MONITOR_OK")


if __name__ == "__main__":
    main()
