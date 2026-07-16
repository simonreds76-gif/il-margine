from __future__ import annotations

import runpy
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = runpy.run_path(str(ROOT / "scripts" / "weekly-research-report.py"), run_name="weekly_research_report_test")


class WeeklyResearchReportTests(unittest.TestCase):
    def test_settled_ledger_summary_uses_real_stakes(self) -> None:
        rows = [
            {"settled": "1", "bet_outcome": "won", "stake": "0.5", "pnl_units": "1.0"},
            {"settled": "1", "bet_outcome": "lost", "stake": "1.0", "pnl_units": "-1.0"},
            {"settled": "", "bet_outcome": "", "stake": "1.0", "pnl_units": ""},
        ]
        summary = REPORT["settled_ledger_summary"](rows, stake_field="stake")
        self.assertEqual(summary["registered"], 3)
        self.assertEqual(summary["settled"], 2)
        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary["staked_units"], 1.5)
        self.assertEqual(summary["pnl_units"], 0.0)
        self.assertEqual(summary["roi_pct"], 0.0)

    def test_assist_summary_is_fail_closed(self) -> None:
        summary = REPORT["assist_value_research_summary"]()
        self.assertIn(summary["lane_status"], {"FROZEN_RESEARCH", "NOT_RUN"})
        self.assertIn("backtest_status", summary)
        self.assertIn("settlement_status", summary)
        self.assertIn("market_status", summary)
        self.assertIn("prospective", summary)

    def test_assist_workflow_has_a_fixed_weekly_api_ceiling(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "assist-value-shadow.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "10 7 * * 0,5,6"', workflow)
        self.assertIn("--max-events-per-league 10", workflow)
        self.assertIn("--max-odds-requests-per-league 1", workflow)
        self.assertIn("--disable-global-fallback", workflow)
        self.assertNotIn("SUPABASE_SERVICE_ROLE_KEY", workflow)
        self.assertNotIn("DATABASE_URL", workflow)

    def test_weekly_payload_includes_automation_budget(self) -> None:
        payload = REPORT["build_payload"]()
        self.assertIn("automation_budget", payload)


if __name__ == "__main__":
    unittest.main()
