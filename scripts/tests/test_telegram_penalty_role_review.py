from __future__ import annotations

import runpy
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = runpy.run_path(
    str(ROOT / "scripts" / "telegram-penalty-role-review.py"),
    run_name="telegram_penalty_role_review_test",
)


class TelegramPenaltyRoleReviewTests(unittest.TestCase):
    def test_fingerprint_ignores_generation_time_but_tracks_hierarchy_changes(self) -> None:
        base = {
            "row_id": "fpl-role|epl|2026/27|liverpool",
            "review_priority": "high",
            "review_type": "primary_not_in_current_roster",
            "current_primary": "Mohamed Salah",
            "proposed_primary": "Alexander Isak",
            "status": "active",
            "generated_at": "2026-08-07T12:00:00Z",
        }
        regenerated = dict(base, generated_at="2026-08-08T12:00:00Z")
        changed = dict(base, proposed_primary="Dominik Szoboszlai")

        self.assertEqual(MODULE["review_fingerprint"]([base]), MODULE["review_fingerprint"]([regenerated]))
        self.assertNotEqual(MODULE["review_fingerprint"]([base]), MODULE["review_fingerprint"]([changed]))

    def test_message_is_concise_and_points_to_internal_review_queue(self) -> None:
        message = MODULE["build_message"](
            [
                {
                    "team": "Liverpool",
                    "review_priority": "high",
                    "review_type": "primary_not_in_current_roster",
                    "current_primary": "Mohamed Salah",
                    "proposed_primary": "Alexander Isak",
                }
            ]
        )

        self.assertIn("Club penalty hierarchy reviews: 1 open", message)
        self.assertIn("Liverpool: Mohamed Salah -> Alexander Isak", message)
        self.assertIn("Model Monitor > Goalscorer > Preseason Role Review", message)
        self.assertNotIn("http", message)

    def test_active_rows_prioritise_high_severity(self) -> None:
        rows = MODULE["active_rows"](
            {
                "rows": [
                    {"row_id": "a", "status": "active", "review_priority": "medium"},
                    {"row_id": "z", "status": "active", "review_priority": "high"},
                    {"row_id": "ignored", "status": "dismissed", "review_priority": "high"},
                ]
            }
        )

        self.assertEqual([row["row_id"] for row in rows], ["z", "a"])


if __name__ == "__main__":
    unittest.main()
