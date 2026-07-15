from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HEALTH = (ROOT / "scripts" / "tennis-health-check.ps1").read_text(encoding="utf-8")
DAILY_PROPS = (ROOT / "scripts" / "run-tennis-props-daily.py").read_text(encoding="utf-8")


class TennisBenchmarkRuntimeTests(unittest.TestCase):
    def test_health_watchdog_is_read_only(self) -> None:
        self.assertNotIn("Refresh-TennisPropsBenchmark", HEALTH)
        self.assertNotIn("tennis-props-compare-bet365.py", HEALTH)
        self.assertNotIn("tennis-props-market-observations.py", HEALTH)

    def test_daily_benchmark_has_a_hard_timeout(self) -> None:
        self.assertIn('"Update all-main-line Bet365 observation benchmark"', DAILY_PROPS)
        self.assertIn("timeout_seconds=300", DAILY_PROPS)
        self.assertIn("except subprocess.TimeoutExpired", DAILY_PROPS)


if __name__ == "__main__":
    unittest.main()
