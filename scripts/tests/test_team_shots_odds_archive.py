from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "team-shots-odds-archive.py"
SPEC = importlib.util.spec_from_file_location("team_shots_odds_archive", SCRIPT)
assert SPEC and SPEC.loader
ARCHIVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ARCHIVE)


class TeamShotsOddsArchiveTests(unittest.TestCase):
    def test_keeps_team_total_market_with_target_team(self) -> None:
        self.assertTrue(
            ARCHIVE._is_team_total_row(
                {"market": "TEAM_SHOTS", "team": "Atletico Madrid", "player": ""}
            )
        )

    def test_drops_blank_team_player_market_mislabeled_as_team_shots(self) -> None:
        self.assertFalse(
            ARCHIVE._is_team_total_row(
                {
                    "market": "TEAM_SHOTS",
                    "team": "",
                    "player": "",
                    "notes": "market=Player Shots O/U",
                }
            )
        )

    def test_drops_explicit_player_market(self) -> None:
        self.assertFalse(
            ARCHIVE._is_team_total_row(
                {"market": "player_shots", "team": "", "player": "Player Name"}
            )
        )


if __name__ == "__main__":
    unittest.main()
