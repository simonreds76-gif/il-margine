import unittest
import sys
from datetime import date, datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from tennis_qualifying_coverage import (
    current_tours, event_key, fallback_leagues, is_upcoming_quote,
    missing_qualifier_keys, schedule_coverage,
)

DAY = date(2026, 9, 27)
NOW = datetime(2026, 9, 27, 19, tzinfo=timezone.utc)
TOURS = [
    {"id": "10", "name": "China Open - Beijing", "date": "2026-09-28", "rank": "2"},
    {"id": "11", "name": "Japan Open Tennis Championships - Tokyo", "date": "2026-09-28", "rank": "2"},
    {"id": "12", "name": "Beijing Challenger - Beijing", "date": "2026-09-28", "rank": "1"},
]
MATCH = {"tour_id": "10", "player1_id": "1", "player2_id": "2", "round_id": "1", "date": "2026-09-28", "result": ""}
QUOTE = {"league_name": "ATP Beijing - Qualifiers", "player1_name": "One", "player2_name": "Two",
         "kickoff_iso": "2026-09-28T03:00:00Z", "odds1": "1.85", "odds2": "2.10"}

def resolver(name):
    return {"One": 1, "Two": 2, "Other": 3}.get(name), "test"


class CoverageTests(unittest.TestCase):
    def test_beijing_and_tokyo_keep_parent_tournament(self):
        tours = current_tours(TOURS, DAY)
        self.assertEqual(tours["beijing"]["tour_id"], 10)
        self.assertEqual(tours["tokyo"]["tour_id"], 11)
        self.assertEqual(event_key("ATP Beijing - Qualifiers"), event_key(TOURS[0]["name"]))

    def test_another_250_city_works_without_whitelist(self):
        self.assertEqual(event_key("ATP Winston-Salem - Qualifiers"), event_key("Winston-Salem Open - Winston-Salem"))

    def test_slam_alias_does_not_become_paris_masters(self):
        self.assertEqual(event_key("French Open - Paris"), "french_open")
        self.assertEqual(event_key("ATP Paris - Qualifiers"), "paris")

    def test_wrong_level_and_team_events_rejected(self):
        for text in ("WTA Beijing - Qualifiers", "ATP Challenger Beijing - Qualifiers", "ATP Beijing - Doubles - Qualifiers", "Laver Cup - London"):
            self.assertIsNone(event_key(text))

    def test_ambiguous_current_edition_rejected(self):
        self.assertNotIn("beijing", current_tours(TOURS + [{**TOURS[0], "id": "99"}], DAY))

    def test_wrong_season_rejected(self):
        self.assertFalse(current_tours([{**TOURS[0], "date": "2025-09-28"}], DAY))

    def test_missing_price_explicit_and_placeholders_excluded(self):
        rows = schedule_coverage([MATCH, {**MATCH, "player1_id": "3700", "player2_id": "3700"}], current_tours(TOURS, DAY), [], resolver, DAY, NOW)
        self.assertEqual(rows[0]["missing_prices"], 1)
        self.assertEqual(rows[0]["status"], "awaiting_prices")

    def test_reversed_price_pair_is_covered(self):
        rows = schedule_coverage([MATCH], current_tours(TOURS, DAY), [{**QUOTE, "player1_name": "Two", "player2_name": "One"}], resolver, DAY, NOW)
        self.assertEqual(rows[0]["with_current_prices"], 1)

    def test_wrong_event_cannot_supply_price(self):
        rows = schedule_coverage([MATCH], current_tours(TOURS, DAY), [{**QUOTE, "league_name": "ATP Tokyo - Qualifiers"}], resolver, DAY, NOW)
        self.assertEqual(rows[0]["with_current_prices"], 0)

    def test_started_unknown_and_naive_kickoffs_rejected(self):
        for timestamp in ("2026-09-27T18:59:00Z", "", "2026-09-28T03:00:00"):
            self.assertFalse(is_upcoming_quote({**QUOTE, "kickoff_iso": timestamp}, NOW))

    def test_finished_main_draw_and_outside_window_not_expected(self):
        variants = [{**MATCH, "result": "6-4 6-4"}, {**MATCH, "round_id": "4"}, {**MATCH, "date": "2026-10-10"}, {**MATCH, "live": "1"}]
        self.assertFalse(schedule_coverage(variants, current_tours(TOURS, DAY), [], resolver, DAY, NOW))

    def test_bounded_discovery_targets_only_missing_qualifiers(self):
        tours = current_tours(TOURS, DAY)
        missing = missing_qualifier_keys([MATCH], tours, [{"id": 1, "name": "ATP Tokyo - Qualifiers"}], DAY)
        catalogue = [{"id": 2, "name": "ATP Beijing - Qualifiers"}, {"id": 3, "name": "WTA Beijing - Qualifiers"}, {"id": 4, "name": "ATP Beijing - R1"}, {"id": 5, "name": "ATP Challenger Beijing - Qualifiers"}]
        self.assertEqual(list(fallback_leagues(catalogue, missing)), [2])
        self.assertFalse(missing_qualifier_keys([MATCH], tours, [catalogue[0]], DAY))


if __name__ == "__main__":
    unittest.main()
