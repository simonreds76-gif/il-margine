from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "evaluate_tennis_spread_math",
    SCRIPTS / "evaluate-tennis-spread-math.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class EvaluateTennisSpreadMathTests(unittest.TestCase):
    def test_slam_main_draw_detection(self) -> None:
        row = {"tour_name": "Wimbledon", "round_id": "4"}
        self.assertTrue(MODULE.is_bo5(row))
        row["round_id"] = "3"
        self.assertFalse(MODULE.is_bo5(row))

    def test_reverse_solve_matches_target(self) -> None:
        for best_of in ("bo3", "bo5"):
            p_a, p_b = MODULE.solve_point_probabilities(0.70, 0.64, best_of)
            implied = MODULE.match_win_probability(p_a, p_b, best_of)
            self.assertAlmostEqual(implied, 0.70, delta=0.001)

    def test_integer_push_is_not_assigned_to_p2(self) -> None:
        p_a, p_b = MODULE.solve_point_probabilities(0.65, 0.64, "bo3")
        corrected, push = MODULE.conditional_cover(
            MODULE.match_margin_pmf(p_a, p_b, "bo3"),
            -2.0,
        )
        old = MODULE.old_cover_probability(p_a, p_b, -2.0)
        self.assertGreater(push, 0.0)
        self.assertNotAlmostEqual(corrected, old, places=6)


if __name__ == "__main__":
    unittest.main()
