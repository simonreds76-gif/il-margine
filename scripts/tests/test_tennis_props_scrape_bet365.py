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


if __name__ == "__main__":
    unittest.main()
