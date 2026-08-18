from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
MODULE_PATH = SCRIPTS / "probe-odds-api-goalkeeper-saves.py"
SPEC = importlib.util.spec_from_file_location("probe_odds_api_goalkeeper_saves", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GoalkeeperSavesMarketProbeTests(unittest.TestCase):
    def test_choose_event_prefers_top_five_league(self) -> None:
        selected = MODULE.choose_event(
            [
                {"id": "minor", "date": "2026-08-18T09:00:00Z", "league": {"name": "Other League"}},
                {"id": "epl", "date": "2026-08-18T19:00:00Z", "league": {"name": "England Premier League"}},
            ]
        )
        self.assertIsNotNone(selected)
        self.assertEqual(selected["id"], "epl")

    def test_choose_event_rejects_irrelevant_fixture(self) -> None:
        for league in (
            "Australia Northern Territory Premier League Women",
            "England Amateur - U21 Premier League Cup, Group C",
        ):
            selected = MODULE.choose_event(
                [
                    {
                        "id": "regional",
                        "date": "2026-08-18T09:00:00Z",
                        "league": {"name": league},
                    }
                ]
            )
            self.assertIsNone(selected)

    def test_extracts_paired_goalkeeper_save_lines_only(self) -> None:
        payload = [
            {
                "id": "fixture-1",
                "bookmakers": {
                    "Bet365": [
                        {
                            "name": "Goalkeeper Saves",
                            "odds": [
                                {"name": "Goalkeeper A", "hdp": 3.5, "over": "1.90", "under": "1.90"},
                                {"name": "Goalkeeper B", "hdp": 2.5, "over": "1.83", "under": "2.00"},
                            ],
                        },
                        {"name": "Team Shots Home", "odds": [{"hdp": 11.5, "over": "1.90", "under": "1.90"}]},
                    ]
                },
            }
        ]
        observed = MODULE.goalkeeper_save_markets(payload)
        self.assertEqual(observed["market_labels"], ["Bet365: Goalkeeper Saves"])
        self.assertEqual(observed["events_with_goalkeeper_saves"], 1)
        self.assertEqual([row["line"] for row in observed["paired_lines"]], [3.5, 2.5])
        self.assertEqual([row["line"] for row in observed["over_lines"]], [3.5, 2.5])
        self.assertIn("over", observed["structures"][0]["prop_keys"])

    def test_extracts_over_only_goalkeeper_save_prices(self) -> None:
        payload = [
            {
                "id": "fixture-3",
                "bookmakers": {
                    "Bet365": [
                        {
                            "name": "Goalkeeper Saves",
                            "odds": [{"label": "Keeper A", "hdp": 3.5, "over": "1.83"}],
                        }
                    ]
                },
            }
        ]
        observed = MODULE.goalkeeper_save_markets(payload)
        self.assertEqual(observed["paired_lines"], [])
        self.assertEqual(
            observed["over_lines"],
            [
                {
                    "event_id": "fixture-3",
                    "bookmaker": "Bet365",
                    "market_name": "Goalkeeper Saves",
                    "player": "Keeper A",
                    "line": 3.5,
                    "over_price": 1.83,
                }
            ],
        )

    def test_unpaired_label_does_not_open_market_gate(self) -> None:
        payload = [
            {
                "id": "fixture-2",
                "bookmakers": {
                    "Bet365": [
                        {"name": "Goalkeeper Saves", "odds": [{"label": "Goalkeeper A Over 3.5", "odds": "1.90"}]}
                    ]
                },
            }
        ]
        observed = MODULE.goalkeeper_save_markets(payload)
        self.assertEqual(observed["market_labels"], ["Bet365: Goalkeeper Saves"])
        self.assertEqual(observed["paired_lines"], [])


if __name__ == "__main__":
    unittest.main()
