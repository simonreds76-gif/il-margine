from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "sot_definition_agreement",
    SCRIPTS / "sot-definition-agreement.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SotDefinitionAgreementTests(unittest.TestCase):
    def test_comparison_and_summary(self) -> None:
        reference = [
            {
                "date": "2026-05-24",
                "league": "epl",
                "home_team": "Manchester United",
                "away_team": "Arsenal",
                "home_sot": 5,
                "away_sot": 4,
            }
        ]
        key = MODULE.build_fixture_key("2026-05-24", "Manchester United", "Arsenal")
        independent = {
            key: {
                "home_sot": 5,
                "away_sot": 5,
                "match_id": 123,
            }
        }
        rows = MODULE.compare_rows(reference, independent)
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0]["exact_match"])
        self.assertTrue(rows[1]["within_one"])
        summary = MODULE.summarize(rows, 1)
        self.assertEqual(summary["matched_matches"], 1)
        self.assertEqual(summary["within_one_rate"], 1.0)
        self.assertFalse(summary["definition_pass"])

    def test_report_lists_material_discrepancies(self) -> None:
        rows = [
            {
                "date": "2026-05-24",
                "league": "epl",
                "home_team": "Sunderland",
                "away_team": "Chelsea",
                "team_side": "home",
                "football_data_sot": 2,
                "fotmob_sot": 6,
                "delta": 4,
                "absolute_delta": 4,
                "exact_match": False,
                "within_one": False,
                "fotmob_match_id": 123,
            }
        ]
        summary = MODULE.summarize(rows, 1)
        report = MODULE.render_report(summary, {"epl": summary}, rows)
        self.assertIn("Sunderland vs Chelsea", report)
        self.assertIn("| 2 | 6 | +4 |", report)


if __name__ == "__main__":
    unittest.main()
