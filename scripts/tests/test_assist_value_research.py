from __future__ import annotations

import runpy
import unittest
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODEL = runpy.run_path(str(ROOT / "scripts" / "build-assist-value-model.py"), run_name="assist_value_model_test")
RESEARCH = runpy.run_path(str(ROOT / "scripts" / "assist-value-research-gates.py"), run_name="assist_value_research_test")
TRACKER = runpy.run_path(str(ROOT / "scripts" / "assist-value-prospective-tracker.py"), run_name="assist_value_tracker_test")
BACKFILL = runpy.run_path(str(ROOT / "scripts" / "backfill-assist-match-results.py"), run_name="assist_value_backfill_test")


class AssistValueResearchTests(unittest.TestCase):
    def test_registered_team_alias_handles_cologne(self) -> None:
        self.assertEqual(RESEARCH["canonical_team"]("1. FC Koln"), "cologne")
        self.assertEqual(RESEARCH["canonical_team"]("FC Cologne"), "cologne")

    def test_median_five_minutes_replaces_mean_eight(self) -> None:
        base_date = datetime(2026, 1, 1)
        minutes = [10.0, 20.0, 30.0, 40.0, 90.0]
        history = [
            {
                "match_date": base_date + timedelta(days=index),
                "position": "AMC",
                "minutes": value,
                "assists": 0.0,
                "xa": 0.05,
            }
            for index, value in enumerate(minutes)
        ]
        features = MODEL["player_features"](history, base_date + timedelta(days=10))
        self.assertEqual(features["expected_minutes"], 30.0)

    def test_confirmed_lineup_minutes_are_gated(self) -> None:
        lineup_index = {
            ("2026-08-15", "arsenal", "chelsea"): {
                "lineup_type": "standard",
                "home_team": "Arsenal",
                "away_team": "Chelsea",
                "home_starters": [{"name": "Test Creator"}],
                "home_subs": ["Bench Player"],
                "home_unavailable": ["Injured Player"],
            }
        }
        base_row = {
            "match_date": "2026-08-15",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "player_name": "Test Creator",
        }
        self.assertEqual(MODEL["lineup_state"](base_row, "arsenal", lineup_index), "confirmed_starter")
        self.assertEqual(MODEL["lineup_minutes"](48.0, "confirmed_starter"), (60.0, "confirmed_starter_plus_median5"))

    def test_research_calibration_reduces_systematic_overestimate(self) -> None:
        probabilities = [0.20] * 100 + [0.40] * 100
        outcomes = [1] * 10 + [0] * 90 + [1] * 25 + [0] * 75
        a, b = RESEARCH["fit_platt"](probabilities, outcomes)
        calibrated = [RESEARCH["apply_platt"](p, a, b) for p in probabilities]
        raw = RESEARCH["probability_metrics"](probabilities, outcomes)
        fitted = RESEARCH["probability_metrics"](calibrated, outcomes)
        self.assertLess(fitted["brier"], raw["brier"])
        self.assertLess(fitted["mean_probability"], raw["mean_probability"])

    def test_prospective_tracker_requires_confirmed_v1_starter(self) -> None:
        row = {
            "model_version": "assist_research_v1",
            "signal_status": "shadow_signal",
            "lineup_state": "confirmed_starter",
            "market_odds": "4.50",
            "captured_at": "2026-08-15T13:00:00Z",
            "kickoff_at": "2026-08-15T14:00:00Z",
            "match_date": "2026-08-15",
            "league_key": "epl",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "player_name": "Test Creator",
            "bookmaker": "Bet365",
        }
        self.assertTrue(TRACKER["eligible"](row))
        row["lineup_state"] = "predicted_starter"
        self.assertFalse(TRACKER["eligible"](row))
        row["lineup_state"] = "confirmed_starter"
        row["market_odds"] = "suspended"
        self.assertFalse(TRACKER["eligible"](row))

    def test_prospective_tracker_is_append_only_per_player_fixture(self) -> None:
        base = {
            "model_version": "assist_research_v1",
            "signal_status": "shadow_signal",
            "lineup_state": "confirmed_starter",
            "market_odds": "4.50",
            "captured_at": "2026-08-15T13:00:00Z",
            "kickoff_at": "2026-08-15T14:00:00Z",
            "match_date": "2026-08-15",
            "league_key": "epl",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "player_name": "Test Creator",
            "bookmaker": "Bet365",
        }
        later = {**base, "captured_at": "2026-08-15T13:30:00Z", "market_odds": "4.20"}
        first, added = TRACKER["update_ledger"]([base, later], [], "2026-08-15T13:31:00Z")
        second, added_again = TRACKER["update_ledger"]([base, later], first, "2026-08-15T13:32:00Z")
        self.assertEqual(added, 1)
        self.assertEqual(first[0]["market_odds"], "4.20")
        self.assertEqual(added_again, 0)
        self.assertEqual(len(second), 1)

    def test_backfill_targets_only_legacy_results_by_default(self) -> None:
        self.assertTrue(BACKFILL["needs_refresh"]({"match_id": 1}))
        self.assertFalse(BACKFILL["needs_refresh"]({"match_id": 1, "assist_data_complete": False}))
        self.assertTrue(BACKFILL["needs_refresh"]({"match_id": 1, "assist_data_complete": False}, include_incomplete=True))

    def test_backfill_refuses_reused_or_mismatched_fotmob_id(self) -> None:
        identity_matches = BACKFILL["identity_matches"]
        old = {
            "match_date": "2026-03-21",
            "home_team": "Bayern München",
            "away_team": "Union Berlin",
        }
        same = {
            "match_date": "2026-03-21",
            "home_team": "Union Berlin",
            "away_team": "Bayern Munchen",
        }
        reused = {
            "match_date": "2026-09-18",
            "home_team": "Bayern München",
            "away_team": "Union Berlin",
        }
        wrong_teams = {
            "match_date": "2026-03-21",
            "home_team": "Bayern München",
            "away_team": "Mainz",
        }
        self.assertTrue(identity_matches(old, same))
        self.assertFalse(identity_matches(old, reused))
        self.assertFalse(identity_matches(old, wrong_teams))


if __name__ == "__main__":
    unittest.main()
