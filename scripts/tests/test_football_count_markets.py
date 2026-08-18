from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from football_count_markets import (  # noqa: E402
    build_market_inventory_rows,
    classify_market,
    market_line_sides,
)


class FootballCountMarketTests(unittest.TestCase):
    def test_conservative_market_classification(self) -> None:
        self.assertEqual(classify_market("Team Fouls Home"), "team_fouls_total")
        self.assertEqual(classify_market("Fouls Totals"), "match_fouls_total")
        self.assertEqual(classify_market("Player Fouls Committed"), "player_fouls_committed")
        self.assertEqual(classify_market("Player To Be Fouled"), "player_fouled")
        self.assertEqual(classify_market("Team Cards Away"), "team_cards_total")
        self.assertEqual(classify_market("Bookings Spread"), "cards_other")
        self.assertEqual(classify_market("Goalkeeper Saves"), "player_saves")
        self.assertEqual(classify_market("Team Saves Home"), "team_saves_total")

    def test_detects_paired_prices_in_both_provider_shapes(self) -> None:
        combined = {"name": "Team Fouls Home", "odds": [{"hdp": 11.5, "over": "1.90", "under": "1.90"}]}
        separate = {
            "name": "Team Cards Away",
            "odds": [
                {"label": "Over 2.5", "odds": "2.10"},
                {"label": "Under 2.5", "odds": "1.70"},
            ],
        }
        self.assertEqual(market_line_sides(combined)[11.5], {"over", "under"})
        self.assertEqual(market_line_sides(separate)[2.5], {"over", "under"})

    def test_inventory_preserves_raw_label_and_pair_count(self) -> None:
        payload = [
            {
                "id": "event-1",
                "date": "2026-08-15T14:00:00Z",
                "home": "Home FC",
                "away": "Away FC",
                "bookmakers": {
                    "Bet365": [
                        {
                            "name": "Team Fouls Home",
                            "odds": [{"hdp": 10.5, "over": "1.85", "under": "1.95"}],
                        }
                    ]
                },
            }
        ]
        rows = build_market_inventory_rows(payload, "Premier League", "2026-08-15T08:15:00Z")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["market_name"], "Team Fouls Home")
        self.assertEqual(rows[0]["market_category"], "team_fouls_total")
        self.assertEqual(rows[0]["paired_line_count"], 1)


if __name__ == "__main__":
    unittest.main()
