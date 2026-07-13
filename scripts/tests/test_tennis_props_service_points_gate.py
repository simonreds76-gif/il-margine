from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "backtest-tennis-props-service-points.py"
SPEC = importlib.util.spec_from_file_location("tennis_props_service_points_gate", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TennisPropsServicePointsGateTests(unittest.TestCase):
    def test_service_point_gate_rejects_a_worse_candidate(self) -> None:
        rows = [
            {
                "actual_service_points": "60",
                "expected_service_points": "61",
                "candidate_expected_service_points": "70",
            },
            {
                "actual_service_points": "80",
                "expected_service_points": "78",
                "candidate_expected_service_points": "95",
            },
        ]

        summary = MODULE.service_point_summary(rows)

        self.assertEqual(summary["n"], 2)
        self.assertAlmostEqual(summary["current_mae"], 1.5)
        self.assertAlmostEqual(summary["candidate_mae"], 12.5)
        self.assertFalse(summary["passed"])

    def test_service_point_gate_accepts_a_better_candidate(self) -> None:
        rows = [
            {
                "actual_service_points": "60",
                "expected_service_points": "68",
                "candidate_expected_service_points": "61",
            },
            {
                "actual_service_points": "80",
                "expected_service_points": "70",
                "candidate_expected_service_points": "78",
            },
        ]

        summary = MODULE.service_point_summary(rows)

        self.assertAlmostEqual(summary["current_mae"], 9.0)
        self.assertAlmostEqual(summary["candidate_mae"], 1.5)
        self.assertTrue(summary["passed"])


if __name__ == "__main__":
    unittest.main()
