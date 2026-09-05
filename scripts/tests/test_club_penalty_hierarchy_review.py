from __future__ import annotations

import copy
import json
import runpy
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "club-penalty-hierarchy-review.py"
M = runpy.run_path(str(SCRIPT))
NOW = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)


class ClubPenaltyHierarchyReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data/goalscorer"
        self.data.mkdir(parents=True)
        self.entry = {"primary": "First Player", "secondary": "Second Player", "tertiary": "Third Player",
                      "last_updated": "2026-09-01", "public_updated_at": "2026-09-01", "hierarchy_status": "probable",
                      "last_reviewed": {"date": "2026-09-01", "method": "current_season_multi_source_review", "sources": ["a", "b"]},
                      "evidence_log": [{"id": "curated", "date": "2026-09-01", "context": "Retain this editorial evidence"}],
                      "change_log": [], "condition_note": "Original context", "custom_curated_field": {"keep": True}}
        self.write("epl-penalty-takers.json", {"_meta": {"schema_version": 2, "season": {"label": "2026/27"}}, "Example FC": self.entry})
        self.events = [self.event("one", "2026-09-03"), self.event("two", "2026-09-04")]
        self.write_events()
        self.squad = {"generated_at": "2026-09-05T10:00:00Z", "club_squads": {"epl|Example FC": list(M["hierarchy"](self.entry).values())},
                      "rows": [{"league": "epl", "club": "Example FC", "rank": slot, "player": name, "status": "present",
                                "source_url": "https://www.fotmob.com/teams/1/example"} for slot, name in M["hierarchy"](self.entry).items()]}
        self.write("club-penalty-squad-audit.json", self.squad)

    def write(self, name, value):
        (self.data / name).write_text(json.dumps(value), encoding="utf-8")

    def event(self, match, day, **overrides):
        return dict({"id": f"fotmob|epl|{match}|shot", "match_id": match, "source_event_id": "shot",
                     "source_url": f"https://www.fotmob.com/matches/{match}", "observed_at": "2026-09-05T10:00:00Z",
                     "event_date": day, "team": "Example FC", "taker": "Second Player", "primary": "First Player",
                     "minute": 60, "on_pitch_proof": {"method": "completed_lineup_timeline", "reason": "on_pitch", "player_id": 1, "player": "First Player", "minute": 60},
                     "primary_on_pitch": True, "competitive": True, "finished": True, "penalty_kind": "in_match", "season": "2026/27"}, **overrides)

    def write_events(self, complete=True):
        self.write("epl-penalty-duty-live-review.json", {"generated_at": "2026-09-05T10:00:00Z", "source_health": {"complete": complete},
                                                        "rows": [{"review_source": "fotmob_live", "event_evidence": self.events}]})

    def report(self):
        return M["build_report"](self.root, NOW)[0]

    def club(self):
        return self.report()["clubs"][0]

    def command(self, action="override", **overrides):
        report = self.report()
        return dict({"action": action, "id": "epl|Example FC", "expected_revision": report["revision"],
                     "expected_entry_hash": report["clubs"][0]["entry_hash"], "reason": "Verified editorial adjustment",
                     "hierarchy": {"primary": "Third Player", "secondary": "First Player", "tertiary": "Second Player"},
                     "sources": [{"label": "Club report", "url": "https://example.org/club-report"}]}, **overrides)

    def test_default_review_retains_curated_bytes_and_dates(self):
        before = (self.data / "epl-penalty-takers.json").read_bytes()
        report = M["run"](self.root, now=NOW)
        self.assertEqual(report["summary"], {"ready": 1})
        self.assertEqual((self.data / "epl-penalty-takers.json").read_bytes(), before)
        self.assertFalse((self.data / "club-penalty-controls.json").exists())

    def test_two_exact_matches_can_apply_once_preserving_editorial_history(self):
        report = M["run"](self.root, apply_safe=True, now=NOW)
        self.assertEqual(len(report["applied_transactions"]), 1)
        row = json.loads((self.data / "epl-penalty-takers.json").read_text())["Example FC"]
        self.assertEqual(row["primary"], "Second Player")
        self.assertEqual(row["secondary"], "First Player")
        self.assertEqual(row["custom_curated_field"], {"keep": True})
        self.assertEqual(row["evidence_log"][0], self.entry["evidence_log"][0])
        self.assertEqual(row["last_reviewed"], self.entry["last_reviewed"])
        self.assertEqual(row["change_log"][-1]["evidence_ids"], [row["evidence_log"][-1]["id"]])
        self.assertEqual(row["squad_membership"]["primary"]["player"], "Second Player")
        self.assertEqual(M["run"](self.root, apply_safe=True, now=NOW)["applied_transactions"], [])

    def test_same_match_multiple_attempts_are_not_independent(self):
        self.events[1] = dict(self.events[0], id="different-shot", source_event_id="second-shot")
        self.write_events()
        self.assertEqual(self.club()["status"], "review")

    def test_unproven_or_ineligible_events_cannot_promote(self):
        for field, value in (("primary_on_pitch", None), ("primary_on_pitch", False), ("competitive", False),
                             ("finished", False), ("penalty_kind", "shootout"), ("source_event_id", ""),
                             ("source_url", "http://example.org"), ("season", "2025/26"),
                             ("on_pitch_proof", {}),
                             ("observed_at", "2026-09-06T00:00:00Z"), ("event_date", "2026-09-01")):
            with self.subTest(field=field, value=value):
                self.events = [self.event("one", "2026-09-03"), self.event("two", "2026-09-04", **{field: value})]
                self.write_events()
                self.assertNotEqual(self.club()["status"], "ready")

    def test_stale_missing_and_incomplete_sources_cannot_promote(self):
        self.write_events(complete=False)
        self.assertNotEqual(self.club()["status"], "ready")
        self.write_events()
        self.squad["generated_at"] = "2026-08-01T00:00:00Z"
        self.write("club-penalty-squad-audit.json", self.squad)
        self.assertNotEqual(self.club()["status"], "ready")

    def test_conflicting_assignment_disputed_order_and_unranked_taker_require_review(self):
        self.events.append(self.event("three", "2026-09-04", taker="First Player"))
        self.write_events()
        self.assertEqual(self.club()["status"], "review")
        self.events.pop()
        self.write_events()
        self.entry["hierarchy_status"] = "disputed"
        self.write("epl-penalty-takers.json", {"_meta": {"season": {"label": "2026/27"}}, "Example FC": self.entry})
        self.assertEqual(self.club()["status"], "review")

    def test_old_manual_ticket_resolution_blocks_repromotion(self):
        self.write("penalty-duty-review-state.json", {"schema_version": 1, "items": {"2026-09-03|epl|example fc|opponent|player": {"status": "ignored"}}})
        self.assertEqual(self.club()["status"], "review")
        self.assertTrue(any("manual ticket" in reason for reason in self.club()["reasons"]))

    def test_manual_override_and_unlock_preserve_override_until_release(self):
        M["run"](self.root, command=self.command(), now=NOW)
        self.assertEqual(self.club()["status"], "locked")
        M["run"](self.root, command=self.command("unlock"), now=NOW)
        self.assertEqual(self.club()["status"], "locked")
        M["run"](self.root, command=self.command("release"), now=NOW)
        self.assertNotEqual(self.club()["status"], "locked")
        self.assertEqual(self.club()["current"]["primary"], "Third Player")

    def test_stale_revision_and_newer_entry_refuse_overwrite(self):
        command = self.command()
        M["run"](self.root, command=self.command("lock"), now=NOW)
        with self.assertRaisesRegex(M["Conflict"], "revision changed"):
            M["run"](self.root, command=command, now=NOW)
        command = self.command()
        payload = json.loads((self.data / "epl-penalty-takers.json").read_text())
        payload["Example FC"]["condition_note"] = "Later manual edit"
        self.write("epl-penalty-takers.json", payload)
        with self.assertRaisesRegex(M["Conflict"], "Hierarchy changed"):
            M["run"](self.root, command=command, now=NOW)

    def test_revert_restores_full_prior_entry_and_locks_against_reapplication(self):
        report = M["run"](self.root, command=self.command(), now=NOW)
        transaction = report["audit"][-1]["id"]
        M["run"](self.root, command=self.command("revert", transaction_id=transaction), now=NOW)
        restored = json.loads((self.data / "epl-penalty-takers.json").read_text())["Example FC"]
        self.assertEqual(M["hierarchy"](restored), M["hierarchy"](self.entry))
        self.assertEqual(restored["condition_note"], self.entry["condition_note"])
        self.assertEqual(restored["custom_curated_field"], self.entry["custom_curated_field"])
        self.assertEqual(restored["last_reviewed"], self.entry["last_reviewed"])
        self.assertEqual(restored["evidence_log"][0], self.entry["evidence_log"][0])
        self.assertEqual(restored["public_updated_at"], "2026-09-05")
        self.assertEqual(restored["evidence_log"][-1]["detection"], "manual_revert")
        self.assertEqual(self.club()["status"], "locked")
        self.assertEqual(len(M["state"](self.root)["audit"]), 2)

    def test_invalid_sources_placeholder_and_duplicate_names_are_rejected(self):
        for fields in ({"sources": []}, {"sources": [{"url": "javascript:alert(1)"}]},
                       {"hierarchy": {"primary": "TBC", "secondary": "", "tertiary": ""}},
                       {"hierarchy": {"primary": "First Player", "secondary": "First Player", "tertiary": ""}}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                M["run"](self.root, command=self.command(**fields), now=NOW)

    def test_interrupted_write_blocks_until_recovery_and_does_not_lose_audit(self):
        original = M["atomic_json"]
        def fail_state(path, value):
            if path.name == "club-penalty-controls.json":
                raise OSError("simulated interruption")
            original(path, value)
        with patch.dict(M["commit"].__globals__, atomic_json=fail_state):
            with self.assertRaises(OSError):
                M["run"](self.root, command=self.command(), now=NOW)
        with self.assertRaisesRegex(M["Conflict"], "Interrupted penalty transaction"):
            M["run"](self.root, now=NOW)
        with M["writer_lock"](self.root):
            self.assertEqual(len(M["recover"](self.root)), 1)
        self.assertEqual(M["state"](self.root)["revision"], 1)
        self.assertEqual(self.club()["current"]["primary"], "Third Player")
        self.assertEqual(len(M["state"](self.root)["audit"]), 1)

    def test_concurrent_writer_is_blocked_and_inspection_is_readonly(self):
        with M["writer_lock"](self.root):
            with self.assertRaises(M["Conflict"]):
                M["run"](self.root, now=NOW)
        before = sorted(str(path) for path in self.data.rglob("*"))
        M["run"](self.root, inspect_only=True, now=NOW)
        self.assertEqual(sorted(str(path) for path in self.data.rglob("*")), before)

    def test_source_correction_is_retained_and_blocks_autoapply(self):
        M["run"](self.root, now=NOW)
        self.events[0]["primary_on_pitch"] = False
        self.write_events()
        report = M["run"](self.root, now=NOW)
        evidence = report["clubs"][0]["evidence"][0]
        self.assertTrue(evidence["source_correction"])
        self.assertTrue(evidence["previous_evidence"]["primary_on_pitch"])
        self.assertNotEqual(report["clubs"][0]["status"], "ready")


if __name__ == "__main__":
    unittest.main()
