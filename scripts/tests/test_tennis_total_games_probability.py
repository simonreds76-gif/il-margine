from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from src.lib.tennis_prob import (
    _set_outcome_distribution,
    expected_total_games_from_pmf,
    fair_total_prices,
    match_games_pmf,
    over_push_under_from_pmf,
)


SCRIPT = Path(__file__).resolve().parents[1] / "oncourt-compute-fair-odds.py"
SPEC = importlib.util.spec_from_file_location("oncourt_compute_fair_odds_totals", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TennisTotalGamesProbabilityTests(unittest.TestCase):
    def test_pmf_support_and_mass_for_both_formats(self):
        bo3 = match_games_pmf(0.65, 0.62, best_of=3)
        bo5 = match_games_pmf(0.65, 0.62, best_of=5)

        self.assertAlmostEqual(sum(bo3.values()), 1.0, places=12)
        self.assertAlmostEqual(sum(bo5.values()), 1.0, places=12)
        self.assertEqual((min(bo3), max(bo3)), (12, 39))
        self.assertEqual((min(bo5), max(bo5)), (18, 65))
        self.assertGreater(expected_total_games_from_pmf(bo5), expected_total_games_from_pmf(bo3))

    def test_next_set_server_follows_completed_game_parity(self):
        outcomes = _set_outcome_distribution(0.65, 0.62, a_serves_first=True)

        for games, _a_won, next_a_serves in outcomes:
            self.assertEqual(next_a_serves, games % 2 == 0)

    def test_unknown_first_server_is_symmetric_between_players(self):
        original = match_games_pmf(0.68, 0.60, best_of=3)
        swapped = match_games_pmf(0.60, 0.68, best_of=3)

        for games in set(original) | set(swapped):
            self.assertAlmostEqual(original.get(games, 0.0), swapped.get(games, 0.0), places=12)

    def test_integer_line_push_is_refunded_in_fair_prices(self):
        pmf = match_games_pmf(0.65, 0.62, best_of=3)
        p_over, p_push, p_under = over_push_under_from_pmf(pmf, 22.0)
        fair_over, fair_under = fair_total_prices(p_over, p_push, p_under)

        self.assertGreater(p_push, 0.0)
        self.assertAlmostEqual(p_over + p_push + p_under, 1.0, places=12)
        self.assertAlmostEqual(1.0 / fair_over + 1.0 / fair_under, 1.0, places=12)

    def test_half_line_has_no_push(self):
        pmf = match_games_pmf(0.65, 0.62, best_of=3)
        p_over, p_push, p_under = over_push_under_from_pmf(pmf, 22.5)
        fair_over, fair_under = fair_total_prices(p_over, p_push, p_under)

        self.assertEqual(p_push, 0.0)
        self.assertAlmostEqual(fair_over, 1.0 / p_over, places=12)
        self.assertAlmostEqual(fair_under, 1.0 / p_under, places=12)

    def test_tournament_adjustment_changes_prices(self):
        pmf = match_games_pmf(0.65, 0.62, best_of=3)
        base = MODULE._build_ou_data(
            pmf,
            confidence="high",
            is_best_of_5=False,
            ou_shift=2.5,
            tournament_total_adjustment=0.0,
        )
        adjusted = MODULE._build_ou_data(
            pmf,
            confidence="high",
            is_best_of_5=False,
            ou_shift=2.5,
            tournament_total_adjustment=0.8,
        )

        self.assertNotEqual(base, adjusted)

    def test_bo5_totals_are_hidden(self):
        pmf = match_games_pmf(0.65, 0.62, best_of=5)
        self.assertEqual(
            MODULE._build_ou_data(
                pmf,
                confidence="high",
                is_best_of_5=True,
                ou_shift=2.5,
                tournament_total_adjustment=0.0,
            ),
            {},
        )

    def test_grand_slam_qualifying_remains_bo3(self):
        self.assertFalse(MODULE._is_best_of_five_match("Grand Slam", 3))
        self.assertTrue(MODULE._is_best_of_five_match("Grand Slam", 4))
        self.assertFalse(MODULE._is_best_of_five_match("ATP500", 8))


if __name__ == "__main__":
    unittest.main()
