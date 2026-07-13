from __future__ import annotations

import unittest

from src.lib.tennis_prob import (
    expected_match_service_points,
    expected_points_in_service_game,
    expected_tiebreak_service_points,
)


class TennisServicePointExpectationTests(unittest.TestCase):
    def test_even_service_game_has_known_expectation(self) -> None:
        self.assertAlmostEqual(expected_points_in_service_game(0.5), 6.75, places=10)

    def test_match_workload_is_symmetric_when_players_are_swapped(self) -> None:
        forward = expected_match_service_points(0.67, 0.61, best_of=3)
        reverse = expected_match_service_points(0.61, 0.67, best_of=3)
        self.assertAlmostEqual(forward.player_a_points, reverse.player_b_points, places=8)
        self.assertAlmostEqual(forward.player_b_points, reverse.player_a_points, places=8)
        self.assertAlmostEqual(forward.player_a_games, reverse.player_b_games, places=8)

    def test_best_of_five_requires_more_service_work_than_best_of_three(self) -> None:
        best_of_three = expected_match_service_points(0.66, 0.64, best_of=3)
        best_of_five = expected_match_service_points(0.66, 0.64, best_of=5)
        self.assertGreater(best_of_five.player_a_points, best_of_three.player_a_points)
        self.assertGreater(best_of_five.player_b_points, best_of_three.player_b_points)

    def test_even_tiebreak_splits_expected_service_points(self) -> None:
        served_a, served_b = expected_tiebreak_service_points(0.65, 0.65, True)
        reverse_a, reverse_b = expected_tiebreak_service_points(0.65, 0.65, False)
        self.assertAlmostEqual((served_a + reverse_a) / 2.0, (served_b + reverse_b) / 2.0, places=8)
        self.assertGreater(served_a + served_b, 7.0)


if __name__ == "__main__":
    unittest.main()
