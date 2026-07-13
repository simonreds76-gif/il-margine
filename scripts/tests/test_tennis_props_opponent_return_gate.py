from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "backtest-tennis-props-opponent-return.py"
SPEC = importlib.util.spec_from_file_location("tennis_props_opponent_return_gate", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TennisPropsOpponentReturnGateTests(unittest.TestCase):
    def test_zero_exponent_removes_opponent_adjustment(self) -> None:
        side = MODULE.SideInput(
            pre_opponent_rate=0.08,
            return_ratio=1.15,
            expected_service_points=100.0,
        )

        self.assertAlmostEqual(MODULE.candidate_side_mean(side, 0.0), 8.0)

    def test_positive_exponent_rewards_weaker_returner(self) -> None:
        side = MODULE.SideInput(
            pre_opponent_rate=0.08,
            return_ratio=1.15,
            expected_service_points=100.0,
        )

        self.assertGreater(
            MODULE.candidate_side_mean(side, MODULE.CURRENT_EXPONENT),
            MODULE.candidate_side_mean(side, 0.0),
        )

    def test_return_adjustment_is_clipped(self) -> None:
        side = MODULE.SideInput(
            pre_opponent_rate=0.08,
            return_ratio=10.0,
            expected_service_points=100.0,
        )

        self.assertAlmostEqual(MODULE.candidate_side_mean(side, 1.0), 9.76)

    def test_registered_grid_contains_current_exponent(self) -> None:
        self.assertIn(MODULE.CURRENT_EXPONENT, MODULE.EXPONENT_GRID)


if __name__ == "__main__":
    unittest.main()
