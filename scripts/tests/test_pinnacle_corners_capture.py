from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
