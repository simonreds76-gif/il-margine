from __future__ import annotations

import importlib.util
import sys
import unittest
from collections import defaultdict
from unittest.mock import patch
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

    def test_warmup_tracking_keeps_only_edge_qualified_rows_and_caps_fixture(self) -> None:
        rows = [
            {
                "pick_id": "weaker", "match_id": "fixture-1", "edge": 0.04,
                "book_odds": 1.90, "kickoff_utc": "2026-08-22T14:00:00Z",
                "match": "A vs B", "blocked_reason": "matchdays_1_to_3",
                "signal_status": "blocked", "current_model_would_have_priced": "false",
                "confidence_guard_applied": "true",
            },
            {
                "pick_id": "stronger", "match_id": "fixture-1", "edge": 0.08,
                "book_odds": 1.80, "kickoff_utc": "2026-08-22T14:00:00Z",
                "match": "A vs B", "blocked_reason": "matchdays_1_to_3",
                "signal_status": "blocked", "current_model_would_have_priced": "false",
                "confidence_guard_applied": "true",
            },
            {
                "pick_id": "low-edge", "match_id": "fixture-2", "edge": 0.01,
                "book_odds": 1.90, "kickoff_utc": "2026-08-22T16:00:00Z",
                "match": "C vs D", "blocked_reason": "matchdays_1_to_3;edge_below_3pct",
                "signal_status": "blocked", "current_model_would_have_priced": "false",
                "confidence_guard_applied": "true",
            },
        ]

        tracking = SHADOW.warmup_tracking_signals(rows)

        self.assertEqual([row["pick_id"] for row in tracking], ["stronger"])
        self.assertEqual(tracking[0]["signal_status"], "warmup_tracking")
        self.assertEqual(tracking[0]["current_model_would_have_priced"], "true")
        self.assertEqual(tracking[0]["confidence_guard_applied"], "false")
        self.assertEqual(tracking[0]["blocked_reason"], "")

    def test_existing_warmup_fixture_is_frozen(self) -> None:
        existing = [
            {
                "model": "corners_v3",
                "match_id": "fixture-1",
                "pick_id": "first",
                "signal_status": "warmup_tracking",
            }
        ]
        fresh = [
            {
                "model": "corners_v3",
                "match_id": "fixture-1",
                "pick_id": "later-higher-edge",
                "signal_status": "warmup_tracking",
            },
            {
                "model": "corners_v3",
                "match_id": "fixture-2",
                "pick_id": "new-fixture",
                "signal_status": "warmup_tracking",
            },
        ]

        unseen = SHADOW.unseen_warmup_signals(existing, fresh)

        self.assertEqual([row["pick_id"] for row in unseen], ["new-fixture"])

    def test_team_identity_must_match_the_fixture(self) -> None:
        self.assertTrue(SHADOW.is_fixture_team("Arsenal", "Arsenal", "Chelsea"))
        self.assertTrue(SHADOW.is_fixture_team("Chelsea", "Arsenal", "Chelsea"))
        self.assertFalse(SHADOW.is_fixture_team("", "Arsenal", "Chelsea"))
        self.assertFalse(SHADOW.is_fixture_team("Player Name", "Arsenal", "Chelsea"))

    def test_current_provider_team_names_resolve_to_historical_keys(self) -> None:
        self.assertEqual(SHADOW.PUB.team_key("Espanyol Barcelona"), "espanol")
        self.assertEqual(SHADOW.PUB.team_key("Espanyol"), "espanol")
        self.assertEqual(SHADOW.PUB.team_key("RC Deportivo De A Coruna"), "la coruna")
        self.assertEqual(SHADOW.PUB.team_key("Deportivo La Coruna"), "la coruna")
        self.assertEqual(SHADOW.PUB.team_key("Atletico Madrid"), "ath madrid")

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

    def test_corners_candidates_store_the_predicted_mean(self) -> None:
        captured = datetime(2026, 8, 15, 12, tzinfo=UTC)
        kickoff = datetime(2026, 8, 16, 14, tzinfo=UTC)
        base = {
            "league_slug": "epl", "home_team": "Arsenal", "away_team": "Chelsea",
            "line_label": "10.5", "captured_at_dt": captured, "kickoff": kickoff,
        }
        odds_rows = [
            {**base, "side": "over", "odds": 1.95},
            {**base, "side": "under", "odds": 1.95},
        ]
        states = defaultdict(SHADOW.EventState)
        form = {"ema20_matches": "20"}
        with (
            patch.object(SHADOW.PUB, "latest_corners_odds", return_value=odds_rows),
            patch.object(SHADOW.PUB, "live_form_row", return_value=form),
            patch.object(SHADOW, "latest_event_states", return_value=states),
            patch.object(SHADOW, "corners_features", return_value=(10.0, (0.0,) * 7)),
            patch.object(SHADOW, "predict_corners_mean", return_value=9.25),
        ):
            _accepted, candidates = SHADOW.score_corners(
                by_team={}, by_league={}, odds_rows=[], event_rows=[],
                params={"event_min_history": 0, "alpha": 0.1},
                lock={"selection_rules": {"minimum_edge": 0.03}}, now=captured,
            )
        self.assertEqual(len(candidates), 2)
        self.assertTrue(all(row["model_mean"] == 9.25 for row in candidates))



if __name__ == "__main__":
    unittest.main()
