import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "poll-automation-commands.py"
SPEC = importlib.util.spec_from_file_location("poll_automation_commands", SCRIPT)
assert SPEC and SPEC.loader
poller = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(poller)


class PollAutomationCommandsTests(unittest.TestCase):
    def test_pending_request_starts_am_task(self):
        command = {"request_id": "request-1", "state": "pending", "requested_at": poller.utc_now()}
        with (
            patch.object(poller, "task_snapshot", side_effect=[
                {"exists": True, "running": False, "last_result": 0},
                {"exists": True, "running": False, "last_result": 0},
            ]),
            patch.object(poller, "start_task") as start_task,
            patch.object(poller, "write_command") as write_command,
        ):
            updated = poller.process_command(command)

        self.assertEqual(updated["state"], "started")
        start_task.assert_called_once_with(poller.AM_TASK)
        self.assertEqual(write_command.call_args.args[0]["state"], "dispatching")

    def test_pending_request_waits_when_nightly_task_is_running(self):
        command = {"request_id": "request-2", "state": "pending", "requested_at": poller.utc_now()}
        with (
            patch.object(poller, "task_snapshot", side_effect=[
                {"exists": True, "running": False, "last_result": 0},
                {"exists": True, "running": True, "last_result": 0},
            ]),
            patch.object(poller, "start_task") as start_task,
        ):
            updated = poller.process_command(command)

        self.assertEqual(updated["state"], "waiting")
        self.assertEqual(updated["waiting_for"], poller.NIGHT_TASK)
        start_task.assert_not_called()

    def test_started_request_records_scheduler_failure(self):
        command = {
            "request_id": "request-3",
            "state": "started",
            "requested_at": "2026-08-15T08:00:00+00:00",
            "local_started_at": "2026-08-15T08:00:00+00:00",
        }
        with patch.object(poller, "task_snapshot", side_effect=[
            {"exists": True, "running": False, "last_result": 2},
            {"exists": True, "running": False, "last_result": 0},
        ]):
            updated = poller.process_command(command)

        self.assertEqual(updated["state"], "failed")
        self.assertEqual(updated["last_result"], 2)


if __name__ == "__main__":
    unittest.main()
