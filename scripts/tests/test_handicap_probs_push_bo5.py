from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from handicap_probs import (  # noqa: E402
    cover_probs,
    match_margin_pmf,
    match_win_probability,
    p_cover_conditional,
    prob_p1_covers_plus,
)


class HandicapProbabilityTests(unittest.TestCase):
    def test_bo3_and_bo5_pmfs_are_normalized(self) -> None:
        for best_of in ("bo3", "bo5"):
            pmf = match_margin_pmf(0.65, 0.61, best_of)
            self.assertAlmostEqual(sum(pmf.values()), 1.0, places=10)
            self.assertGreater(len(pmf), 10)

    def test_bo5_has_a_wider_margin_support_than_bo3(self) -> None:
        bo3 = match_margin_pmf(0.67, 0.60, "bo3")
        bo5 = match_margin_pmf(0.67, 0.60, "bo5")
        self.assertGreater(max(bo5), max(bo3))
        self.assertLess(min(bo5), min(bo3))

    def test_unknown_first_server_is_player_symmetric(self) -> None:
        forward = match_margin_pmf(0.67, 0.60, "bo3")
        reverse = match_margin_pmf(0.60, 0.67, "bo3")
        all_margins = set(forward) | {-margin for margin in reverse}
        for margin in all_margins:
            self.assertAlmostEqual(
                forward.get(margin, 0.0),
                reverse.get(-margin, 0.0),
                places=10,
            )

    def test_match_win_probability_is_normalized_and_symmetric(self) -> None:
        for best_of in ("bo3", "bo5"):
            p_a = match_win_probability(0.67, 0.60, best_of)
            p_b = match_win_probability(0.60, 0.67, best_of)
            self.assertGreater(p_a, 0.5)
            self.assertAlmostEqual(p_a + p_b, 1.0, places=10)

    def test_integer_line_preserves_push_mass(self) -> None:
        pmf = match_margin_pmf(0.65, 0.61, "bo3")
        p_win, p_push, p_loss = cover_probs(pmf, -2.0)
        self.assertGreater(p_push, 0.0)
        self.assertAlmostEqual(p_win + p_push + p_loss, 1.0, places=10)
        self.assertAlmostEqual(
            p_cover_conditional(pmf, -2.0),
            p_win / (p_win + p_loss),
            places=10,
        )

    def test_half_line_has_no_push(self) -> None:
        pmf = match_margin_pmf(0.65, 0.61, "bo3")
        p_win, p_push, p_loss = cover_probs(pmf, -2.5)
        self.assertAlmostEqual(p_push, 0.0, places=12)
        self.assertAlmostEqual(p_win + p_loss, 1.0, places=10)

    def test_compatibility_wrapper_is_push_conditional(self) -> None:
        pmf = match_margin_pmf(0.65, 0.61, "bo3")
        expected = p_cover_conditional(pmf, -2.0)
        self.assertAlmostEqual(
            prob_p1_covers_plus(0.65, 0.61, -2.0),
            expected,
            places=10,
        )

    def test_invalid_best_of_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            match_margin_pmf(0.65, 0.61, "bo7")


if __name__ == "__main__":
    unittest.main()
