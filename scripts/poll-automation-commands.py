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
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ENV_FILES = (ROOT / ".env.local", ROOT / "env.local")
COMMAND_KEY = "automation.tennis_fair_odds_request"
AM_TASK = "IlMargine-Daily-AM"
MANUAL_TASK = "IlMargine-OnDemand"
PRIORITY_REQUEST = ROOT / "data/locks/tennis-on-demand-request.json"
MANUAL_STATUS = ROOT / "data/backtest/tennis-on-demand-status.json"
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

    refresh_started = parse_time(ready.get("started_at"))
    extracted_at = parse_time(ready.get("oncourt_extracted_at"))
    odds_floor = parse_time(ready.get("odds_not_before"))
    requested_at = parse_time(command.get("requested_at")) or started_at
    if not ready.get("refresh_id") or refresh_started is None or extracted_at is None or odds_floor is None:
        raise RuntimeError("Refresh finished without verified fresh OnCourt/odds metadata")
    if (requested_at and refresh_started < requested_at) or extracted_at < refresh_started or odds_floor < refresh_started:
        raise RuntimeError("Refresh inputs belong to an earlier run")

    state = read_json_file(DIGEST_STATE)
    dispatched_at = parse_time(state.get("dispatched_at"))
    dispatched_for_request = bool(
        state.get("date") == ready_date
        and dispatched_at is not None
        and (started_at is None or dispatched_at >= started_at)
    )
    checked_at = parse_time(state.get("checked_at") or state.get("updated_at"))
    if not dispatched_for_request and (checked_at is None or (started_at and checked_at < started_at)):
        raise RuntimeError("No fresh Telegram selection-check receipt; refusing to force a resend")

    signal_ids = state.get("signal_ids")
    signal_count = len(signal_ids) if isinstance(signal_ids, list) else 0
    return {
        "refresh_id": ready.get("refresh_id"),
        "oncourt_database_updated_at": ready.get("oncourt_database_updated_at"),
        "oncourt_extracted_at": ready.get("oncourt_extracted_at"),
        "odds_not_before": ready.get("odds_not_before"),
        "signal_date": ready_date,
        "signal_count": signal_count,
        "signal_generation_completed_at": ready.get("completed_at"),
        "telegram_status": "relay_queued" if dispatched_for_request else "checked_no_new",
        "telegram_dispatched_at": state.get("dispatched_at"),
    }


def write_priority(command: dict[str, Any]) -> None:
    PRIORITY_REQUEST.parent.mkdir(parents=True, exist_ok=True)
    payload = {"request_id": command["request_id"], "requested_at": command["requested_at"],
               "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()}
    temporary = PRIORITY_REQUEST.with_suffix(f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    temporary.replace(PRIORITY_REQUEST)


def clear_priority(command: dict[str, Any]) -> None:
    if read_json_file(PRIORITY_REQUEST).get("request_id") == command.get("request_id"):
        PRIORITY_REQUEST.unlink(missing_ok=True)


def manual_details(command: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    if receipt.get("request_id") != command.get("request_id") or receipt.get("state") != "completed":
        raise RuntimeError(receipt.get("error") or "Manual task stopped without its completed receipt")
    requested = parse_time(command.get("requested_at"))
    started = parse_time(receipt.get("started_at"))
    extracted = parse_time(receipt.get("oncourt_extracted_at"))
    odds = parse_time(receipt.get("odds_not_before"))
    completed = parse_time(receipt.get("completed_at"))
    if not receipt.get("refresh_id") or not all((requested, started, extracted, odds, completed)):
        raise RuntimeError("Missing fresh-input evidence for manual completion")
    if not (requested <= started <= extracted <= completed and started <= odds <= completed):
        raise RuntimeError("Manual input receipt belongs to an earlier run")
    if receipt.get("telegram_status") not in {"relay_queued", "checked_no_new"}:
        raise RuntimeError("Manual task did not verify its Telegram selection checks")
    return {key: value for key, value in receipt.items() if key not in {"state", "request_id", "requested_at"}}


def process_command(command: dict[str, Any]) -> dict[str, Any] | None:
    state = str(command.get("state") or "")
    if state not in ACTIVE_STATES:
        return None
    task_name = str(command.get("task") or MANUAL_TASK)
    # Fixed allowlist; never run a task name supplied arbitrarily through the DB.
    if task_name not in {MANUAL_TASK, AM_TASK}:
        return transition(command, "failed", error="Unknown refresh task")
    task = task_snapshot(task_name)
    if state in {"pending", "waiting"}:
        if not task["exists"]:
            return transition(command, "failed", error=f"{task_name} is not installed on the laptop")
        if task["running"]:
            return transition(command, "waiting", waiting_for=task_name)
        write_priority(command)
        dispatching = transition(command, "dispatching", task=MANUAL_TASK, dispatching_at=utc_now())
        try:
            write_command(dispatching)
            start_task(MANUAL_TASK)
        except Exception as exc:
            clear_priority(command)
            return transition(dispatching, "failed", error=str(exc))
        return transition(dispatching, "started", local_started_at=utc_now(),
                          progress_message="Queued for exclusive input access; historical reports yield between steps.")

    receipt = read_json_file(MANUAL_STATUS) if task_name == MANUAL_TASK else {}
    matched = receipt.get("request_id") == command.get("request_id")
    if state == "dispatching" and task["running"]:
        command = transition(command, "started", local_started_at=command.get("dispatching_at") or utc_now())
    if task["running"]:
        if matched:
            details = {k: v for k, v in receipt.items() if k not in {"state", "request_id", "requested_at", "updated_at"}}
            if any(command.get(k) != v for k, v in details.items()):
                return transition(command, "started", **details)
        return command if state == "dispatching" else None
    started_at = parse_time(command.get("local_started_at") or command.get("dispatching_at"))
    if started_at and (datetime.now(timezone.utc) - started_at).total_seconds() < 30:
        return None
    try:
        if task.get("last_result") != 0:
            raise RuntimeError((receipt.get("error") if matched else None) or f"{task_name} finished with scheduler result {task.get('last_result')}")
        details = manual_details(command, receipt) if task_name == MANUAL_TASK else delivery_details(command)
        return transition(command, "completed", last_result=0, **details)
    except Exception as exc:
        return transition(command, "failed", completed_at=utc_now(), last_result=task.get("last_result"), error=str(exc))
    finally:
        clear_priority(command)


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
