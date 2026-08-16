from __future__ import annotations

import json
import runpy
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LAB = runpy.run_path(str(ROOT / "scripts" / "generate-fair-odds-lab.py"), run_name="fair_odds_lab_lifecycle_test")


class FairOddsLabLifecycleTests(unittest.TestCase):
    def test_completed_fotmob_fixture_is_removed_before_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "status.json"
            path.write_text(
                json.dumps(
                    {
                        "completed_fixtures": [
                            {
                                "league": "la-liga",
                                "match_date": "2026-08-16",
                                "home_team": "Espanyol",
                                "away_team": "Levante",
                                "finished": True,
                                "cancelled": False,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            completed = LAB["load_completed_fixture_keys"](path)

        rows, candidates = LAB["build_candidates_from_rows"](
            [
                {
                    "competition": "La Liga",
                    "match_date": "2026-08-16",
                    "kickoff": "2026-08-16T14:00:00Z",
                    "home_team": "Espanyol",
                    "away_team": "Levante",
                    "odds_decimal": "3.10",
                    "model_p_atgs": "0.42",
                }
            ],
            "2026-08-16",
            False,
            {},
            completed,
        )
        self.assertEqual(rows, [])
        self.assertEqual(candidates, [])

    def test_unfinished_status_does_not_hide_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "status.json"
            path.write_text(
                json.dumps(
                    {
                        "completed_fixtures": [
                            {
                                "league": "la-liga",
                                "match_date": "2026-08-16",
                                "home_team": "Espanyol",
                                "away_team": "Levante",
                                "finished": False,
                                "cancelled": False,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            completed = LAB["load_completed_fixture_keys"](path)
        self.assertEqual(completed, set())


if __name__ == "__main__":
    unittest.main()
