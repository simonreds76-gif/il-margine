from __future__ import annotations

import runpy
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GATE = runpy.run_path(str(ROOT / "scripts" / "football-counts-vnext-gate.py"), run_name="football_vnext_gate_test")


class FootballVnextGateTests(unittest.TestCase):
    def test_near_kickoff_workflow_refreshes_and_commits_scan_gate(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "football-counts-vnext-shadow.yml").read_text(encoding="utf-8")
        self.assertGreaterEqual(workflow.count("python scripts/football-counts-vnext-gate.py"), 1)
        self.assertIn("git add data/football-form/football-counts-vnext-gate.json", workflow)
        self.assertIn("git add data/football-form/football-counts-vnext-gate.md", workflow)

    def test_manual_gk_settlement_skips_capture_and_limits_staged_files(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "football-counts-vnext-shadow.yml").read_text(encoding="utf-8")
        self.assertIn("settlement_only:", workflow)
        self.assertGreaterEqual(workflow.count("github.event.inputs.settlement_only != 'true'"), 4)
        self.assertIn('if [[ "${{ github.event.inputs.settlement_only }}" == "true" ]]; then', workflow)
        self.assertIn("git add data/goalkeeper-saves/", workflow)

    def test_diagnostics_distinguish_expected_warmup_from_missing_feed(self) -> None:
        rows = [
            {
                "model": "team_shots_v4",
                "match_id": "fixture-1",
                "signal_status": "blocked",
                "blocked_reason": "matchdays_1_to_3",
                "matchday": "2",
            },
            {
                "model": "team_shots_v4",
                "match_id": "fixture-1",
                "signal_status": "blocked",
                "blocked_reason": "matchdays_1_to_3;edge_below_3pct",
                "matchday": "2",
            },
        ]

        summary = GATE["candidate_diagnostics"](rows, "team_shots_v4")

        self.assertEqual(summary["state"], "EXPECTED_WARMUP_BLOCK")
        self.assertEqual(summary["scored_rows"], 2)
        self.assertEqual(summary["scored_fixtures"], 1)
        self.assertEqual(summary["edge_pass_but_warmup_blocked_fixtures"], 1)
        self.assertEqual(summary["blocker_rows"]["matchdays_1_to_3"], 2)
        self.assertEqual(summary["next_unlock"], "matchday_4")

    def test_diagnostics_fail_closed_when_no_candidates_were_scored(self) -> None:
        summary = GATE["candidate_diagnostics"]([], "corners_v3")

        self.assertEqual(summary["state"], "NO_SCORED_CANDIDATES")
        self.assertEqual(summary["scored_rows"], 0)
        self.assertIsNone(summary["next_unlock"])

    def test_post_unlock_missing_lane_raises_operational_alert(self) -> None:
        missing = GATE["candidate_diagnostics"]([], "team_shots_v4")
        peer = GATE["candidate_diagnostics"](
            [
                {
                    "model": "corners_v3",
                    "match_id": "fixture-1",
                    "signal_status": "blocked",
                    "blocked_reason": "edge_below_3pct",
                    "matchday": "4",
                }
            ],
            "corners_v3",
        )

        GATE["reconcile_cross_model_alert"](missing, peer)

        self.assertEqual(missing["state"], "POST_UNLOCK_NO_SCORED_CANDIDATES")
        self.assertTrue(missing["operational_alert_required"])
        self.assertEqual(missing["operational_alert_code"], "POST_UNLOCK_NO_SCORED_CANDIDATES")
        self.assertEqual(peer["state"], "NO_EDGE_AFTER_UNLOCK")


if __name__ == "__main__":
    unittest.main()
