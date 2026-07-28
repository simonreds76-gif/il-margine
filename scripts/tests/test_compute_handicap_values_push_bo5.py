from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "compute_handicap_values_push_bo5",
    SCRIPTS / "compute-handicap-values.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ComputeHandicapValuesTests(unittest.TestCase):
    def test_slam_main_draw_is_bo5_but_qualifying_is_not(self) -> None:
        meta = {"name": "Wimbledon"}
        self.assertFalse(MODULE._is_best_of_five_match(meta, 3))
        self.assertTrue(MODULE._is_best_of_five_match(meta, 4))
        self.assertTrue(MODULE._is_best_of_five_match(meta, 12))

    def test_non_slam_is_never_bo5(self) -> None:
        self.assertFalse(
            MODULE._is_best_of_five_match({"name": "ATP Masters Toronto"}, 12)
        )

    def test_missing_slam_round_is_identified_for_fail_closed_routing(self) -> None:
        meta = {"name": "US Open"}
        self.assertTrue(MODULE._is_grand_slam_event(meta))
        self.assertFalse(MODULE._is_best_of_five_match(meta, None))

    def test_integer_line_returns_two_way_prices_and_push(self) -> None:
        p1, p2, push = MODULE._shape_cover_probabilities(
            0.65,
            0.61,
            -2.0,
            "bo3",
        )
        self.assertAlmostEqual(p1 + p2, 1.0, places=10)
        self.assertGreater(push, 0.0)

    def test_half_line_has_no_push(self) -> None:
        p1, p2, push = MODULE._shape_cover_probabilities(
            0.65,
            0.61,
            -2.5,
            "bo3",
        )
        self.assertAlmostEqual(p1 + p2, 1.0, places=10)
        self.assertAlmostEqual(push, 0.0, places=12)

    def test_reverse_solver_supports_bo5(self) -> None:
        p_a, p_b = MODULE._solve_spw_for_match_prob(0.72, 0.64, "bo5")
        implied = MODULE.match_win_probability(p_a, p_b, "bo5")
        self.assertAlmostEqual(implied, 0.72, delta=0.001)


if __name__ == "__main__":
    unittest.main()
