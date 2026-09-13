from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "ops-alert-check.py"
SPEC = importlib.util.spec_from_file_location("ops_alert_check", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PipelineAwareStuckTests(unittest.TestCase):
    def test_only_healthy_unrouted_research_rule_conflict_is_warning(self) -> None:
        lane = {"live_routing": False, "prospective_status": "AUTHORIZED_SHADOW", "count_gate": "PASS",
                "latest_scan": {"operational_alert_required": True,
                                "operational_alert_code": "EARLY_RULE_COMBINATION_BLOCKS_PRICED_LINES",
                                "scored_rows": 70, "scored_fixtures": 12,
                                "explanation": "Maximum edge 2.11%, required 3.00%."}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gate.json"
            path.write_text(json.dumps({"team_shots_v4": lane}), encoding="utf-8")
            self.assertEqual(MODULE.load_football_model_alerts(path), [])
            warnings = MODULE.load_football_model_alerts(path, warnings=True)
            self.assertIn("2.11%", warnings[0])
            for change in ({"live_routing": True}, {"count_gate": "FAIL"}, {"prospective_status": "BLOCKED"}):
                path.write_text(json.dumps({"team_shots_v4": {**lane, **change}}), encoding="utf-8")
                self.assertEqual(len(MODULE.load_football_model_alerts(path)), 1)
                self.assertEqual(MODULE.load_football_model_alerts(path, warnings=True), [])

    def test_warning_only_message_does_not_claim_pipeline_failure(self) -> None:
        message = MODULE.render_message(stuck=[], silent=[], model_warnings=["Review frozen selection rules"])
        self.assertIn("Ops check passed", message)
        self.assertIn("Review frozen selection rules", message)
        self.assertNotIn("found pipeline issues", message)

    def test_daily_run_below_ninety_minutes_is_not_stuck(self) -> None:
        rows = [{"pipeline": "oncourt-daily", "age_seconds": 22.2 * 60}]
        self.assertEqual(MODULE.filter_pipeline_aware_stuck_rows(rows), [])

    def test_daily_run_above_ninety_minutes_is_stuck(self) -> None:
        row = {"pipeline": "oncourt-daily", "age_seconds": 91 * 60}
        self.assertEqual(MODULE.filter_pipeline_aware_stuck_rows([row]), [row])

    def test_short_pipeline_keeps_database_view_threshold(self) -> None:
        row = {"pipeline": "pinnacle-capture-history", "age_seconds": 16 * 60}
        self.assertEqual(MODULE.filter_pipeline_aware_stuck_rows([row]), [row])

    def test_post_unlock_missing_candidates_becomes_ops_alert(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gate.json"
            path.write_text(
                json.dumps(
                    {
                        "team_shots_v4": {
                            "latest_scan": {
                                "operational_alert_required": True,
                                "operational_alert_code": "POST_UNLOCK_NO_SCORED_CANDIDATES",
                                "scored_rows": 0,
                                "scored_fixtures": 0,
                            }
                        },
                        "corners_v3": {"latest_scan": {"operational_alert_required": False}},
                    }
                ),
                encoding="utf-8",
            )

            alerts = MODULE.load_football_model_alerts(path)

        self.assertEqual(len(alerts), 1)
        self.assertIn("Team Shots v4: POST_UNLOCK_NO_SCORED_CANDIDATES", alerts[0])

    def test_isr_guard_passes_without_alert(self) -> None:
        completed = mock.Mock(returncode=0, stdout='{"ok":true,"issues":[]}', stderr="")
        with mock.patch.object(MODULE.subprocess, "run", return_value=completed):
            self.assertEqual(MODULE.load_vercel_isr_policy_alerts(SCRIPT), [])

    def test_isr_guard_failure_becomes_ops_alert(self) -> None:
        completed = mock.Mock(
            returncode=1,
            stdout='{"ok":false,"issues":["short revalidate on src/app/page.tsx: 60s (minimum 86400s)"]}',
            stderr="",
        )
        with mock.patch.object(MODULE.subprocess, "run", return_value=completed):
            alerts = MODULE.load_vercel_isr_policy_alerts(SCRIPT)
        self.assertEqual(
            alerts,
            ["Vercel ISR policy: short revalidate on src/app/page.tsx: 60s (minimum 86400s)"],
        )


if __name__ == "__main__":
    unittest.main()
