import importlib.util
import json
import subprocess
import unittest
from unittest import mock
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("hosted", Path(__file__).resolve().parents[1] / "goalscorer-live-hosted.py")
HOSTED = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HOSTED)


class BoardPriceRefreshTests(unittest.TestCase):
    def test_scheduled_board_only_run_keeps_request_cap_and_skips_db_and_research(self):
        plan = {"leagues": [{"league": "epl", "tier": "off", "active_fixture_count": 0, "upcoming_fixture_count": 1}]}
        commands = []
        def run(args):
            commands.append(args)
            return subprocess.CompletedProcess(args, 0, json.dumps(plan) if "goalscorer-live-schedule.py" in args[1] else "", "")
        with mock.patch.dict(HOSTED.os.environ, {"GOALSCORER_LINEUP_ONLY": "0", "GOALSCORER_FORCE_REFRESH": "0", "ENABLE_SUPABASE_SNAPSHOT_UPLOADS": "1", "SUPABASE_SERVICE_ROLE_KEY": "test", "NEXT_PUBLIC_SUPABASE_URL": "https://example.invalid"}), mock.patch.object(HOSTED, "LEAGUES", ["epl"]), mock.patch.object(HOSTED, "read_json", return_value={}), mock.patch.object(HOSTED, "write_json"), mock.patch.object(HOSTED, "write_status"), mock.patch.object(HOSTED, "csv_has_data_rows", return_value=True), mock.patch.object(HOSTED, "preferred_player_log", return_value=Path("history.csv")), mock.patch.object(HOSTED, "refresh_assist_from_confirmed_lineups", return_value=[]), mock.patch.object(HOSTED, "run_cmd", side_effect=run):
            self.assertEqual(HOSTED.main(), 0)
        pipeline = next(c for c in commands if c[1].endswith("run-goalscorer-pipeline.py"))
        self.assertEqual(pipeline[pipeline.index("--odds-api-max-http-requests") + 1], "3")
        self.assertEqual(pipeline[pipeline.index("--odds-api-days-ahead") + 1], "3")
        self.assertTrue(all("--supabase" not in c for c in commands))
        self.assertFalse(any("penalty-review" in c[1] or "clv-monitor" in c[1] for c in commands))

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
