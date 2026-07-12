from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "backtest-tennis-player-props-v2.py"
SPEC = importlib.util.spec_from_file_location("tennis_props_v2", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TennisPropsV2Tests(unittest.TestCase):
    def test_nb_distribution_is_normalized(self) -> None:
        total = sum(MODULE.nb_cdf(k, 8.0, 0.3) - MODULE.nb_cdf(k - 1, 8.0, 0.3) for k in range(100))
        self.assertAlmostEqual(total, 1.0, places=8)

    def test_shrinkage_stays_between_raw_and_parent(self) -> None:
        shrunk = MODULE.shrink_alpha(0.8, 0.2, 20, 30.0)
        self.assertGreater(shrunk, 0.2)
        self.assertLess(shrunk, 0.8)

    def test_rung_does_not_change_count_mean_or_mae(self) -> None:
        row = MODULE.CountRow("ATP", 2025, "Wimbledon", "123", "Player", "aces", 10, 8.0, 7.0)
        fitted = {
            "base": {("ATP", "aces"): 0.3},
            "tournament": {},
            "player": {},
        }
        summary = MODULE.summarise([row], fitted)
        self.assertEqual(summary["mae_current"], 2.0)
        self.assertEqual(summary["mae_v2"], 2.0)
        self.assertEqual(summary["mae_delta"], 0.0)


if __name__ == "__main__":
    unittest.main()
