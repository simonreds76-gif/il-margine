from __future__ import annotations

import runpy
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOADER = runpy.run_path(
    str(ROOT / "scripts" / "oncourt-load-supabase.py"),
    run_name="oncourt_load_supabase_current_players_test",
)


class OnCourtCurrentPlayerSyncTests(unittest.TestCase):
    def test_selects_each_current_fixture_player_once(self) -> None:
        players = [
            {"id": "10", "name": "Alpha"},
            {"id": "20", "name": "Beta"},
            {"id": "30", "name": "Gamma"},
        ]
        fixtures = [
            {"player1_id": "20", "player2_id": "30"},
            {"player1_id": "30", "player2_id": "20"},
            {"player1_id": "", "player2_id": None},
        ]

        selected = LOADER["current_fixture_player_rows"](players, fixtures)

        self.assertEqual([row["id"] for row in selected], ["20", "30"])


if __name__ == "__main__":
    unittest.main()
