from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from football_team_names import football_form_team_key  # noqa: E402


class FootballTeamNameTests(unittest.TestCase):
    def test_bookmaker_suffixes_match_form_names(self) -> None:
        self.assertEqual(football_form_team_key("Arsenal FC"), football_form_team_key("Arsenal"))
        self.assertEqual(football_form_team_key("AFC Bournemouth"), football_form_team_key("Bournemouth"))

    def test_long_provider_names_match_form_abbreviations(self) -> None:
        pairs = (
            ("Bayer Leverkusen", "Leverkusen"),
            ("Borussia Dortmund", "Dortmund"),
            ("Eintracht Frankfurt", "Ein Frankfurt"),
            ("Paris Saint-Germain", "Paris SG"),
            ("Wolverhampton Wanderers", "Wolves"),
        )
        for provider_name, form_name in pairs:
            with self.subTest(provider_name=provider_name):
                self.assertEqual(football_form_team_key(provider_name), football_form_team_key(form_name))


if __name__ == "__main__":
    unittest.main()
