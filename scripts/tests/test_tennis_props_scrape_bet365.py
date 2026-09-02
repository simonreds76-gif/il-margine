from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
MODULE_PATH = SCRIPTS / "tennis-props-scrape-bet365.py"
SPEC = importlib.util.spec_from_file_location("tennis_props_scrape_bet365", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def event(league: str, home: str = "Player One", away: str = "Player Two") -> dict:
    return {"league": {"name": league}, "home": home, "away": away}


class TennisPropsTournamentSelectionTests(unittest.TestCase):
    def test_current_main_tour_events_are_selected(self) -> None:
        for league in (
            "ATP - Bastad, Sweden",
            "ATP - Gstaad, Switzerland",
            "ATP - Umag, Croatia",
            "ATP - Estoril, Portugal",
            "ATP - Kitzbuhel, Austria",
            "WTA - Hamburg, Germany",
        ):
            with self.subTest(league=league):
                self.assertTrue(MODULE.is_supported_tournament_event(event(league)))

    def test_lower_tiers_are_rejected_even_when_city_matches(self) -> None:
        for league in (
            "Challenger - Nottingham 3, Great Britain",
            "ATP Challenger - Gstaad",
            "ITF Women - Bastad",
            "WTA 125 - Hamburg",
            "WTA 125K - Rome, Italy",
            "ATP - Wimbledon Juniors",
            "WTA - Athens, Greece, Doubles",
        ):
            with self.subTest(league=league):
                self.assertFalse(MODULE.is_supported_tournament_event(event(league)))

    def test_doubles_are_rejected_separately(self) -> None:
        self.assertFalse(
            MODULE.is_singles_event(event("ATP - Bastad", "One / Two", "Three / Four"))
        )

    def test_current_tournament_names_are_canonical(self) -> None:
        self.assertEqual(MODULE.tournament_from_event(event("ATP - Bastad, Sweden")), "Bastad")
        self.assertEqual(MODULE.tournament_from_event(event("ATP - Gstaad, Switzerland")), "Gstaad")
        self.assertEqual(MODULE.tournament_from_event(event("ATP - Umag, Croatia")), "Umag")
        self.assertEqual(MODULE.tournament_from_event(event("ATP - Estoril, Portugal")), "Estoril")
        self.assertEqual(MODULE.tournament_from_event(event("ATP - Kitzbuhel, Austria")), "Kitzbuhel")

    def test_unknown_main_tour_name_uses_league_location(self) -> None:
        self.assertEqual(MODULE.tournament_from_event(event("ATP - Los Cabos, Mexico")), "Los Cabos")

    def test_slam_qualifying_events_are_selected(self) -> None:
        self.assertTrue(
            MODULE.is_supported_tournament_event(
                event("ATP - US Open, New York, USA, Qualifying")
            )
        )


class TennisPropsMarketShapeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = {
            "id": "72987034",
            "date": "2026-07-22T11:00:00Z",
            "league": {"name": "ATP - Estoril, Portugal"},
            "home": "Bueno, Gonzalo",
            "away": "Pereira, Tiago",
        }

    def test_team_total_away_is_assigned_to_away_player(self) -> None:
        rows = MODULE.extract_rows(
            self.fixture,
            "Bet365",
            {"name": "Team Total (Aces) Away", "odds": [{"hdp": 2.5, "over": "1.83"}]},
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["market"], "aces")
        self.assertEqual(rows[0]["player"], "Tiago Pereira")
        self.assertEqual(rows[0]["opponent"], "Gonzalo Bueno")
        self.assertEqual(rows[0]["over_odds"], "1.8300")

    def test_team_total_home_is_assigned_to_home_player(self) -> None:
        rows = MODULE.extract_rows(
            self.fixture,
            "Bet365",
            {"name": "Team Total (Double Faults) Home", "odds": [{"hdp": 1.5, "over": "2.10"}]},
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["market"], "double_faults")
        self.assertEqual(rows[0]["player"], "Gonzalo Bueno")
        self.assertEqual(rows[0]["opponent"], "Tiago Pereira")

    def test_plain_totals_remain_match_level(self) -> None:
        rows = MODULE.extract_rows(
            self.fixture,
            "Bet365",
            {"name": "Totals (Aces)", "odds": [{"hdp": 4.5, "over": "1.66"}]},
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["market"], "match_aces")

    def test_plain_break_totals_are_match_level(self) -> None:
        rows = MODULE.extract_rows(
            self.fixture,
            "Bet365",
            {"name": "Totals (Service Breaks)", "odds": [{"hdp": 6.5, "over": "1.90", "under": "1.83"}]},
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["market"], "match_breaks")
        self.assertEqual(rows[0]["line"], "6.5")

    def test_team_break_total_is_assigned_to_player(self) -> None:
        rows = MODULE.extract_rows(
            self.fixture,
            "Bet365",
            {"name": "Team Total (Breaks) Away", "odds": [{"hdp": 2.5, "over": "2.00"}]},
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["market"], "player_breaks")
        self.assertEqual(rows[0]["player"], "Tiago Pereira")

    def test_tiebreak_is_not_misclassified_as_service_break(self) -> None:
        self.assertEqual(MODULE.identify_market("Tie Break in Match"), "match_tiebreak")

    def test_consolidated_player_props_are_split_by_stat_label(self) -> None:
        rows = MODULE.extract_rows(
            self.fixture,
            "Bet365",
            {
                "name": "Player Props",
                "odds": [
                    {"label": "Gonzalo Bueno (Aces)", "hdp": 4.5, "over": "1.90", "under": "1.83"},
                    {"label": "Tiago Pereira (Double Faults)", "hdp": 2.5, "over": "2.10", "under": "1.66"},
                ],
            },
        )
        self.assertEqual([(row["market"], row["player"]) for row in rows], [
            ("aces", "Gonzalo Bueno"),
            ("double_faults", "Tiago Pereira"),
        ])

    def test_count_row_detection_ignores_generic_match_markets(self) -> None:
        generic = dict(self.fixture)
        generic["bookmakers"] = {"Bet365": [{"name": "ML", "odds": []}]}
        self.assertFalse(MODULE.has_supported_count_rows(generic))
        generic["bookmakers"]["Bet365"].append(
            {"name": "Player Props", "odds": [{"label": "Gonzalo Bueno (Aces)", "hdp": 4.5, "over": "1.90"}]}
        )
        self.assertTrue(MODULE.has_supported_count_rows(generic))

    def test_break_detection_does_not_treat_aces_as_break_coverage(self) -> None:
        payload = dict(self.fixture)
        payload["bookmakers"] = {
            "Bet365": [
                {
                    "name": "Player Props",
                    "odds": [
                        {"label": "Gonzalo Bueno (Aces)", "hdp": 4.5, "over": "1.90", "under": "1.83"},
                    ],
                }
            ]
        }
        self.assertTrue(MODULE.has_supported_count_rows(payload))
        self.assertFalse(MODULE.event_has_market_rows(payload, MODULE.BREAK_MARKETS))

        payload["bookmakers"]["Bet365"][0]["odds"].append(
            {"label": "Gonzalo Bueno (Service Breaks)", "hdp": 2.5, "over": "2.10", "under": "1.66"}
        )
        self.assertTrue(MODULE.event_has_market_rows(payload, MODULE.BREAK_MARKETS))

    def test_default_and_player_props_rows_are_semantically_deduplicated(self) -> None:
        base = {
            "event_id": "72987034",
            "bookmaker": "Bet365",
            "player": "Gonzalo Bueno",
            "opponent": "Tiago Pereira",
            "market": "aces",
            "line": "4.5",
            "over_odds": "1.9000",
            "under_odds": "",
            "raw_market_name": "Team Total (Aces) Home",
        }
        consolidated = {
            **base,
            "under_odds": "1.8300",
            "raw_market_name": "Player Aces",
        }
        rows = MODULE.dedupe_snapshot_rows([base, consolidated])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["over_odds"], "1.9000")
        self.assertEqual(rows[0]["under_odds"], "1.8300")


if __name__ == "__main__":
    unittest.main()
