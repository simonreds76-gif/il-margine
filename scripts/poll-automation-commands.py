#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ENV_FILES = (ROOT / ".env.local", ROOT / "env.local")
COMMAND_KEY = "automation.tennis_fair_odds_request"
AM_TASK = "IlMargine-Daily-AM"
NIGHT_TASK = "IlMargine-Daily"
ACTIVE_STATES = {"pending", "waiting", "dispatching", "started"}
READY_STATE = ROOT / "data" / "backtest" / "tennis-signal-generation-status.json"
DIGEST_STATE = ROOT / "data" / "backtest" / "tennis-daily-signal-digest-state.json"
DIGEST_SCRIPT = ROOT / "scripts" / "tennis-daily-signal-digest.py"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_env_files() -> None:
    for path in ENV_FILES:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def rest_config() -> tuple[str, dict[str, str]] | None:
    base = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL") or "").strip()
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not base or not key:
        return None
    return base.rstrip("/"), {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def request_json(method: str, query: dict[str, str], payload: dict[str, Any] | None = None) -> Any:
    config = rest_config()
    if config is None:
        raise RuntimeError("missing Supabase REST credentials")
    base, headers = config
    url = f"{base}/rest/v1/site_settings?{urllib.parse.urlencode(query)}"
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    if method == "PATCH":
        headers = {**headers, "Prefer": "return=minimal"}
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"site_settings {method} failed: HTTP {exc.code}: {detail}") from exc
    return json.loads(text or "[]") if text else None


def parse_command(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return dict(value)
    if not isinstance(value, str):
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return dict(parsed) if isinstance(parsed, dict) else None


def read_command() -> dict[str, Any] | None:
    rows = request_json("GET", {"select": "value", "key": f"eq.{COMMAND_KEY}", "limit": "1"})
    if not isinstance(rows, list) or not rows:
        return None
    return parse_command(rows[0].get("value"))


def write_command(command: dict[str, Any]) -> None:
    request_json(
        "PATCH",
        {"key": f"eq.{COMMAND_KEY}"},
        {"value": json.dumps(command, separators=(",", ":"))},
    )


def schtasks_executable() -> str:
    return str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "schtasks.exe")


def run_schtasks(args: list[str]) -> subprocess.CompletedProcess[str]:
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(
        [schtasks_executable(), *args],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=20,
        creationflags=creation_flags,
        check=False,
    )


def task_snapshot(task_name: str) -> dict[str, Any]:
    result = run_schtasks(["/Query", "/TN", task_name, "/FO", "LIST", "/V"])
    output = f"{result.stdout}\n{result.stderr}"
    if result.returncode != 0:
        return {"exists": False, "running": False, "last_result": None}
    running = bool(re.search(r"(?:^|\r?\n)Status:\s+Running\s*(?:\r?\n|$)", output, re.IGNORECASE))
    result_match = re.search(r"(?:^|\r?\n)Last Result:\s+(0x[0-9a-f]+|-?\d+)", output, re.IGNORECASE)
    last_result: int | None = None
    if result_match:
        try:
            last_result = int(result_match.group(1), 0)
        except ValueError:
            pass
    return {"exists": True, "running": running, "last_result": last_result}


def start_task(task_name: str) -> None:
    result = run_schtasks(["/Run", "/TN", task_name])
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "unknown schtasks error").strip()
        raise RuntimeError(detail)


def transition(command: dict[str, Any], state: str, **details: Any) -> dict[str, Any]:
    return {**command, "state": state, "updated_at": utc_now(), **details}


def read_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def delivery_details(command: dict[str, Any]) -> dict[str, Any]:
    started_at = parse_time(command.get("local_started_at"))
    ready = read_json_file(READY_STATE)
    ready_at = parse_time(ready.get("completed_at"))
    ready_date = str(ready.get("date") or "")
    if ready.get("status") != "ok" or not ready_date:
        raise RuntimeError("Fair-odds task finished without a ready signal-generation marker")
    if started_at and (ready_at is None or ready_at < started_at):
        raise RuntimeError("Fair-odds task finished without generating fresh signals for this request")

    state = read_json_file(DIGEST_STATE)
    dispatched_at = parse_time(state.get("dispatched_at"))
    dispatched_for_request = bool(
        state.get("date") == ready_date
        and dispatched_at is not None
        and (started_at is None or dispatched_at >= started_at)
    )
    if not dispatched_for_request:
        result = subprocess.run(
            [
                sys.executable,
                str(DIGEST_SCRIPT),
                "--date",
                ready_date,
                "--require-ready",
                "--force",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "unknown digest error").strip()
            raise RuntimeError(f"Telegram digest dispatch failed: {detail[-500:]}")
        state = read_json_file(DIGEST_STATE)
        dispatched_at = parse_time(state.get("dispatched_at"))
        if state.get("date") != ready_date or dispatched_at is None:
            raise RuntimeError("Telegram digest completed without recording its dispatch")

    signal_ids = state.get("signal_ids")
    signal_count = len(signal_ids) if isinstance(signal_ids, list) else 0
    return {
        "signal_date": ready_date,
        "signal_count": signal_count,
        "signal_generation_completed_at": ready.get("completed_at"),
        "telegram_status": "relay_queued",
        "telegram_dispatched_at": state.get("dispatched_at"),
    }


def process_command(command: dict[str, Any]) -> dict[str, Any] | None:
    state = str(command.get("state") or "")
    if state not in ACTIVE_STATES:
        return None

    am = task_snapshot(AM_TASK)
    night = task_snapshot(NIGHT_TASK)

    if state in {"pending", "waiting"}:
        if not am["exists"]:
            return transition(command, "failed", error=f"{AM_TASK} is not installed on the laptop")
        if am["running"] or night["running"]:
            active_task = AM_TASK if am["running"] else NIGHT_TASK
            return transition(command, "waiting", waiting_for=active_task)

        dispatching = transition(command, "dispatching", dispatching_at=utc_now())
        write_command(dispatching)
        try:
            start_task(AM_TASK)
        except Exception as exc:
            return transition(dispatching, "failed", error=str(exc))
        return transition(dispatching, "started", local_started_at=utc_now(), task=AM_TASK)

    if state == "dispatching":
        if am["running"]:
            return transition(command, "started", local_started_at=utc_now(), task=AM_TASK)
        dispatching_at = parse_time(command.get("dispatching_at"))
        if dispatching_at and (datetime.now(timezone.utc) - dispatching_at).total_seconds() < 300:
            return None
        return transition(command, "failed", error="Task dispatch did not reach a running state")

    started_at = parse_time(command.get("local_started_at"))
    if am["running"] or (started_at and (datetime.now(timezone.utc) - started_at).total_seconds() < 30):
        return None
    last_result = am.get("last_result")
    if last_result == 0:
        try:
            details = delivery_details(command)
        except Exception as exc:
            return transition(
                command,
                "failed",
                completed_at=utc_now(),
                last_result=last_result,
                error=str(exc),
            )
        return transition(
            command,
            "completed",
            completed_at=utc_now(),
            last_result=last_result,
            **details,
        )
    return transition(
        command,
        "failed",
        completed_at=utc_now(),
        last_result=last_result,
        error=f"{AM_TASK} finished with scheduler result {last_result}",
    )


def main() -> int:
    if os.name != "nt":
        print("AUTOMATION_COMMAND_POLLER skipped: Windows only")
        return 0
    load_env_files()
    if rest_config() is None:
        print("AUTOMATION_COMMAND_POLLER skipped: Supabase credentials unavailable", file=sys.stderr)
        return 0
    try:
        command = read_command()
        if command is None:
            return 0
        updated = process_command(command)
        if updated is not None:
            write_command(updated)
            print(f"AUTOMATION_COMMAND_POLLER request={updated.get('request_id')} state={updated.get('state')}")
        return 0
    except Exception as exc:
        print(f"AUTOMATION_COMMAND_POLLER failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
