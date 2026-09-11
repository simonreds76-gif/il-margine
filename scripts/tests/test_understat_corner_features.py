from __future__ import annotations

import importlib.util
import sys
import unittest
import tempfile
from unittest.mock import patch, Mock
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "understat-download-corner-features.py"
SPEC = importlib.util.spec_from_file_location("understat_corner_features", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class UnderstatCornerFeatureTests(unittest.TestCase):
    def test_downloads_only_completed_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.csv"
            fixtures = [{"id": "1", "isResult": True}, {"id": "2", "isResult": False}, {"id": "3"}]
            def response(url, **kwargs):
                if "getLeagueData" in url:
                    return {"dates": fixtures}
                self.assertTrue(url.endswith("/1"), url)
                return {"shots": {"h": [], "a": []}}
            argv = ["script", "--leagues", "epl", "--seasons", "2026", "--output", str(out), "--cache-dir", tmp, "--delay", "0"]
            with patch.object(sys, "argv", argv), patch.object(MODULE, "request_json", side_effect=response) as fetch:
                self.assertEqual(MODULE.main(), 0)
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(set(MODULE.load_existing(out)), {"1"})

    def test_404_is_not_retried_but_429_is(self) -> None:
        for status, expected_calls in [(404, 1), (429, 3)]:
            with self.subTest(status=status):
                response = Mock(status_code=status)
                response.raise_for_status.side_effect = MODULE.requests.HTTPError(response=response)
                with patch.object(MODULE.requests, "get", return_value=response) as get, patch.object(MODULE.time, "sleep"):
                    with self.assertRaises(MODULE.requests.HTTPError):
                        MODULE.request_json("https://example.test")
                    self.assertEqual(get.call_count, expected_calls)

    def test_parse_match_payload(self) -> None:
        payload = {
            "shots": {
                "h": [
                    {"Y": "0.10", "result": "BlockedShot", "date": "2025-08-10 15:00:00", "h_team": "Home", "a_team": "Away"},
                    {"Y": "0.50", "result": "Goal"},
                    {"Y": "0.72", "result": "MissedShots"},
                ],
                "a": [
                    {"Y": "0.55", "result": "BlockedShot"},
                    {"Y": "0.40", "result": "SavedShot"},
                ],
            }
        }
        row = MODULE.parse_match_payload(payload, match_id="1", league="epl", season=2025)
        self.assertEqual(row["home_shots"], 3)
        self.assertEqual(row["home_wide_shots"], 2)
        self.assertAlmostEqual(row["home_wide_share"], 2 / 3, places=6)
        self.assertEqual(row["home_blocked_shots"], 1)
        self.assertAlmostEqual(row["away_blocked_rate"], 0.5)
        self.assertEqual(row["date"], "2025-08-10")
        self.assertEqual(row["home_team"], "Home")

    def test_empty_shot_sides_are_safe(self) -> None:
        row = MODULE.parse_match_payload(
            {"shots": {"h": [], "a": []}},
            match_id="2",
            league="epl",
            season=2025,
            fixture={"datetime": "2025-08-11 18:00:00", "h": {"title": "H"}, "a": {"title": "A"}},
        )
        self.assertEqual(row["home_shots"], 0)
        self.assertEqual(row["away_wide_share"], 0.0)
        self.assertEqual(row["home_team"], "H")


if __name__ == "__main__":
    unittest.main()
