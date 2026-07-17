from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PIPELINE = (ROOT / "scripts" / "run-daily-odds.py").read_text(encoding="utf-8")


class DailyOddsRecentActivityTests(unittest.TestCase):
    def test_refresh_runs_before_fair_odds(self) -> None:
        refresh = PIPELINE.index("oncourt-compute-recent-activity.py")
        fair_odds = PIPELINE.index("oncourt-compute-fair-odds.py")
        self.assertLess(refresh, fair_odds)

    def test_refresh_is_fail_closed_by_default(self) -> None:
        refresh_block = PIPELINE[PIPELINE.index("oncourt-compute-recent-activity.py") :]
        self.assertIn("fatal=True", refresh_block[:400])
        self.assertIn("--skip-recent-activity", PIPELINE)


if __name__ == "__main__":
    unittest.main()
