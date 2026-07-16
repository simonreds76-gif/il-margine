from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "team_shots_capture_window",
    SCRIPTS / "team-shots-scrape-odds.py",
)
assert SPEC is not None and SPEC.loader is not None
CAPTURE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CAPTURE
SPEC.loader.exec_module(CAPTURE)


class FootballCaptureWindowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 15, 14, 0, tzinfo=UTC)

    def test_iso_kickoff_inside_window(self) -> None:
        self.assertTrue(
            CAPTURE.within_kickoff_window(
                "2026-08-15T15:15:00Z",
                90,
                now=self.now,
            )
        )

    def test_far_and_started_events_are_excluded(self) -> None:
        self.assertFalse(
            CAPTURE.within_kickoff_window(
                "2026-08-15T16:00:00Z",
                90,
                now=self.now,
            )
        )
        self.assertFalse(
            CAPTURE.within_kickoff_window(
                "2026-08-15T13:59:00Z",
                90,
                now=self.now,
            )
        )

    def test_unix_timestamp_is_supported(self) -> None:
        kickoff = datetime(2026, 8, 15, 15, 0, tzinfo=UTC)
        self.assertTrue(
            CAPTURE.within_kickoff_window(
                int(kickoff.timestamp()),
                90,
                now=self.now,
            )
        )

    def test_zero_disables_filter(self) -> None:
        self.assertTrue(CAPTURE.within_kickoff_window("not-a-date", 0, now=self.now))

    def test_odds_api_http_budget_includes_retries_and_fallbacks(self) -> None:
        response = object()
        CAPTURE.configure_odds_api_http_budget(1)
        try:
            with patch.object(CAPTURE.requests, "get", return_value=response) as request:
                self.assertIs(CAPTURE.odds_api_get("https://example.test"), response)
                with self.assertRaisesRegex(RuntimeError, "request budget exhausted"):
                    CAPTURE.odds_api_get("https://example.test/retry")
                request.assert_called_once()
        finally:
            CAPTURE.configure_odds_api_http_budget(0)


if __name__ == "__main__":
    unittest.main()
