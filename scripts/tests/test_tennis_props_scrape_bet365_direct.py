from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SCRIPTS_DIR / "tennis-props-scrape-bet365-direct.py"
SPEC = importlib.util.spec_from_file_location("tennis_props_scrape_bet365_direct", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Bet365DirectParserTests(unittest.TestCase):
    def test_builds_stable_seed_from_projection_board_row(self) -> None:
        rows = [
            {
                "scheduled_date": "2026-09-03",
                "scheduled_start_utc": "",
                "tour": "ATP",
                "tournament": "US Open",
                "player": "Jan-Lennard Struff",
                "opponent": "Francisco Cerundolo",
            }
        ]
        first = MODULE.seed_events(rows)
        second = MODULE.seed_events(rows)
        seed = first[MODULE.pair_key("Jan-Lennard Struff", "Francisco Cerundolo")]
        self.assertEqual(seed["date"], "2026-09-03")
        self.assertTrue(seed["event_id"].startswith("bet365-direct-"))
        self.assertEqual(first, second)

    def test_parses_london_event_start_to_utc_during_bst(self) -> None:
        body = "US Open 3 Sep 16:00 Jan-Lennard Struff vs Francisco Cerundolo Popular"
        self.assertEqual(
            MODULE.parse_event_start(
                body, "Jan-Lennard Struff", "Francisco Cerundolo", "2026-09-03"
            ),
            "2026-09-03T15:00:00Z",
        )

    def test_parses_london_event_start_to_utc_during_gmt(self) -> None:
        body = "ATP London 8 Jan 14:30 One Player vs Two Player Popular"
        self.assertEqual(
            MODULE.parse_event_start(body, "One Player", "Two Player", "2027-01-08"),
            "2027-01-08T14:30:00Z",
        )

    def test_parses_fractional_break_board(self) -> None:
        body = (
            "Double Result BB Total Breaks of Serve BB Match Brandon Nakashima Alex Michelsen "
            "Over 6.5 5/6 3.5 4/7 2.5 4/6 Under 6.5 5/6 3.5 5/4 2.5 11/10 "
            "Ace Totals BB Double Fault Totals BB"
        )
        self.assertEqual(
            MODULE.parse_break_board(body),
            [
                ("6.5", 1.0 + 5.0 / 6.0, 1.0 + 5.0 / 6.0),
                ("3.5", 1.0 + 4.0 / 7.0, 2.25),
                ("2.5", 1.0 + 4.0 / 6.0, 2.1),
            ],
        )

    def test_parses_decimal_break_board(self) -> None:
        body = (
            "Total Breaks of Serve Match Brandon Nakashima Alex Michelsen "
            "Over 6.5 1.83 3.5 1.57 2.5 1.66 Under 6.5 1.83 3.5 2.25 2.5 2.10 "
            "Ace Totals"
        )
        self.assertEqual(
            MODULE.parse_break_board(body),
            [("6.5", 1.83, 1.83), ("3.5", 1.57, 2.25), ("2.5", 1.66, 2.1)],
        )

    def test_rejects_mismatched_over_under_lines(self) -> None:
        body = (
            "Total Breaks of Serve BB Match One Two Over 6.5 5/6 3.5 4/7 2.5 4/6 "
            "Under 7.5 5/6 3.5 5/4 2.5 11/10 Ace Totals"
        )
        self.assertEqual(MODULE.parse_break_board(body), [])

    def test_builds_match_and_both_player_rows(self) -> None:
        rows = MODULE.build_rows(
            player1="Brandon Nakashima",
            player2="Alex Michelsen",
            seed={
                "event_id": "73992358",
                "date": "2026-09-02",
                "tour": "ATP",
                "tournament": "US Open",
                "match_start_utc": "2026-09-02T16:00:00Z",
            },
            prices=[("6.5", 1.83, 1.83), ("3.5", 1.57, 2.25), ("2.5", 1.66, 2.1)],
            captured_at="2026-09-02T12:00:00Z",
        )
        self.assertEqual([row["market"] for row in rows], ["match_breaks", "player_breaks", "player_breaks"])
        self.assertEqual(rows[0]["line"], "6.5")
        self.assertEqual(rows[1]["player"], "Brandon Nakashima")
        self.assertEqual(rows[2]["player"], "Alex Michelsen")
        self.assertEqual(rows[2]["under_odds"], "2.1000")

    def test_derives_both_us_open_competitions_from_atp_and_wta_seeds(self) -> None:
        seeds = {
            ("a", "b"): {"tournament": "US Open", "tour": "ATP"},
            ("c", "d"): {"tournament": "US Open", "tour": "WTA"},
        }
        self.assertEqual(MODULE.competition_labels(seeds, None), ("US Open", "US Open Women"))

    def test_tracked_only_keeps_pending_prospective_break_fixtures(self) -> None:
        seeds = {
            MODULE.pair_key("Madison Keys", "Anna Bondar"): {"event_id": "1"},
            MODULE.pair_key("Other Player", "Another Player"): {"event_id": "2"},
        }
        rows = [
            {
                "player": "Anna Bondar",
                "opponent": "Madison Keys",
                "market": "player_breaks",
                "decision_mode": "breaks_single_source_shadow",
                "settlement_status": "pending",
            },
            {
                "player": "Other Player",
                "opponent": "Another Player",
                "market": "player_breaks",
                "decision_mode": "breaks_single_source_shadow",
                "settlement_status": "settled",
            },
        ]
        filtered = MODULE.tracked_seed_events(seeds, rows)
        self.assertEqual(list(filtered.values()), [{"event_id": "1"}])


if __name__ == "__main__":
    unittest.main()
