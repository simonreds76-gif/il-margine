from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
MODULE_PATH = SCRIPTS / "team-shots-scrape-odds.py"
SPEC = importlib.util.spec_from_file_location("team_shots_scrape_odds", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TeamShotsMarketFilterTests(unittest.TestCase):
    def test_rejects_player_shots_market(self):
        self.assertFalse(MODULE._is_team_shots_market("Player Shots O/U"))

    def test_accepts_explicit_team_markets(self):
        self.assertTrue(MODULE._is_team_shots_market("Team Shots Home"))
        self.assertTrue(MODULE._is_team_shots_market("Total Shots Away"))
        self.assertTrue(MODULE._is_team_shots_market("Total Shots Home"))

    def test_rejects_ambiguous_match_total(self):
        self.assertFalse(MODULE._is_team_shots_market("Total Shots"))

    def test_extractor_drops_rows_without_a_team_identity(self):
        payload = [
            {
                "id": "1",
                "date": "2026-08-17T19:00:00Z",
                "home": "Home FC",
                "away": "Away FC",
                "bookmakers": {
                    "Bet365": [
                        {
                            "name": "Player Shots O/U",
                            "odds": [{"label": "Over 1.5", "odds": "1.90"}],
                        },
                        {
                            "name": "Team Shots Home",
                            "odds": [{"label": "Over 10.5", "odds": "1.95"}],
                        },
                    ]
                },
            }
        ]
        rows = MODULE._extract_odds_api_rows(payload, {"competition": "Test"}, "2026-08-15T00:00:00Z")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["team"], "Home FC")


if __name__ == "__main__":
    unittest.main()
