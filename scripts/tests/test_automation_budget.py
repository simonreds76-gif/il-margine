from __future__ import annotations

import json
import runpy
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT = runpy.run_path(str(ROOT / "scripts" / "audit-automation-budget.py"), run_name="automation_budget_test")
CONFIG = json.loads((ROOT / "config" / "automation-budget.json").read_text(encoding="utf-8"))


class AutomationBudgetTests(unittest.TestCase):
    def test_all_scheduled_workflows_are_registered_and_within_limits(self) -> None:
        report = AUDIT["build_report"](CONFIG)
        self.assertEqual(report["status"], "PASS", report["errors"])
        self.assertEqual(report["errors"], [])
        self.assertLessEqual(
            report["providers"]["odds_api_io"]["max_requests_in_one_hour"],
            report["providers"]["odds_api_io"]["requests_per_hour"],
        )
        self.assertLessEqual(
            report["providers"]["api_football"]["max_requests_in_one_day"],
            report["providers"]["api_football"]["requests_per_day"],
        )

    def test_explicit_effective_workflow_directory_is_reported(self) -> None:
        workflows = ROOT / ".github" / "workflows"
        report = AUDIT["build_report"](CONFIG, workflows)
        self.assertEqual(report["workflow_directory"], str(workflows))
        self.assertEqual(report["status"], "PASS", report["errors"])

    def test_assist_collects_three_weekend_snapshots_without_database_access(self) -> None:
        workflow = next(row for row in CONFIG["github_workflows"] if row["file"] == "assist-value-shadow.yml")
        slots = AUDIT["expand_week"](workflow["schedules"][0]["cron"])
        self.assertEqual(len(slots), 3)
        self.assertEqual(workflow["database_mode"], "none")
        self.assertEqual(workflow["db_writes_max_per_run"], 0)

    def test_team_shots_and_tennis_have_hard_credit_caps(self) -> None:
        counts_workflow = (ROOT / ".github" / "workflows" / "football-counts-vnext-shadow.yml").read_text(encoding="utf-8")
        scraper = (ROOT / "scripts" / "team-shots-scrape-odds.py").read_text(encoding="utf-8")
        tennis = (ROOT / ".github" / "workflows" / "tennis-props-bet365-refresh.yml").read_text(encoding="utf-8")
        self.assertIn("--max-odds-requests-per-league 1", counts_workflow)
        self.assertIn("--max-odds-requests-per-league 2", counts_workflow)
        self.assertIn("--max-odds-api-http-requests 35", counts_workflow)
        self.assertIn("--max-odds-api-http-requests 50", counts_workflow)
        self.assertIn('"--max-odds-requests-per-league"', scraper)
        self.assertIn('"--max-odds-api-http-requests"', scraper)
        self.assertIn("Odds-API.io HTTP request budget exhausted", scraper)
        self.assertIn("github.event.schedule == '25 11 * * *'", tennis)
        self.assertEqual(CONFIG["provider_limits"]["odds_api_io"]["requests_per_day"], 500)


if __name__ == "__main__":
    unittest.main()
