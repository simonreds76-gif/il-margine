from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("fouls_definition_agreement", SCRIPTS / "fouls-definition-agreement.py")
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FoulsDefinitionAgreementTests(unittest.TestCase):
    def test_no_overlap_is_explicit(self) -> None:
        result = MODULE.evaluate({})
        self.assertEqual(result["status"], "NO_OVERLAP")
        self.assertFalse(result["settlement_source_authorized"])

    def test_api_pass_still_requires_fotmob(self) -> None:
        result = MODULE.evaluate(
            {
                "matched_fixtures": 125,
                "fields": {
                    "fouls": {
                        "comparable_team_values": 250,
                        "exact_pct": 96.0,
                        "within_one_pct": 98.0,
                        "mae": 0.12,
                    }
                },
            }
        )
        self.assertEqual(result["status"], "WAIT_OR_FAIL")
        self.assertTrue(result["api_football"]["passed"])
        self.assertFalse(result["settlement_source_authorized"])

    def test_both_sources_must_pass(self) -> None:
        api = {
            "matched_fixtures": 125,
            "fields": {"fouls": {"comparable_team_values": 250, "within_one_pct": 98.0}},
        }
        fotmob = {
            "summary": {"comparable_team_values": 220, "within_one_pct": 97.5, "mae": 0.18}
        }
        result = MODULE.evaluate(api, fotmob)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["settlement_source_authorized"])


if __name__ == "__main__":
    unittest.main()
