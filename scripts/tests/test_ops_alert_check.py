from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "ops-alert-check.py"
SPEC = importlib.util.spec_from_file_location("ops_alert_check", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PipelineAwareStuckTests(unittest.TestCase):
    def test_daily_run_below_ninety_minutes_is_not_stuck(self) -> None:
        rows = [{"pipeline": "oncourt-daily", "age_seconds": 22.2 * 60}]
        self.assertEqual(MODULE.filter_pipeline_aware_stuck_rows(rows), [])

    def test_daily_run_above_ninety_minutes_is_stuck(self) -> None:
        row = {"pipeline": "oncourt-daily", "age_seconds": 91 * 60}
        self.assertEqual(MODULE.filter_pipeline_aware_stuck_rows([row]), [row])

    def test_short_pipeline_keeps_database_view_threshold(self) -> None:
        row = {"pipeline": "pinnacle-capture-history", "age_seconds": 16 * 60}
        self.assertEqual(MODULE.filter_pipeline_aware_stuck_rows([row]), [row])


if __name__ == "__main__":
    unittest.main()
