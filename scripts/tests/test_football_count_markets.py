from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from football_count_markets import (  # noqa: E402
    append_control_odds_rows,
    build_control_odds_rows,
    build_market_inventory_rows,
    classify_market,
    market_line_sides,
)


class FootballCountMarketTests(unittest.TestCase):
    def test_conservative_market_classification(self) -> None:
        self.assertEqual(classify_market("Team Fouls Home"), "team_fouls_total")
        self.assertEqual(classify_market("Total Fouls Home"), "team_fouls_total")
        self.assertEqual(classify_market("Fouls Totals"), "match_fouls_total")
        self.assertEqual(classify_market("Player Fouls Committed"), "player_fouls_committed")
        self.assertEqual(classify_market("Player To Be Fouled"), "player_fouled")
        self.assertEqual(classify_market("Team Cards Away"), "team_cards_total")
        self.assertEqual(classify_market("Bookings Totals Away"), "team_cards_total")
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

    def test_extracts_match_odds_from_direct_provider_shape(self) -> None:
        payload = [
            {
                "id": "event-1",
                "date": "2026-08-22T16:30:00Z",
                "home": "Udinese Calcio",
                "away": "Como 1907",
                "bookmakers": {
                    "Bet365": [
                        {"name": "ML", "home": 2.10, "draw": 3.30, "away": 3.40},
                        {"name": "ML HT", "home": 2.80, "draw": 2.10, "away": 4.10},
                    ]
                },
            }
        ]
        rows = build_control_odds_rows(payload, "Serie A", "2026-08-21T09:00:00Z")
        self.assertEqual([row["side"] for row in rows], ["home", "draw", "away"])
        self.assertEqual([row["odds_decimal"] for row in rows], ["2.1000", "3.3000", "3.4000"])
        self.assertTrue(all(row["market"] == "MATCH_ODDS" for row in rows))

    def test_extracts_match_shots_and_full_match_corner_ladders_only(self) -> None:
        payload = [
            {
                "id": "event-2",
                "date": "2026-08-23T18:45:00Z",
                "home": "Torino FC",
                "away": "AC Milan",
                "bookmakers": {
                    "Bet365": [
                        {
                            "name": "Match Shots",
                            "odds": [{"hdp": 23.5, "over": "1.90", "under": "1.90"}],
                        },
                        {
                            "name": "Corners Totals",
                            "odds": [
                                {"label": "Over 9.5", "odds": "1.85"},
                                {"label": "Under 9.5", "odds": "1.95"},
                            ],
                        },
                        {
                            "name": "Alternative Corners",
                            "odds": [{"hdp": 10.5, "over": "2.20", "under": "1.65"}],
                        },
                        {
                            "name": "Corners Totals HT",
                            "odds": [{"hdp": 4.5, "over": "1.90", "under": "1.90"}],
                        },
                        {
                            "name": "Corners Totals Home",
                            "odds": [{"hdp": 5.5, "over": "1.90", "under": "1.90"}],
                        },
                    ]
                },
            }
        ]
        rows = build_control_odds_rows(payload, "Serie A", "2026-08-21T09:00:00Z")
        by_market: dict[str, list[dict]] = {}
        for row in rows:
            by_market.setdefault(row["market"], []).append(row)
        self.assertEqual(set(by_market), {"MATCH_SHOTS", "MATCH_CORNERS", "MATCH_CORNERS_ALT"})
        self.assertEqual({row["side"] for row in by_market["MATCH_SHOTS"]}, {"over", "under"})
        self.assertEqual({row["line"] for row in by_market["MATCH_CORNERS"]}, {"9.5"})
        self.assertEqual({row["line"] for row in by_market["MATCH_CORNERS_ALT"]}, {"10.5"})

    def test_extracts_canonical_total_shots_but_not_team_totals(self) -> None:
        payload = [
            {
                "id": "event-canonical",
                "date": "2026-09-06T18:45:00Z",
                "home": "Home FC",
                "away": "Away FC",
                "bookmakers": {
                    "Bet365": [
                        {
                            "name": "Total Shots",
                            "odds": [{"hdp": 24.5, "over": "1.91", "under": "1.91"}],
                        },
                        {
                            "name": "Total Shots Home",
                            "odds": [{"hdp": 14.5, "over": "1.83", "under": "2.00"}],
                        },
                        {
                            "name": "Total Shots on Target",
                            "odds": [{"hdp": 8.5, "over": "1.90", "under": "1.90"}],
                        },
                    ]
                },
            }
        ]
        rows = build_control_odds_rows(payload, "Premier League", "2026-09-05T09:00:00Z")
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["market"] == "MATCH_SHOTS" for row in rows))
        self.assertEqual({row["line"] for row in rows}, {"24.5"})

    def test_control_odds_append_is_idempotent(self) -> None:
        row = {
            "captured_at": "2026-08-21T09:00:00Z",
            "match_date": "2026-08-22",
            "event_id": "event-3",
            "kickoff_at": "2026-08-22T16:30:00Z",
            "snapshot_kind": "live_capture",
            "bookmaker": "Bet365",
            "competition": "Serie A",
            "home_team": "Inter Milano",
            "away_team": "AC Monza",
            "market": "MATCH_ODDS",
            "line": "",
            "side": "home",
            "odds_decimal": "1.3000",
            "source": "odds_api_io",
            "notes": "market=ML",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "control.csv"
            self.assertEqual(append_control_odds_rows(path, [row]), 1)
            self.assertEqual(append_control_odds_rows(path, [row]), 0)
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
