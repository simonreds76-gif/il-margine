import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "cleanup-run-status-orphans.py"
SPEC = importlib.util.spec_from_file_location("cleanup_run_status_orphans", SCRIPT)
assert SPEC and SPEC.loader
cleanup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cleanup)


class CleanupRunStatusOrphansTests(unittest.TestCase):
    def test_am_laptop_row_expires_after_safe_scheduler_buffer(self):
        row = {"pipeline": "oncourt-am-refresh", "host": "laptop-win", "age_seconds": 7201}
        self.assertTrue(cleanup.is_past_hard_timeout(row))
        payload = cleanup.build_hard_timeout_payload(row)
        self.assertEqual(payload["patch"]["status"], "timeout")
        self.assertEqual(payload["patch"]["error_type"], "SchedulerExecutionLimitExceeded")

    def test_am_laptop_row_is_not_closed_while_it_can_still_be_running(self):
        row = {"pipeline": "oncourt-am-refresh", "host": "laptop-win", "age_seconds": 7199}
        self.assertFalse(cleanup.is_past_hard_timeout(row))

    def test_unregistered_pipeline_is_never_hard_timed_out(self):
        row = {"pipeline": "goalscorer-hot-live", "host": "laptop-win", "age_seconds": 999999}
        self.assertFalse(cleanup.is_past_hard_timeout(row))

    def test_github_row_is_never_closed_by_laptop_scheduler_rule(self):
        row = {"pipeline": "oncourt-am-refresh", "host": "github-actions", "age_seconds": 999999}
        self.assertFalse(cleanup.is_past_hard_timeout(row))


if __name__ == "__main__":
    unittest.main()
