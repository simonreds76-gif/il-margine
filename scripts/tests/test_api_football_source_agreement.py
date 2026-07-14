from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "api_football_source_agreement",
    SCRIPTS / "api-football-source-agreement.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ApiFootballSourceAgreementTests(unittest.TestCase):
    def test_reports_exact_within_one_and_missing_coverage(self) -> None:
        api_rows = [
            {
                "date": "2026-08-15",
                "home_team": "Arsenal",
                "away_team": "Chelsea",
                "home_shots": "15",
                "away_shots": "8",
                "home_sot": "6",
                "away_sot": "",
                "home_corners": "7",
                "away_corners": "4",
            }
        ]
        reference_rows = [
            {
                "Date": "15/08/2026",
                "HomeTeam": "Arsenal",
                "AwayTeam": "Chelsea",
                "HS": "15",
                "AS": "9",
                "HST": "5",
                "AST": "3",
                "HC": "7",
                "AC": "4",
            }
        ]
        result = MODULE.build_agreement(api_rows, reference_rows)
        self.assertEqual(result["matched_fixtures"], 1)
        self.assertEqual(result["fields"]["shots"]["exact_pct"], 50.0)
        self.assertEqual(result["fields"]["shots"]["within_one_pct"], 100.0)
        self.assertEqual(result["fields"]["shots_on_target"]["coverage_pct"], 50.0)
        self.assertEqual(result["fields"]["corners"]["mae"], 0.0)

    def test_no_overlap_is_explicit(self) -> None:
        result = MODULE.build_agreement([], [])
        self.assertEqual(result["status"], "no_overlap")
        self.assertEqual(result["matched_fixtures"], 0)


if __name__ == "__main__":
    unittest.main()
