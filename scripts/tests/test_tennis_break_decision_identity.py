from __future__ import annotations

import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
TRACKER = runpy.run_path(str(SCRIPTS / "tennis-props-shadow-tracker.py"))
SETTLE = runpy.run_path(str(SCRIPTS / "tennis-props-settle-shadow.py"))


class BreakDecisionIdentityTests(unittest.TestCase):
    def row(self, **changes):
        row = {
            "signal_id": "old-first", "date": "2026-09-04", "tour": "ATP", "tournament": "US Open",
            "event_id": "bet365-direct-stable", "bookmaker": "Bet365", "market": "player_breaks", "scope": "player",
            "player": "Frances Tiafoe", "opponent": "Valentin Vacherot", "side": "UNDER", "line": "3.5",
            "selected_odds": "1.833", "over_odds": "1.90", "under_odds": "1.833",
            "capture_ts": "2026-09-03T09:45:54Z", "logged_at_utc": "2026-09-03T09:52:30+00:00",
            "decision_mode": "breaks_single_source_shadow", "settlement_status": "settled",
            "result": "loss", "actual": "4", "pnl": "-1.000", "settlement_note": "oncourt:US Open:6-4 6-2 6-4",
            "settled_at_utc": "2026-09-05T01:00:00Z", "decision_key": "legacy-date-key", "trackable_shadow": "true",
        }
        row.update(changes)
        return row

    def test_reschedule_and_line_side_moves_keep_one_registered_decision(self):
        first = self.row()
        later = self.row(date="2026-09-05", line="4.5", side="OVER", shadow_side="OVER")
        self.assertEqual(TRACKER["prospective_decision_key"](first), TRACKER["prospective_decision_key"](later))
        self.assertEqual(TRACKER["signal_id"](first, "UNDER"), TRACKER["signal_id"](later, "OVER"))

    def test_different_events_books_tournaments_editions_and_subjects_are_preserved(self):
        first = self.row()
        for changes in ({"event_id": "different-event"}, {"bookmaker": "BetsBK"}, {"tournament": "Wimbledon"},
                        {"date": "2027-09-04"}, {"player": "Valentin Vacherot", "opponent": "Frances Tiafoe"}):
            with self.subTest(changes=changes):
                self.assertNotEqual(TRACKER["prospective_decision_key"](first), TRACKER["prospective_decision_key"](self.row(**changes)))

    def test_missing_event_identity_never_guesses_a_rescheduled_fixture(self):
        first = self.row(event_id="")
        later = self.row(event_id="", date="2026-09-05")
        rows = [first, later]
        self.assertEqual(TRACKER["reconcile_duplicate_break_decisions"](rows), 0)
        self.assertTrue(all(row["settlement_status"] == "settled" for row in rows))

    def test_duplicate_loss_is_quarantined_with_provenance_and_is_idempotent(self):
        first = self.row()
        later = self.row(signal_id="old-rescheduled", date="2026-09-05", capture_ts="2026-09-04T09:11:34Z")
        rows = [first, later]
        self.assertEqual(TRACKER["reconcile_duplicate_break_decisions"](rows), 1)
        self.assertEqual(len(rows), 2)
        self.assertEqual(first["signal_id"], "old-first")
        self.assertEqual((first["line"], first["side"], first["selected_odds"], first["pnl"]), ("3.5", "UNDER", "1.833", "-1.000"))
        self.assertEqual(later["settlement_status"], "void")
        self.assertEqual(later["quarantine_reason"], "duplicate_rescheduled_decision")
        self.assertEqual(later["duplicate_of_signal_id"], first["signal_id"])
        self.assertEqual((later["original_settlement_status"], later["original_result"], later["original_pnl"]), ("settled", "loss", "-1.000"))
        self.assertEqual(later["actual"], "4")
        self.assertEqual(TRACKER["reconcile_duplicate_break_decisions"](rows), 0)
        self.assertEqual(later["original_pnl"], "-1.000")
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            SETTLE["write_csv"](target / "signals.csv", rows)
            reread = SETTLE["read_csv"](target / "signals.csv")
            self.assertEqual(reread[1]["original_pnl"], "-1.000")
            SETTLE["write_performance"](target / "performance.txt", reread)
            performance = (target / "performance.txt").read_text()
            self.assertIn("settled: 1", performance)
            self.assertIn("PnL: -1.00u", performance)

    def test_line_side_change_updates_movement_without_rewriting_the_entry(self):
        first = self.row()
        later = self.row(signal_id="later", date="2026-09-05", capture_ts="2026-09-04T09:11:34Z", line="4.5", side="OVER")
        self.assertEqual(TRACKER["reconcile_duplicate_break_decisions"]([first, later]), 1)
        self.assertEqual((first["line"], first["side"]), ("3.5", "UNDER"))
        self.assertEqual(first["latest_line"], "4.5")
        self.assertEqual(first["line_move"], "1.000")

    def test_generic_aces_and_double_fault_contract_identity_is_unchanged(self):
        for market in ("aces", "double_faults"):
            row = self.row(market=market, decision_mode="two_way_player_shadow")
            self.assertNotEqual(TRACKER["signal_id"](row, "UNDER"), TRACKER["signal_id"](dict(row, line="4.5"), "UNDER"))

    def test_standalone_settlement_quarantines_before_roi_without_tracker_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            signals = path / "signals.csv"
            SETTLE["write_csv"](signals, [self.row(), self.row(signal_id="later", date="2026-09-05", capture_ts="2026-09-04T09:11:34Z")])
            with patch.object(sys, "argv", ["settle", "--signals", str(signals), "--performance", str(path / "performance.txt"),
                                           "--oncourt-dir", tmp, "--sackmann-dir", tmp, "--history-glob", str(path / "missing.csv")]):
                self.assertEqual(SETTLE["main"](), 0)
            retained = SETTLE["read_csv"](signals)
            self.assertEqual(len(retained), 2)
            self.assertEqual(retained[1]["original_pnl"], "-1.000")
            self.assertEqual(retained[1]["settlement_status"], "void")


if __name__ == "__main__":
    unittest.main()
