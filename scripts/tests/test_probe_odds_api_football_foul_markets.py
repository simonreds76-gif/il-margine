from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
MODULE_PATH = SCRIPTS / "probe-odds-api-football-foul-markets.py"
SPEC = importlib.util.spec_from_file_location("probe_odds_api_football_foul_markets", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FootballFoulMarketProbeTests(unittest.TestCase):
    def test_market_labels_separate_fouls_from_cards(self) -> None:
        payload = [
            {
                "id": "1",
                "bookmakers": {
                    "Bet365": [
                        {"name": "Team Fouls Home", "odds": [{"hdp": 11.5, "over": "1.90", "under": "1.90"}]},
                        {"name": "Bookings Totals", "odds": []},
                        {"name": "Totals", "odds": []},
                    ]
                },
            }
        ]
        labels = MODULE.market_labels(payload)
        self.assertEqual(labels["foul_market_labels"], ["Bet365: Team Fouls Home"])
        self.assertEqual(labels["card_market_labels"], ["Bet365: Bookings Totals"])
        self.assertEqual(labels["events_with_foul_markets"], 1)
        self.assertEqual(len(labels["paired_foul_lines"]), 1)
        self.assertEqual(labels["paired_foul_lines"][0]["line"], 11.5)


if __name__ == "__main__":
    unittest.main()
