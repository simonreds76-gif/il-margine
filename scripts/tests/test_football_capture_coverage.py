from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "football_capture_coverage",
    SCRIPTS / "football-counts-capture-coverage.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FootballCaptureCoverageTests(unittest.TestCase):
    def test_latest_pre_kickoff_snapshot_drives_coverage(self) -> None:
        now = datetime(2026, 8, 15, 18, tzinfo=UTC)
        kickoff = now - timedelta(hours=2)
        fixtures = {
            "one": {
                "kickoff": kickoff,
                "captures": {
                    kickoff - timedelta(hours=4),
                    kickoff - timedelta(minutes=25),
                    kickoff + timedelta(minutes=5),
                },
            }
        }
        summary = MODULE.summarize(fixtures, now=now, lookback_days=14, target=0.70)
        self.assertEqual(summary["true_close_fixtures"], 1)
        self.assertEqual(summary["median_close_lag_minutes"], 25.0)
        self.assertTrue(summary["passes"])

    def test_stale_only_snapshot_fails(self) -> None:
        now = datetime(2026, 8, 15, 18, tzinfo=UTC)
        kickoff = now - timedelta(hours=2)
        fixtures = {
            "one": {
                "kickoff": kickoff,
                "captures": {kickoff - timedelta(minutes=121)},
            }
        }
        summary = MODULE.summarize(fixtures, now=now, lookback_days=14, target=0.50)
        self.assertEqual(summary["true_close_coverage"], 0.0)
        self.assertFalse(summary["passes"])


if __name__ == "__main__":
    unittest.main()
