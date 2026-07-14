from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("football_counts_vnext_gate", SCRIPTS / "football-counts-vnext-gate.py")
assert SPEC is not None and SPEC.loader is not None
GATE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = GATE
SPEC.loader.exec_module(GATE)


class FootballCountsVnextGateTests(unittest.TestCase):
    def test_team_gate_requires_both_folds_to_improve(self) -> None:
        passing = {
            "status": "OK",
            "hierarchical_mle_brier": "0.19",
            "fixed_alpha_025_brier": "0.20",
            "hierarchical_mle_log_loss": "0.56",
            "fixed_alpha_025_log_loss": "0.57",
        }
        report = "Count-distribution gate: **PASS**"
        self.assertTrue(GATE.team_count_gate([passing, passing], report))
        failing = {**passing, "hierarchical_mle_brier": "0.21"}
        self.assertFalse(GATE.team_count_gate([passing, failing], report))

    def test_corners_gate_requires_all_three_count_metrics(self) -> None:
        passing = {
            "status": "OK",
            "v3_mae": "2.70",
            "baseline_mae": "2.80",
            "v3_brier": "0.21",
            "baseline_brier": "0.22",
            "v3_log_loss": "0.61",
            "baseline_log_loss": "0.64",
        }
        report = "Count-model gate: **PASS**"
        self.assertTrue(GATE.corners_count_gate([passing, passing], report))
        failing = {**passing, "v3_log_loss": "0.65"}
        self.assertFalse(GATE.corners_count_gate([passing, failing], report))


if __name__ == "__main__":
    unittest.main()
