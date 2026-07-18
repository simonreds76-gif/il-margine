from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location("strict_policy_report_guard_test", SCRIPT_DIR / "strict-policy-report.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class StrictPolicyGuardParityTests(unittest.TestCase):
    def test_opposite_handicap_conflict_matches_api_orientation(self):
        self.assertTrue(MODULE.has_opposite_side_handicap_conflict("P1", 5.0, 20.0))
        self.assertTrue(MODULE.has_opposite_side_handicap_conflict("P2", 20.0, 5.0))
        self.assertFalse(MODULE.has_opposite_side_handicap_conflict("P1", 20.0, 19.99))
        self.assertFalse(MODULE.has_opposite_side_handicap_conflict("P2", None, 50.0))


if __name__ == "__main__":
    unittest.main()
