from __future__ import annotations

import importlib.util
import math
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
MODULE_PATH = SCRIPTS / "team-fouls-f2-folds.py"
SPEC = importlib.util.spec_from_file_location("team_fouls_f2_folds", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TeamFoulsF2Tests(unittest.TestCase):
    def test_registered_feature_set_is_deliberately_small(self) -> None:
        self.assertEqual(MODULE.FEATURE_NAMES, ("team_committed", "opponent_drawn", "opening_strength"))
        self.assertEqual(MODULE.FEATURE_INDICES, (0, 1, 4))

    def test_poisson_log_pmf_matches_closed_form(self) -> None:
        actual, mean = 11, 12.4
        expected = (actual * math.log(mean)) - mean - math.lgamma(actual + 1)
        self.assertAlmostEqual(MODULE.poisson_log_pmf(actual, mean), expected, places=12)

    def test_external_gates_never_authorize_signals(self) -> None:
        folds = []
        for season in MODULE.VALIDATION_SEASONS:
            folds.append(
                {
                    "season": season,
                    "status": "OK",
                    "causal_baseline_mae": 3.0,
                    "f2": {"mae": 2.7},
                    "opening_strength_transition": {"delta_nll": -0.002, "delta_mae": -0.01},
                    "poisson": {
                        "brier": 0.17,
                        "log_loss": 0.50,
                        "reliability": {"max_abs_gap": 0.01},
                    },
                    "baseline_probability": {"brier": 0.18, "log_loss": 0.52},
                    "f1_control": {"hierarchical_nb_brier": 0.171, "hierarchical_nb_log_loss": 0.501},
                }
            )
        decision = MODULE.apply_gates(folds)
        self.assertTrue(decision["count_gate_pass"])
        self.assertFalse(decision["market_gate_pass"])
        self.assertFalse(decision["settlement_gate_pass"])
        self.assertFalse(decision["signals_authorized"])


if __name__ == "__main__":
    unittest.main()
