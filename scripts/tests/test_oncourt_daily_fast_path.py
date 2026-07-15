from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DAILY = (ROOT / "scripts" / "oncourt-daily.ps1").read_text(encoding="utf-8")
WEEKLY = (ROOT / "scripts" / "oncourt-weekly.ps1").read_text(encoding="utf-8")


class NightlyFastPathTests(unittest.TestCase):
    def test_nightly_uses_current_schedule_sync(self) -> None:
        self.assertIn('$syncArgs = @("--quick")', DAILY)
        self.assertNotIn('$syncArgs = @("--recent")', DAILY)

    def test_slow_model_refreshes_are_weekly_only(self) -> None:
        slow_commands = (
            "oncourt-compute-player-stats-extended.py",
            "scrape-tennisabstract-surface-speed.py",
            "handicap-calibration.py",
            "fit-spread-v1-model.py",
        )
        for command in slow_commands:
            with self.subTest(command=command):
                self.assertNotIn(command, DAILY)
                self.assertIn(command, WEEKLY)

    def test_daily_betting_outputs_remain_enabled(self) -> None:
        required_commands = (
            "run-daily-odds.py",
            "run-tennis-props-daily.py",
            "strict-policy-report.py",
            "oncourt-settle-nightly.ps1",
        )
        for command in required_commands:
            with self.subTest(command=command):
                self.assertIn(command, DAILY)


if __name__ == "__main__":
    unittest.main()
