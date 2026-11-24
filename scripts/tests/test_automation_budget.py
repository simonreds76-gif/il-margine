from __future__ import annotations

import json
import io
import runpy
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT = runpy.run_path(str(ROOT / "scripts" / "audit-automation-budget.py"), run_name="automation_budget_test")
CONFIG = json.loads((ROOT / "config" / "automation-budget.json").read_text(encoding="utf-8"))


class AutomationBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effective = ROOT / ".effective-default-branch" / ".github" / "workflows"
        if cls.effective.is_dir():
            return
        # The report code and the schedules it audits live on different branches.
        scratch = tempfile.TemporaryDirectory()
        cls.addClassCleanup(scratch.cleanup)
        cls.effective = Path(scratch.name)
        archive = subprocess.check_output(["git", "archive", "origin/main", ".github/workflows"], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            for item in tar:
                path = Path(item.name)
                if item.isfile() and path.parent.as_posix() == ".github/workflows" and path.suffix in (".yml", ".yaml"):
                    (cls.effective / path.name).write_bytes(tar.extractfile(item).read())

    def test_all_scheduled_workflows_are_registered_and_within_limits(self) -> None:
        report = AUDIT["build_report"](CONFIG, self.effective, state_for=lambda _: "disabled_manually")
        self.assertEqual(report["status"], "PASS", report["errors"])
        self.assertEqual(report["errors"], [])
        self.assertLessEqual(
            report["providers"]["odds_api_io"]["max_requests_in_one_hour"],
            report["providers"]["odds_api_io"]["requests_per_hour"],
        )
        self.assertLessEqual(
            report["providers"]["odds_api_io"]["max_requests_in_one_day"],
            report["providers"]["odds_api_io"]["requests_per_day"],
        )
        self.assertLessEqual(
            report["providers"]["api_football"]["max_requests_in_one_day"],
            report["providers"]["api_football"]["requests_per_day"],
        )

    def test_explicit_effective_workflow_directory_is_reported(self) -> None:
        workflows = self.effective
        report = AUDIT["build_report"](CONFIG, workflows, state_for=lambda _: "disabled_manually")
        self.assertEqual(report["workflow_directory"], str(workflows))
        self.assertEqual(report["status"], "PASS", report["errors"])

    def test_only_a_verified_disabled_pilot_is_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "pilot.yaml").write_text("on:\n  schedule:\n    - cron: '0 10 20-24 11 *'\n")
            cfg = {"github_workflows": [], "provider_limits": {}, "expected_disabled_workflows": ["pilot.yaml"]}
            for state in ("active", "unverified", "disabled_manually"):
                result = AUDIT["build_report"](cfg, folder, state_for=lambda name: state)
                self.assertEqual(result["status"], "PASS" if state == "disabled_manually" else "FAIL")
            cfg["expected_disabled_workflows"] = []
            self.assertEqual(AUDIT["build_report"](cfg, folder)["status"], "FAIL")

    def test_drop_desk_and_bookings_have_separate_provider_envelopes(self):
        report = AUDIT["build_report"](CONFIG, self.effective, state_for=lambda _: "disabled_manually")
        self.assertEqual(report["providers"]["tennis_board"]["max_requests_in_one_day"], 96)
        self.assertEqual(report["providers"]["football_research"]["max_requests_in_one_day"], 268)
        self.assertIsNone(report["database"]["registered_reads_per_week_max"])

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
        tennis_scraper = (ROOT / "scripts" / "tennis-props-scrape-bet365.py").read_text(encoding="utf-8")
        self.assertIn("--max-odds-requests-per-league 1", counts_workflow)
        self.assertIn("--max-odds-requests-per-league 2", counts_workflow)
        self.assertIn('cron: "45 9-22 * * *"', counts_workflow)
        self.assertIn("--max-odds-api-http-requests 9", counts_workflow)
        self.assertIn("--max-odds-api-http-requests 50", counts_workflow)
        self.assertIn('"--max-odds-requests-per-league"', scraper)
        self.assertIn('"--max-odds-api-http-requests"', scraper)
        self.assertIn("Odds-API.io HTTP request budget exhausted", scraper)
        self.assertIn("github.event.schedule == '25 11 * * *'", tennis)
        self.assertIn("if args.probe_markets:", tennis_scraper)
        self.assertNotIn("if args.probe_markets or not rows:", tennis_scraper)
        self.assertEqual(CONFIG["provider_limits"]["odds_api_io"]["requests_per_day"], 500)

    def test_goalscorer_refreshes_are_scheduled_and_capped(self) -> None:
        expected = (ROOT / ".github" / "workflows" / "goalscorer-expected-refresh.yml").read_text(encoding="utf-8")
        hot = (ROOT / ".github" / "workflows" / "goalscorer-hot-live.yml").read_text(encoding="utf-8")
        settlement = (ROOT / ".github" / "workflows" / "goalscorer-settlement.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "45 6 * * *"', expected)
        self.assertIn("--odds-api-max-http-requests 3", expected)
        self.assertIn('cron: "10 10-22 * * *"', hot)
        self.assertIn('cron: "40 10-22 * * *"', hot)
        self.assertIn("GOALSCORER_LINEUP_ONLY", hot)
        self.assertIn("GOALSCORER_FORCE_REFRESH", hot)
        self.assertIn('cron: "45 8 * * *"', settlement)


if __name__ == "__main__":
    unittest.main()
