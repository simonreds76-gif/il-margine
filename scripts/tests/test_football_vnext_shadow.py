from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("football_vnext_shadow", SCRIPTS / "publish-football-vnext-shadow.py")
assert SPEC is not None and SPEC.loader is not None
SHADOW = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SHADOW
SPEC.loader.exec_module(SHADOW)


class FootballVnextShadowTests(unittest.TestCase):
    def test_paired_rows_requires_both_sides_within_capture_skew(self) -> None:
        captured = datetime(2026, 8, 22, 12, tzinfo=UTC)
        base = {"league": "epl", "match": "A vs B", "line": "10.5"}
        rows = [
            {**base, "side": "over", "captured_at_dt": captured},
            {**base, "side": "under", "captured_at_dt": captured + timedelta(minutes=10)},
        ]
        paired = SHADOW.paired_rows(rows, ("league", "match", "line"))
        self.assertEqual(len(paired), 1)

        rows[1]["captured_at_dt"] = captured + timedelta(minutes=16)
        self.assertEqual(SHADOW.paired_rows(rows, ("league", "match", "line")), [])
        self.assertEqual(SHADOW.paired_rows(rows[:1], ("league", "match", "line")), [])

    def test_cap_signals_keeps_only_strongest_edge_per_fixture(self) -> None:
        rows = [
            {"pick_id": "a", "match_id": "fixture-1", "edge": 0.04, "book_odds": 1.90, "kickoff_utc": "2026-08-22T14:00:00Z", "match": "A vs B"},
            {"pick_id": "b", "match_id": "fixture-1", "edge": 0.08, "book_odds": 1.80, "kickoff_utc": "2026-08-22T14:00:00Z", "match": "A vs B"},
            {"pick_id": "c", "match_id": "fixture-2", "edge": 0.05, "book_odds": 1.95, "kickoff_utc": "2026-08-22T16:00:00Z", "match": "C vs D"},
        ]
        capped = SHADOW.cap_signals(rows)
        self.assertEqual([row["pick_id"] for row in capped], ["b", "c"])

    def test_candidate_row_marks_blocked_rows_as_guarded(self) -> None:
        source = {
            "kickoff": datetime(2026, 8, 22, 14, tzinfo=UTC),
            "captured_at_dt": datetime(2026, 8, 22, 10, tzinfo=UTC),
            "league_slug": "epl",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "line_label": "10.5",
            "odds": 1.95,
            "bookmaker": "Bet365",
        }
        row = SHADOW.candidate_row(
            model=SHADOW.TEAM_MODEL, source=source, team="Arsenal", side="over",
            probability=0.55, raw_probability=0.57, market_probability=0.51, edge=0.0725,
            matchday=2, team_neff=20, opponent_neff=20, model_mean=13.2,
            distribution_parameter=0.1,
            status="blocked", blocked_reason="matchdays_1_to_3",
        )
        self.assertEqual(row["current_model_would_have_priced"], "false")
        self.assertEqual(row["confidence_guard_applied"], "true")
        self.assertEqual(row["signal_status"], "blocked")
        self.assertEqual(row["model_mean"], 13.2)


if __name__ == "__main__":
    unittest.main()
