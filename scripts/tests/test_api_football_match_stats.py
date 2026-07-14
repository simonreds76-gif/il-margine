from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import api_football_match_stats as module


def stat(name: str, value: object) -> dict:
    return {"type": name, "value": value}


class ApiFootballMatchStatsTests(unittest.TestCase):
    def test_maps_reversed_response_by_team_id_and_keeps_extended_counts(self) -> None:
        fixture_payload = {
            "response": [
                {
                    "fixture": {"id": 123, "referee": "Referee Name"},
                    "teams": {
                        "home": {"id": 10, "name": "Arsenal"},
                        "away": {"id": 20, "name": "Chelsea"},
                    },
                }
            ]
        }
        stats_payload = {
            "response": [
                {
                    "team": {"id": 20, "name": "Chelsea"},
                    "statistics": [
                        stat("Total Shots", 8),
                        stat("Shots on Goal", 3),
                        stat("Corner Kicks", 4),
                        stat("Fouls", 13),
                        stat("Yellow Cards", 2),
                    ],
                },
                {
                    "team": {"id": 10, "name": "Arsenal"},
                    "statistics": [
                        stat("Total Shots", 15),
                        stat("Shots on Goal", 6),
                        stat("Corner Kicks", 7),
                        stat("Fouls", 9),
                        stat("Yellow Cards", 1),
                        stat("Blocked Shots", 5),
                    ],
                },
            ]
        }

        with patch.dict(os.environ, {"API_FOOTBALL_KEY": "test-key"}, clear=False), patch.object(
            module,
            "_request",
            side_effect=[fixture_payload, stats_payload],
        ):
            rows, meta = module.fetch_api_football_results(
                "epl",
                [{"date": "2026-08-15", "home_team": "Arsenal", "away_team": "Chelsea"}],
                max_requests=10,
            )

        self.assertEqual(meta["requests_used"], 2)
        row = rows["2026-08-15|arsenal|chelsea"]
        self.assertEqual(row["home_shots"], 15)
        self.assertEqual(row["away_shots"], 8)
        self.assertEqual(row["home_corners"], 7)
        self.assertEqual(row["total_corners"], 11)
        self.assertEqual(row["home_fouls"], 9)
        self.assertEqual(row["away_fouls"], 13)
        self.assertEqual(row["home_blocked_shots"], 5)
        self.assertEqual(row["referee"], "Referee Name")

    def test_missing_stat_stays_none_instead_of_becoming_zero(self) -> None:
        fixture_payload = {
            "response": [
                {
                    "fixture": {"id": 456},
                    "teams": {
                        "home": {"id": 10, "name": "Arsenal"},
                        "away": {"id": 20, "name": "Chelsea"},
                    },
                }
            ]
        }
        stats_payload = {
            "response": [
                {"team": {"id": 10}, "statistics": [stat("Corner Kicks", 3)]},
                {"team": {"id": 20}, "statistics": [stat("Corner Kicks", 5)]},
            ]
        }

        with patch.dict(os.environ, {"API_FOOTBALL_KEY": "test-key"}, clear=False), patch.object(
            module,
            "_request",
            side_effect=[fixture_payload, stats_payload],
        ):
            rows, _ = module.fetch_api_football_results(
                "epl",
                [{"date": "2026-08-15", "home_team": "Arsenal", "away_team": "Chelsea"}],
            )

        row = rows["2026-08-15|arsenal|chelsea"]
        self.assertIsNone(row["home_shots"])
        self.assertIsNone(row["away_sot"])
        self.assertEqual(row["total_corners"], 8)


if __name__ == "__main__":
    unittest.main()
