from __future__ import annotations

import importlib.util
import tempfile
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

    def test_low_priority_row_is_actionable_for_conditional_hierarchy(self):
        candidate = row(priority="low", taker="Conditional Candidate")
        result = MODULE.new_actionable_rows(
            [candidate],
            [],
            {"epl|examplefc": "conditional"},
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["public_hierarchy_status"], "conditional")

    def test_durable_alert_state_blocks_ticket_after_report_window_changes(self):
        candidate = row(taker="Already Alerted")
        result = MODULE.new_actionable_rows(
            [candidate],
            [],
            {},
            {MODULE.row_identity(candidate)},
        )
        self.assertEqual(result, [])

    def test_alert_state_round_trip(self):
        candidate = row(taker="Persisted Taker")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "alert-state.json"
            state = MODULE.load_alert_state(path)
            MODULE.write_alert_state(path, state, [candidate])
            loaded = MODULE.load_alert_state(path)
        self.assertIn(MODULE.row_identity(candidate), loaded["items"])
        self.assertEqual(loaded["items"][MODULE.row_identity(candidate)]["team"], "Example FC")

    def test_identity_normalises_accents_and_spacing(self):
        first = row(taker="Kylian Mbappe")
        second = row(taker="Kylian  Mbappe")
        self.assertEqual(MODULE.row_identity(first), MODULE.row_identity(second))

    def test_message_contains_review_actions_and_link(self):
        message = MODULE.build_message([row()], "http://localhost:3000/model-monitor/goalscorer#penalty-watchlist")
        self.assertIn("1 new ticket(s): 1 high, 0 medium", message)
        self.assertIn("Done = reviewed and close", message)
        self.assertIn("Defer = park", message)
        self.assertIn("Hierarchy changes remain a separate editorial action", message)
        self.assertIn("#penalty-watchlist", message)


if __name__ == "__main__":
    unittest.main()
