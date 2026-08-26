from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
MODULE_PATH = SCRIPTS / "build-tennis-props-board.py"
SPEC = importlib.util.spec_from_file_location("build_tennis_props_board", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CurrentTournamentAliasTests(unittest.TestCase):
    def test_current_atp_clay_events_are_supported(self) -> None:
        aliases = {
            "Nordea Open - Bastad": "Bastad",
            "EFG Swiss Open - Gstaad": "Gstaad",
            "Plava Laguna Croatia Open - Umag": "Umag",
            "Millennium Estoril Open - Estoril": "Estoril",
            "Generali Open - Kitzbuhel": "Kitzbuhel",
            "Generali Open - Kitzbühel": "Kitzbuhel",
        }
        for raw, expected in aliases.items():
            with self.subTest(raw=raw):
                self.assertEqual(MODULE.canonical_tournament_name(raw), expected)

    def test_unknown_main_tour_schedule_uses_location_suffix(self) -> None:
        self.assertEqual(
            MODULE.scheduled_tournament_name("Mifel Tennis Open - Los Cabos"),
            "Los Cabos",
        )

    def test_slam_qualifiers_are_labelled_and_best_of_three(self) -> None:
        self.assertEqual(MODULE.round_label("2", "US Open"), "Q2")
        self.assertTrue(MODULE.is_slam_qualifying_round("US Open", "2"))
        self.assertFalse(MODULE.is_best_of_five("ATP", "US Open", "2"))
        self.assertEqual(MODULE.default_match_games("ATP", "US Open", "2"), 23.5)
        self.assertTrue(MODULE.is_best_of_five("ATP", "US Open", "4"))
        self.assertEqual(MODULE.default_match_games("ATP", "US Open", "4"), 35.0)

    def test_future_slam_shell_keeps_dated_qualifying_round(self) -> None:
        tour = {
            "id": "21349",
            "name": "U.S. Open - New York",
            "date": "2026-08-31",
            "rank": "4",
            "court_id": "1",
        }
        today = {
            "tour_id": "21349",
            "date": "2026-08-26",
            "player1_id": "1",
            "player2_id": "2",
            "round_id": "2",
            "result": "",
        }
        with (
            mock.patch.object(MODULE, "load_oncourt_player_names", return_value={"1": "One Player", "2": "Two Player"}),
            mock.patch.object(MODULE, "load_oncourt_tours", return_value={"21349": tour}),
            mock.patch.object(MODULE, "read_csv", return_value=[today]),
        ):
            rows = MODULE.oncourt_schedule_rows("ATP", False, "2026-08-26")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["round"], "Q2")
        self.assertEqual(rows[0]["date"], "2026-08-26")


class CurrentEventRowsCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        MODULE._CURRENT_EVENT_ROWS_CACHE.clear()

    def tearDown(self) -> None:
        MODULE._CURRENT_EVENT_ROWS_CACHE.clear()

    def test_large_exports_are_read_once_for_repeated_feature_loads(self) -> None:
        with mock.patch.object(
            MODULE,
            "_read_current_event_rows",
            side_effect=([{"tour_id": "101"}], [{"tour_id": "101"}]),
        ) as reader:
            first = MODULE.load_current_event_rows("atp", {"101"})
            second = MODULE.load_current_event_rows("atp", {"101"})

        self.assertIs(first, second)
        self.assertEqual(reader.call_count, 2)

    def test_current_wta_events_are_supported(self) -> None:
        aliases = {
            "Athens Open - Athens": "Athens",
            "UniCredit Iasi Open - Iasi": "Iasi",
        }
        for raw, expected in aliases.items():
            with self.subTest(raw=raw):
                self.assertEqual(MODULE.canonical_tournament_name(raw), expected)


class BreakFairOddsTests(unittest.TestCase):
    def test_match_ladder_contains_central_half_line(self) -> None:
        payload, distribution, status = MODULE.break_fair_odds_ladder(6.114, "ATP", "match_breaks")
        rows = json.loads(payload)
        central = next(row for row in rows if row["line"] == 6.5)
        self.assertEqual(distribution, "negative_binomial")
        self.assertEqual(status, "OUTCOME_PASS_PRICE_FEED_MISSING")
        self.assertAlmostEqual(central["fair_over"], 2.43, places=2)

    def test_match_total_is_identical_on_both_player_rows(self) -> None:
        left = {"tour": "ATP", "projected_breaks_for": "2.909", "break_notes": ""}
        right = {"tour": "ATP", "projected_breaks_for": "3.205", "break_notes": ""}
        MODULE.normalize_match_break_totals(left, right)
        self.assertEqual(left["projected_total_breaks"], right["projected_total_breaks"])
        self.assertEqual(left["match_break_fair_odds_json"], right["match_break_fair_odds_json"])


if __name__ == "__main__":
    unittest.main()
