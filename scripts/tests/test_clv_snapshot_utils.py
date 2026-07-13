from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from clv_snapshot_utils import close_lag_minutes, is_true_close, snapshot_at_or_before, snapshot_price  # noqa: E402


class ClvSnapshotUtilsTests(unittest.TestCase):
    def test_close_is_last_snapshot_before_kickoff(self) -> None:
        kickoff = datetime(2026, 8, 15, 15, 0, tzinfo=UTC)
        items = [
            {"captured_at": kickoff - timedelta(hours=3), "odds": 1.95},
            {"captured_at": kickoff - timedelta(minutes=15), "odds": 1.87},
            {"captured_at": kickoff + timedelta(minutes=2), "odds": 1.80},
        ]
        close = snapshot_at_or_before(items, kickoff)
        self.assertEqual(snapshot_price(close), 1.87)
        self.assertEqual(close_lag_minutes(close, kickoff), 15.0)
        self.assertTrue(is_true_close(close_lag_minutes(close, kickoff)))

    def test_snapshot_older_than_two_hours_is_not_true_close(self) -> None:
        kickoff = datetime(2026, 8, 15, 15, 0, tzinfo=UTC)
        snapshot = {"captured_at": kickoff - timedelta(minutes=121), "odds": 1.95}
        lag = close_lag_minutes(snapshot, kickoff)
        self.assertEqual(lag, 121.0)
        self.assertFalse(is_true_close(lag))

    def test_post_kickoff_snapshot_has_no_valid_close_lag(self) -> None:
        kickoff = datetime(2026, 8, 15, 15, 0, tzinfo=UTC)
        snapshot = {"captured_at": kickoff + timedelta(minutes=1), "odds": 1.80}
        self.assertIsNone(close_lag_minutes(snapshot, kickoff))


if __name__ == "__main__":
    unittest.main()
