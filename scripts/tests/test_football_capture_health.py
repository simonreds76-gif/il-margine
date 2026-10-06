from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from football_capture_health import SUPPORTED_LEAGUES, verified_empty_window


def load_script(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GATE = load_script("capture_gate", "football-counts-vnext-gate.py")
OPS = load_script("capture_ops", "ops-alert-check.py")


class EmptyCaptureWindowTests(unittest.TestCase):
    def setUp(self):
        self.capture = {
            "run_at": "2026-10-06T00:57:25Z", "success": True,
            "provider_errors": [], "events_found": 0, "rows_scraped": 0,
            "leagues": sorted(SUPPORTED_LEAGUES), "days_ahead": 2,
            "kickoff_within_minutes": 1440,
            "discovery_diagnostics": [
                {"league": league, "from": "2026-10-06T00:57:25Z",
                 "to": "2026-10-08T00:57:25Z", "provider_events": 532,
                 "selected_events": 0, "kickoff_within_minutes": 1440,
                 "state": "NO_LEAGUE_EVENTS_IN_FEED"}
                for league in sorted(SUPPORTED_LEAGUES)
            ],
        }
        self.rows = [{"model": "corners_v3", "kickoff_utc": "2026-10-09T18:30:00Z",
                      "match_id": "friday", "matchday": "5", "signal_status": "blocked",
                      "blocked_reason": "price_older_than_3h"}]
        self.scan = "2026-10-06T00:57:32Z"

    def check(self, capture=None, rows=None, scan=None):
        return verified_empty_window(
            self.capture if capture is None else capture,
            self.rows if rows is None else rows, scan or self.scan)

    def test_friday_prices_do_not_prove_missing_tuesday_shots(self):
        evidence = self.check()
        self.assertEqual(evidence["capture_window_end"], "2026-10-07T00:57:25Z")
        self.assertEqual(evidence["peer_rows_outside_window"], 1)

    def test_overlapping_or_unknown_peer_fixture_retains_alert(self):
        for kickoff in ("2026-10-06T12:00:00Z", "2026-10-07T00:57:25Z", "", "bad", "2026-10-09"):
            with self.subTest(kickoff=kickoff):
                self.assertIsNone(self.check(rows=[{**self.rows[0], "kickoff_utc": kickoff}]))

    def test_missing_failed_or_incomplete_feed_retains_alert(self):
        for change in (
            {"success": False}, {"provider_errors": ["HTTP 403"]}, {"error": "timeout"},
            {"events_found": 1}, {"rows_scraped": 2}, {"leagues": ["epl"]},
            {"discovery_diagnostics": []}, {"days_ahead": "bad"},
            {"kickoff_within_minutes": -1}, {"kickoff_within_minutes": float("nan")},
        ):
            with self.subTest(change=change):
                self.assertIsNone(self.check(capture={**self.capture, **change}))
        self.assertIsNone(self.check(capture={}))
        self.assertIsNone(verified_empty_window(self.capture, None, self.scan))

    def test_incomplete_or_failed_discovery_retains_alert(self):
        for change in (
            {"provider_events": 0}, {"selected_events": 1}, {"state": "EVENTS_WITHOUT_TEAM_SHOTS_MARKETS"},
            {"to": "2026-10-06T01:00:00Z"}, {"from": "bad"},
            {"kickoff_within_minutes": 90},
        ):
            capture = copy.deepcopy(self.capture)
            capture["discovery_diagnostics"][0].update(change)
            with self.subTest(change=change):
                self.assertIsNone(self.check(capture=capture))

    def test_stale_or_later_capture_cannot_clear_old_alert(self):
        for scan in ("2026-10-06T04:00:00Z", "2026-10-05T23:57:00Z", "invalid"):
            self.assertIsNone(self.check(scan=scan))

    def test_new_gate_reports_expected_idle_without_altering_record(self):
        with patch.object(GATE, "datetime") as clock:
            clock.now.return_value = datetime(2026, 10, 6, 0, 57, 32, tzinfo=UTC)
            payload = GATE.build_payload([], "", [], "", candidate_rows=self.rows, team_capture=self.capture)
        scan = payload["team_shots_v4"]["latest_scan"]
        self.assertEqual(scan["state"], "EXPECTED_EMPTY_CAPTURE_WINDOW")
        self.assertFalse(scan["operational_alert_required"])
        self.assertEqual(payload["team_shots_v4"]["prospective"]["signals"], 0)
        self.assertFalse(payload["team_shots_v4"]["live_routing"])
        self.assertEqual(payload["team_shots_v4"]["promotion_gate"], "BLOCKED")

    def test_ops_reconciles_saved_gate_and_retains_genuine_alerts(self):
        payload = {"generated_at": self.scan, "team_shots_v4": {"latest_scan": {
            "operational_alert_required": True, "operational_alert_code": "POST_UNLOCK_NO_SCORED_CANDIDATES",
            "scored_rows": 0, "scored_fixtures": 0}}}
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            form = data / "football-form"
            team = data / "team-shots"
            form.mkdir()
            team.mkdir()
            gate = form / "football-counts-vnext-gate.json"
            gate.write_text(json.dumps(payload), encoding="utf-8")
            status = team / "team-shots-scrape-last-run.json"
            status.write_text(json.dumps(self.capture), encoding="utf-8")
            candidates = form / "football-counts-vnext-candidates.csv"
            candidates.write_text("model,kickoff_utc\ncorners_v3,2026-10-09T18:30:00Z\n", encoding="utf-8")
            self.assertEqual(OPS.load_football_model_alerts(gate), [])
            status.write_text(json.dumps({**self.capture, "success": False}), encoding="utf-8")
            self.assertEqual(len(OPS.load_football_model_alerts(gate)), 1)
            status.write_text(json.dumps(self.capture), encoding="utf-8")
            candidates.write_text("model,kickoff_utc\ncorners_v3,2026-10-06T12:00:00Z\n", encoding="utf-8")
            self.assertEqual(len(OPS.load_football_model_alerts(gate)), 1)


if __name__ == "__main__":
    unittest.main()
