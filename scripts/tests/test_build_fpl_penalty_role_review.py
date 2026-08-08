from __future__ import annotations

import runpy
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = runpy.run_path(
    str(ROOT / "scripts" / "build-fpl-penalty-role-review.py"),
    run_name="build_fpl_penalty_role_review_test",
)


class FplPenaltyRoleReviewTests(unittest.TestCase):
    def test_only_conflicts_and_missing_hierarchies_become_tickets(self) -> None:
        hierarchy = {
            "_meta": {"season": {"label": "2026/27"}},
            "Arsenal": {"primary": "Bukayo Saka", "secondary": "Viktor Gyokeres"},
            "Liverpool": {"primary": "Mohamed Salah", "secondary": "Dominik Szoboszlai"},
            "Coventry City": {"primary": "", "secondary": ""},
            "Aston Villa": {"primary": "Ollie Watkins", "secondary": "Morgan Rogers"},
        }
        roster_rows = [
            {"team": "Arsenal", "player_name": "Bukayo Saka", "web_name": "Saka"},
            {"team": "Liverpool", "player_name": "Alexander Isak", "web_name": "Isak"},
            {"team": "Coventry City", "player_name": "Haji Wright", "web_name": "Wright"},
            {"team": "Aston Villa", "player_name": "Ollie Watkins", "web_name": "Watkins"},
            {"team": "Aston Villa", "player_name": "Emiliano Buendia", "web_name": "Buendia"},
        ]
        role_rows = [
            {"team": "Arsenal", "player_name": "Bukayo Saka", "web_name": "Saka", "penalty_order": "1"},
            {"team": "Liverpool", "player_name": "Alexander Isak", "web_name": "Isak", "penalty_order": "1"},
            {"team": "Coventry City", "player_name": "Haji Wright", "web_name": "Wright", "penalty_order": "1"},
            {"team": "Aston Villa", "player_name": "Emiliano Buendia", "web_name": "Buendia", "penalty_order": "1"},
        ]

        rows, season = MODULE["build_review_rows"](
            hierarchy,
            role_rows,
            roster_rows,
            generated_at="2026-08-07T12:00:00+00:00",
        )

        self.assertEqual(season, "2026/27")
        by_team = {row["team"]: row for row in rows}
        self.assertNotIn("Arsenal", by_team)
        self.assertEqual(by_team["Liverpool"]["review_type"], "primary_not_in_current_roster")
        self.assertEqual(by_team["Coventry City"]["review_type"], "unknown_hierarchy")
        self.assertEqual(by_team["Aston Villa"]["review_type"], "official_order_conflict")
        self.assertTrue(all(row["auto_apply"] is False for row in rows))

    def test_name_matching_handles_accents_and_web_names(self) -> None:
        self.assertTrue(
            MODULE["names_match"](
                "Martin Odegaard",
                player_name="Martin Ødegaard",
                web_name="Ødegaard",
            )
        )
        self.assertTrue(
            MODULE["names_match"](
                "Pascal Gross",
                player_name="Pascal Groß",
                web_name="Groß",
            )
        )


if __name__ == "__main__":
    unittest.main()
