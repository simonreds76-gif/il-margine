from __future__ import annotations

import json
import runpy
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LAB = runpy.run_path(str(ROOT / "scripts" / "generate-fair-odds-lab.py"), run_name="fair_odds_lab_lifecycle_test")


class FairOddsLabLifecycleTests(unittest.TestCase):
    def _candidate(self, *, model_probability: float, odds: float):
        model_prob_pct = model_probability * 100
        implied_pct = 100 / odds
        return LAB["Candidate"](
            row={
                "competition": "Spain - LaLiga",
                "match_date": "2026-08-22",
                "kickoff": "2026-08-22T19:30:00Z",
                "home_team": "Espanyol Barcelona",
                "away_team": "Real Madrid",
                "player_name": "Roberto Fernandez",
                "canonical_player_name": "Roberto Fernandez",
                "player_team": "Espanyol",
                "opponent": "Real Madrid",
                "lineup_state": "starter",
                "signal_confidence": "High",
                "position": "FW",
            },
            best_odds=odds,
            model_prob_pct=model_prob_pct,
            fair_odds=1 / model_probability,
            implied_pct=implied_pct,
            price_gap_pp=model_prob_pct - implied_pct,
            recent_npxg=None,
            team_xg=None,
            team_share=None,
            opponent_xga=None,
            fixture_swing=None,
            expected_minutes=78,
            team_form=None,
            opponent_form=None,
        )

    def _public_exclusion_reason(self, candidate) -> str:
        return LAB["public_quality_exclusion_reason"](
            candidate,
            min_model_prob_pct=20,
            max_market_odds=6,
            official_lineup_window_minutes=0,
            allow_projected_lineups=True,
        )

    def test_extreme_goalscorer_model_market_gap_is_not_public(self) -> None:
        candidate = self._candidate(model_probability=0.454690, odds=4.50)
        self.assertEqual(self._public_exclusion_reason(candidate), "model_market_gap_gt_10pp")

    def test_extreme_gap_is_written_to_separate_zero_stake_quarantine(self) -> None:
        candidate = self._candidate(model_probability=0.454690, odds=4.50)
        with tempfile.TemporaryDirectory() as temp_dir:
            added = LAB["append_quarantine_logs"](
                [(candidate, "model_market_gap_gt_10pp")],
                Path(temp_dir),
            )
            path = Path(temp_dir) / "fair-odds-lab-la-liga-quarantine.csv"
            rows, _fieldnames = LAB["read_exposure_log"](path)

        self.assertEqual(added, {"la-liga": 1})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["public_action"], "quarantine")
        self.assertEqual(rows[0]["tracking_tier"], "extreme_gap_quarantine")
        self.assertEqual(rows[0]["quarantine_reason"], "model_market_gap_gt_10pp")
        self.assertEqual(rows[0]["recommended_stake_units"], "0.00")
        self.assertEqual(rows[0]["evaluation_stake_units"], "1.00")
        self.assertEqual(rows[0]["recommended_stake_label"], "Zero-stake quarantine (1u evaluation)")

    def test_ten_point_gap_boundary_can_remain_public(self) -> None:
        candidate = self._candidate(model_probability=0.35, odds=4.00)
        self.assertEqual(candidate.price_gap_pp, 10.0)
        self.assertEqual(self._public_exclusion_reason(candidate), "")

    def test_relative_probability_guard_rejects_outlier_below_absolute_cap(self) -> None:
        candidate = self._candidate(model_probability=0.255, odds=6.00)
        self.assertLess(candidate.price_gap_pp, 10.0)
        self.assertEqual(
            self._public_exclusion_reason(candidate),
            "model_market_probability_ratio_gt_1_5x",
        )

    def test_completed_fotmob_fixture_is_removed_before_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "status.json"
            path.write_text(
                json.dumps(
                    {
                        "completed_fixtures": [
                            {
                                "league": "la-liga",
                                "match_date": "2026-08-16",
                                "home_team": "Espanyol",
                                "away_team": "Levante",
                                "finished": True,
                                "cancelled": False,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            completed = LAB["load_completed_fixture_keys"](path)

        rows, candidates = LAB["build_candidates_from_rows"](
            [
                {
                    "competition": "La Liga",
                    "match_date": "2026-08-16",
                    "kickoff": "2026-08-16T14:00:00Z",
                    "home_team": "Espanyol",
                    "away_team": "Levante",
                    "odds_decimal": "3.10",
                    "model_p_atgs": "0.42",
                }
            ],
            "2026-08-16",
            False,
            {},
            completed,
        )
        self.assertEqual(rows, [])
        self.assertEqual(candidates, [])

    def test_unfinished_status_does_not_hide_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "status.json"
            path.write_text(
                json.dumps(
                    {
                        "completed_fixtures": [
                            {
                                "league": "la-liga",
                                "match_date": "2026-08-16",
                                "home_team": "Espanyol",
                                "away_team": "Levante",
                                "finished": False,
                                "cancelled": False,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            completed = LAB["load_completed_fixture_keys"](path)
        self.assertEqual(completed, set())


if __name__ == "__main__":
    unittest.main()
