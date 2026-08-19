import importlib.util
import json
import subprocess
import tempfile
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

    def test_started_request_records_signal_and_telegram_completion(self):
        command = {
            "request_id": "request-4",
            "state": "started",
            "requested_at": "2026-08-15T08:00:00+00:00",
            "local_started_at": "2026-08-15T08:00:00+00:00",
        }
        delivery = {
            "signal_date": "2026-08-15",
            "signal_count": 3,
            "telegram_status": "relay_queued",
            "telegram_dispatched_at": "2026-08-15T08:12:00Z",
        }
        with (
            patch.object(poller, "task_snapshot", side_effect=[
                {"exists": True, "running": False, "last_result": 0},
                {"exists": True, "running": False, "last_result": 0},
            ]),
            patch.object(poller, "delivery_details", return_value=delivery),
        ):
            updated = poller.process_command(command)

        self.assertEqual(updated["state"], "completed")
        self.assertEqual(updated["signal_count"], 3)
        self.assertEqual(updated["telegram_status"], "relay_queued")

    def test_started_request_surfaces_telegram_failure(self):
        command = {
            "request_id": "request-5",
            "state": "started",
            "requested_at": "2026-08-15T08:00:00+00:00",
            "local_started_at": "2026-08-15T08:00:00+00:00",
        }
        with (
            patch.object(poller, "task_snapshot", side_effect=[
                {"exists": True, "running": False, "last_result": 0},
                {"exists": True, "running": False, "last_result": 0},
            ]),
            patch.object(poller, "delivery_details", side_effect=RuntimeError("relay failed")),
        ):
            updated = poller.process_command(command)

        self.assertEqual(updated["state"], "failed")
        self.assertIn("relay failed", updated["error"])

    def test_delivery_details_does_not_resend_current_dispatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ready_path = Path(temp_dir) / "ready.json"
            digest_path = Path(temp_dir) / "digest.json"
            ready_path.write_text(
                json.dumps({
                    "date": "2026-08-15",
                    "status": "ok",
                    "completed_at": "2026-08-15T08:10:00Z",
                }),
                encoding="utf-8",
            )
            digest_path.write_text(
                json.dumps({
                    "date": "2026-08-15",
                    "signal_ids": ["a", "b"],
                    "dispatched_at": "2026-08-15T08:11:00Z",
                }),
                encoding="utf-8",
            )
            command = {"local_started_at": "2026-08-15T08:00:00Z"}
            with (
                patch.object(poller, "READY_STATE", ready_path),
                patch.object(poller, "DIGEST_STATE", digest_path),
                patch.object(poller.subprocess, "run") as run,
            ):
                details = poller.delivery_details(command)

        run.assert_not_called()
        self.assertEqual(details["signal_count"], 2)
        self.assertEqual(details["telegram_status"], "relay_queued")

    def test_delivery_details_forces_digest_when_manual_run_was_suppressed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ready_path = Path(temp_dir) / "ready.json"
            digest_path = Path(temp_dir) / "digest.json"
            ready_path.write_text(
                json.dumps({
                    "date": "2026-08-15",
                    "status": "ok",
                    "completed_at": "2026-08-15T08:10:00Z",
                }),
                encoding="utf-8",
            )
            digest_path.write_text(
                json.dumps({
                    "date": "2026-08-15",
                    "signal_ids": ["a"],
                    "dispatched_at": "2026-08-15T07:00:00Z",
                }),
                encoding="utf-8",
            )

            def force_digest(*_args, **_kwargs):
                digest_path.write_text(
                    json.dumps({
                        "date": "2026-08-15",
                        "signal_ids": ["a"],
                        "dispatched_at": "2026-08-15T08:12:00Z",
                    }),
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess([], 0, "ok", "")

            command = {"local_started_at": "2026-08-15T08:00:00Z"}
            with (
                patch.object(poller, "READY_STATE", ready_path),
                patch.object(poller, "DIGEST_STATE", digest_path),
                patch.object(poller.subprocess, "run", side_effect=force_digest) as run,
            ):
                details = poller.delivery_details(command)

        self.assertIn("--force", run.call_args.args[0])
        self.assertEqual(details["telegram_dispatched_at"], "2026-08-15T08:12:00Z")


if __name__ == "__main__":
    unittest.main()
