import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("hosted", Path(__file__).resolve().parents[1] / "goalscorer-live-hosted.py")
HOSTED = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HOSTED)


class BoardPriceRefreshTests(unittest.TestCase):
    def test_tomorrow_only_fixture_receives_full_tick_refresh(self):
        self.assertTrue(HOSTED.board_price_refresh_due({"upcoming_fixture_count": 1, "active_fixture_count": 0}, lineup_only=False, price_age=60))

    def test_lineup_only_and_recent_prices_do_not_add_requests(self):
        self.assertFalse(HOSTED.board_price_refresh_due({"upcoming_fixture_count": 1}, lineup_only=True, price_age=90))
        self.assertFalse(HOSTED.board_price_refresh_due({"upcoming_fixture_count": 1}, lineup_only=False, price_age=30))

    def test_finished_or_empty_league_does_not_refresh(self):
        self.assertFalse(HOSTED.board_price_refresh_due({"upcoming_fixture_count": 0}, lineup_only=False, price_age=None))

    def test_lineup_clock_cannot_replace_price_clock(self):
        previous = {"leagues": {"epl": {"last_successful_run_at": "2026-09-13T14:40:00Z", "last_price_run_at": "2026-09-13T13:10:00Z"}}}
        result = HOSTED.build_default_state(previous)["epl"]
        self.assertEqual(result["last_price_run_at"], "2026-09-13T13:10:00Z")
        self.assertNotEqual(result["last_price_run_at"], result["last_successful_run_at"])


if __name__ == "__main__":
    unittest.main()
