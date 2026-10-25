import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import date

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import penalty_alert_reviews as reviews


def script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def state(tickets=None, audit=None):
    return {"tickets": tickets or {}, "clubs": {}, "audit": audit or []}


def decision(status):
    return {"status": status, "updated_at": "2026-10-19T16:00:00Z"}


class PenaltyAlertReviewsTests(unittest.TestCase):
    def test_real_legacy_admin_identity_and_aliases(self):
        cases = [
            ({"date": "2026-10-18", "league": "serie-a", "team": "AC Milan", "opponent": "Atalanta", "actual_taker": "Gonçalo Ramos"},
             "2026-10-18|serie-a|milan|atalanta|ramos"),
            ({"date": "2026-10-12", "league": "epl", "team": "Coventry City", "opponent": "Newcastle United", "actual_taker": "Jack Rudoni"},
             "2026-10-12|epl|coventry city|newcastle united|rudoni"),
            ({"date": "2026-10-18", "league": "la-liga", "team": "Real Madrid", "opponent": "Sevilla", "actual_taker": "Kylian Mbappé"},
             "2026-10-18|la-liga|real madrid|sevilla|mbapp"),
        ]
        alert = script("club-penalty-review-alert")
        for row, identity in cases:
            row.update({role + "_on_pitch_at_penalty": "Yes - started"
                        for role in ("primary", "secondary", "tertiary", "actual_taker")})
            self.assertEqual(reviews.ticket_id(row), identity)
            for status in reviews.CLOSED:
                with self.subTest(identity=identity, status=status):
                    self.assertEqual(alert.new_actionable_rows(
                        [{**row, "review_priority": "high"}], [], reviews=state({identity: decision(status)})), [])
            # A later penalty for this club and taker is not silently dismissed.
            self.assertEqual(len(alert.new_actionable_rows(
                [{**row, "date": "2026-10-25", "review_priority": "high"}], [],
                reviews=state({identity: decision("ignored")}))), 1)

    def test_hosted_reopen_overrides_old_local_closure(self):
        identity = "fpl-role|epl|2026/27|liverpool"
        remote = {"revision": 38, "payload": state({identity: decision("active")})}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "data/goalscorer/penalty-duty-review-state.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"items": {identity: decision("ignored")}}))
            with patch.dict(os.environ, {"NEXT_PUBLIC_SUPABASE_URL": "https://example.supabase.co",
                                        "SUPABASE_SERVICE_ROLE_KEY": "test"}, clear=True):
                with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps([remote]).encode())):
                    loaded = reviews.load_reviews(root)
            self.assertFalse(reviews.is_closed({"row_id": identity}, loaded))
            self.assertEqual(loaded["revision"], 38)

    def test_failure_cannot_turn_into_empty_decisions_or_send(self):
        for script_name, send in [("club-penalty-review-alert", "send_telegram"),
                                  ("club-penalty-squad-alert", "send_telegram"),
                                  ("telegram-penalty-role-review", "post_telegram")]:
            mod = script(script_name)
            with patch.object(mod, "load_reviews", side_effect=RuntimeError("unavailable")), \
                 patch.object(mod, send) as sender, patch.object(sys, "argv", [script_name]):
                with self.assertRaises(RuntimeError):
                    mod.main()
                sender.assert_not_called()

    def test_missing_and_invalid_authority_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(RuntimeError):
                    reviews.load_reviews(Path(directory))
            with patch.dict(os.environ, {"NEXT_PUBLIC_SUPABASE_URL": "https://example.supabase.co",
                                        "SUPABASE_SERVICE_ROLE_KEY": "test"}, clear=True):
                for data in ([], [{"revision": 1, "payload": {}}]):
                    with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(data).encode())):
                        with self.assertRaises(RuntimeError):
                            reviews.load_reviews(Path(directory))

    def test_done_renews_age_reminder_but_not_other_clubs_or_structural_errors(self):
        rows = [
            {"league": "epl", "club": "Coventry City", "status": "hierarchy_review_due"},
            {"league": "epl", "club": "Arsenal", "status": "hierarchy_review_due"},
            {"league": "epl", "club": "Coventry City", "status": "possible_duplicate_player"},
        ]
        s = state(audit=[{"action": "done", "club": "epl|coventrycity", "at": "2026-10-19T16:00:00Z"}])
        self.assertEqual(reviews.filter_quality({"hierarchy_quality": rows}, s, date(2026, 10, 20))["hierarchy_quality"], rows[1:])
        self.assertEqual(len(reviews.filter_quality({"hierarchy_quality": rows}, s, date(2026, 11, 10))["hierarchy_quality"]), 3)
        s["audit"][0]["action"] = "defer"
        self.assertEqual(len(reviews.filter_quality({"hierarchy_quality": rows}, s, date(2026, 10, 20))["hierarchy_quality"]), 3)

    def test_quality_ledger_survives_restart_and_generation_changes(self):
        row = {"status": "hierarchy_review_due", "league": "epl", "club": "Test", "detail": "Last review: 2026-09-01"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            reviews.save_sent(path, {reviews.issue_key(row)})
            self.assertIn(reviews.issue_key({**row, "generated_at": "tomorrow"}), reviews.load_sent(path))
            self.assertNotIn(reviews.issue_key({**row, "detail": "Last review: 2026-10-19"}), reviews.load_sent(path))

    def test_older_legacy_review_does_not_replace_newer_verified_date(self):
        row = {"league": "epl", "club": "Coventry City", "status": "hierarchy_review_due",
               "detail": "Last penalty-role review: 2026-09-19; review due after 21 days."}
        s = state({"2026-08-30|epl|coventry city|test|rudoni":
                   {"status": "ignored", "updated_at": "2026-08-31T00:00:00Z"}})
        self.assertEqual(reviews.filter_quality({"hierarchy_quality": [row]}, s, date(2026, 10, 20))["hierarchy_quality"], [row])

    def test_role_done_is_suppressed_even_when_source_keeps_active(self):
        mod = script("telegram-penalty-role-review")
        row = {"row_id": "fpl-role|epl|2026/27|liverpool", "status": "active"}
        with patch.object(mod, "load_reviews", return_value=state({row["row_id"]: decision("ignored")})), \
             patch.object(mod, "read_json", side_effect=[{"rows": [row]}, {}]), \
             patch.object(mod, "post_telegram") as sender, patch.object(sys, "argv", ["role", "--dry-run"]):
            self.assertEqual(mod.main(), 0)
            sender.assert_not_called()


if __name__ == "__main__":
    unittest.main()
