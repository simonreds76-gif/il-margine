from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pinnacle_corners_capture", SCRIPTS / "pinnacle-scrape-corners.py")
assert SPEC is not None and SPEC.loader is not None
CAPTURE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CAPTURE
SPEC.loader.exec_module(CAPTURE)


class PinnacleCornersCaptureTests(unittest.TestCase):
    def test_six_hour_buckets_retain_morning_and_evening_prices(self) -> None:
        self.assertEqual(CAPTURE._capture_bucket("2026-08-22T08:15:00Z"), "2026-08-22T06")
        self.assertEqual(CAPTURE._capture_bucket("2026-08-22T17:15:00Z"), "2026-08-22T12")

    def test_existing_keys_use_capture_bucket_not_calendar_day(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "corners.csv"
            path.write_text(
                "captured_at,match_date,home_team,away_team,line,side\n"
                "2026-08-22T08:15:00Z,2026-08-22,Arsenal,Chelsea,10.5,over\n"
                "2026-08-22T17:15:00Z,2026-08-22,Arsenal,Chelsea,10.5,over\n",
                encoding="utf-8",
            )
            keys = CAPTURE._load_existing_keys(path)
            self.assertEqual(len(keys), 2)

    def test_synthetic_corners_participants_are_not_a_second_fixture(self) -> None:
        matchup = {
            "id": 123,
            "type": "matchup",
            "startTime": "2026-08-22T15:00:00Z",
            "participants": [
                {"alignment": "home", "name": "Arsenal (Corners)"},
                {"alignment": "away", "name": "Chelsea (Corners)"},
            ],
        }
        with patch.object(CAPTURE, "_get", return_value=[matchup]):
            rows = CAPTURE._scrape_league(
                "epl", 1980, "2026-08-22T10:00:00Z", False
            )
        self.assertEqual(rows, [])

    def test_matchup_fetch_failure_is_reported_to_caller(self) -> None:
        failed: list[str] = []
        with patch.object(CAPTURE, "_get", side_effect=RuntimeError("blocked")):
            rows = CAPTURE._scrape_league(
                "la-liga", 2196, "2026-08-22T10:00:00Z", False, 0, failed
            )
        self.assertEqual(rows, [])
        self.assertEqual(failed, ["la-liga"])


if __name__ == "__main__":
    unittest.main()
