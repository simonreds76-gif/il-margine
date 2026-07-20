from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "club-penalty-review-alert.py"
SPEC = importlib.util.spec_from_file_location("club_penalty_review_alert", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def row(priority="high", taker="New Taker"):
    return {
        "date": "2026-08-17",
        "league": "epl",
        "team": "Example FC",
        "opponent": "Other FC",
        "actual_taker": taker,
        "review_priority": priority,
        "review_type": "unexpected_taker",
        "event_result": "scored",
        "primary_pre_match": "Filed Taker",
    }


class ClubPenaltyReviewAlertTests(unittest.TestCase):
    def test_new_actionable_rows_excludes_existing_and_low_priority(self):
        previous = [row(taker="Existing Taker")]
        current = [row(taker="Existing Taker"), row(priority="low", taker="Expected Taker"), row(taker="New Taker")]
        result = MODULE.new_actionable_rows(current, previous)
        self.assertEqual([item["actual_taker"] for item in result], ["New Taker"])

    def test_identity_normalises_accents_and_spacing(self):
        first = row(taker="Kylian Mbappe")
        second = row(taker="Kylian  Mbappe")
        self.assertEqual(MODULE.row_identity(first), MODULE.row_identity(second))

    def test_message_contains_review_actions_and_link(self):
        message = MODULE.build_message([row()], "http://localhost:3000/model-monitor/goalscorer#penalty-watchlist")
        self.assertIn("1 new ticket(s): 1 high, 0 medium", message)
        self.assertIn("After editing: Hierarchy updated = sorted", message)
        self.assertIn("Keep current order = ignore", message)
        self.assertIn("#penalty-watchlist", message)


if __name__ == "__main__":
    unittest.main()
