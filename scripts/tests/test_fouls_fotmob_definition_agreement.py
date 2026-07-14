from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "fouls_fotmob_definition_agreement",
    SCRIPTS / "fouls-fotmob-definition-agreement.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FoulsFotMobAgreementTests(unittest.TestCase):
    def test_compare_and_summary(self) -> None:
        reference = [
            {
                "date": "2026-08-15",
                "league": "epl",
                "home_team": "Arsenal",
                "away_team": "Chelsea",
                "home_fouls": 10,
                "away_fouls": 13,
            }
        ]
        key = MODULE.build_fixture_key("2026-08-15", "Arsenal", "Chelsea")
        rows = MODULE.compare(reference, {key: {"home_fouls": 10, "away_fouls": 14, "match_id": 1}})
        summary = MODULE.summarize(rows, 1)
        self.assertEqual(summary["comparable_team_values"], 2)
        self.assertEqual(summary["exact_pct"], 50.0)
        self.assertEqual(summary["within_one_pct"], 100.0)
        self.assertEqual(summary["mae"], 0.5)


if __name__ == "__main__":
    unittest.main()
