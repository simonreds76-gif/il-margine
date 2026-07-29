from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("tennis_most_aces", ROOT / "scripts" / "tennis_most_aces.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class MostAcesProbabilityTests(unittest.TestCase):
    def test_probabilities_sum_to_one_and_are_symmetric(self) -> None:
        p1, draw, p2 = MODULE.most_aces_probabilities(
            7.0, 7.0, alpha1=0.18, alpha2=0.18, simulations=4096
        )
        self.assertAlmostEqual(p1 + draw + p2, 1.0, places=10)
        self.assertAlmostEqual(p1, p2, delta=0.015)
        self.assertGreater(draw, 0.05)

    def test_stronger_ace_mean_is_favourite(self) -> None:
        p1, draw, p2 = MODULE.most_aces_probabilities(
            10.0, 4.0, alpha1=0.18, alpha2=0.18, simulations=4096
        )
        self.assertGreater(p1, p2)
        self.assertLess(MODULE.fair_odds(p1), MODULE.fair_odds(p2))
        self.assertGreater(draw, 0.0)

    def test_independence_control_is_symmetric(self) -> None:
        p1, draw, p2 = MODULE.independent_most_aces_probabilities(
            7.0, 7.0, alpha1=0.18, alpha2=0.18
        )
        self.assertAlmostEqual(p1, p2, delta=1e-8)
        self.assertAlmostEqual(p1 + draw + p2, 1.0, places=10)

    def test_three_way_devig(self) -> None:
        p1, draw, p2, overround = MODULE.devig_three_way((1.80, 7.00, 2.30))
        self.assertAlmostEqual(p1 + draw + p2, 1.0, places=12)
        self.assertGreater(overround, 1.0)

    def test_result_includes_draw(self) -> None:
        self.assertEqual(MODULE.result_from_counts(8, 8), "DRAW")
        self.assertEqual(MODULE.result_from_counts(9, 8), "P1")
        self.assertEqual(MODULE.result_from_counts(8, 9), "P2")


if __name__ == "__main__":
    unittest.main()
