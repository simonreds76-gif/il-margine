#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATUS_FILE = ROOT / "data" / "goalscorer" / "goalscorer-live-status.json"
DEFAULT_WORKFLOW_FILE = "goalscorer-hot-live.yml"
DEFAULT_BRANCH = "golden-with-speed-insights"

ACTIVE_STATUSES = {"queued", "in_progress", "pending", "requested", "waiting"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def age_minutes(value: str | None) -> float | None:
    parsed = parse_iso(value)
    if parsed is None:
        return None
    return (now_utc() - parsed).total_seconds() / 60.0


def github_request(
    method: str,
    url: str,
    *,
    token: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "il-margine-goalscorer-watchdog",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8") if resp.length != 0 else ""
    return json.loads(body) if body else {}


def load_hot_live_runs(repo: str, workflow_file: str, branch: str, token: str) -> list[dict[str, Any]]:
    url = (
        f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_file}/runs"
        f"?branch={branch}&per_page=10"
    )
    payload = github_request("GET", url, token=token)
    return payload.get("workflow_runs", []) if isinstance(payload, dict) else []


def dispatch_hot_live(repo: str, workflow_file: str, branch: str, token: str, reason: str) -> None:
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_file}/dispatches"
    github_request(
        "POST",
        url,
        token=token,
        payload={
            "ref": branch,
            "inputs": {
                "reason": reason,
            },
        },
    )


def dispatch_hot_live_with_retry(
    repo: str,
    workflow_file: str,
    branch: str,
    token: str,
    reason: str,
    *,
    attempts: int,
    retry_delay_seconds: float,
) -> None:
    attempts = max(1, attempts)
    retry_delay_seconds = max(0.0, retry_delay_seconds)

    for attempt in range(1, attempts + 1):
        try:
            dispatch_hot_live(repo, workflow_file, branch, token, reason)
            if attempt > 1:
                emit("notice", f"Goalscorer watchdog dispatch succeeded on attempt {attempt}/{attempts}.")
            return
        except urllib.error.HTTPError as exc:
            retryable = 500 <= exc.code <= 599
            if not retryable or attempt >= attempts:
                raise
            emit(
                "warning",
                f"Goalscorer watchdog dispatch got GitHub HTTP {exc.code}; retrying attempt {attempt + 1}/{attempts}.",
            )
        except urllib.error.URLError:
            if attempt >= attempts:
                raise
            emit("warning", f"Goalscorer watchdog dispatch hit a network error; retrying attempt {attempt + 1}/{attempts}.")

        if retry_delay_seconds:
            time.sleep(retry_delay_seconds * attempt)


def newest_status_age_minutes(status_payload: dict[str, Any] | None) -> float | None:
    if not status_payload:
        return None
    candidates = [
        age_minutes(status_payload.get("last_successful_finished_at")),
        age_minutes(status_payload.get("updated_at")),
    ]
    candidates = [value for value in candidates if value is not None]
    return min(candidates) if candidates else None


def emit(level: str, message: str) -> None:
    print(f"::{level}::{message}")


def load_lineup_plan() -> tuple[dict[str, Any] | None, bool]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "goalscorer-live-schedule.py"), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        emit(
            "warning",
            f"Goalscorer watchdog could not build lineup schedule; falling back to heartbeat dispatch. {proc.stderr.strip() or proc.stdout.strip()}",
        )
        return None, True
    try:
        return json.loads(proc.stdout or "{}"), False
    except json.JSONDecodeError:
        emit("warning", "Goalscorer watchdog got invalid lineup schedule JSON; falling back to heartbeat dispatch.")
        return None, True


def due_lineup_fixtures(plan: dict[str, Any] | None) -> tuple[int, list[str]]:
    if not isinstance(plan, dict):
        return 0, []
    due_count = 0
    labels: list[str] = []
    for league in plan.get("leagues", []):
        if not isinstance(league, dict):
            continue
        count = int(league.get("active_fixture_count") or 0)
        if count <= 0:
            continue
        due_count += count
        labels.append(f"{league.get('league')}:{count}")
    return due_count, labels


def main() -> int:
    parser = argparse.ArgumentParser(description="Hosted watchdog for the goalscorer hot-live workflow")
    parser.add_argument("--status-file", default=str(DEFAULT_STATUS_FILE))
    parser.add_argument("--workflow-file", default=DEFAULT_WORKFLOW_FILE)
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    parser.add_argument("--stale-minutes", type=float, default=35.0)
    parser.add_argument("--running-grace-minutes", type=float, default=25.0)
    parser.add_argument("--cooldown-minutes", type=float, default=20.0)
    parser.add_argument("--dispatch-attempts", type=int, default=3)
    parser.add_argument("--dispatch-retry-delay-seconds", type=float, default=8.0)
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not token or not repo:
        raise SystemExit("Set GITHUB_TOKEN and GITHUB_REPOSITORY for the hosted watchdog.")

    lineup_plan, schedule_error = load_lineup_plan()
    due_count, due_labels = due_lineup_fixtures(lineup_plan)
    if due_count <= 0 and not schedule_error:
        emit("notice", "No official-lineup windows are due; goalscorer watchdog stayed idle.")
        return 0
    if schedule_error:
        emit("warning", "Lineup schedule unavailable; using heartbeat freshness as the safety fallback.")
    else:
        emit("notice", f"Official-lineup window due for {due_count} fixture(s): {', '.join(due_labels)}.")

    status_payload = read_json(Path(args.status_file))
    status_state = str((status_payload or {}).get("state") or "").strip().lower()
    status_age = newest_status_age_minutes(status_payload)
    started_age = age_minutes((status_payload or {}).get("last_started_at"))

    try:
        runs = load_hot_live_runs(repo, args.workflow_file, args.branch, token)
    except urllib.error.URLError as exc:
        emit("warning", f"Goalscorer watchdog could not inspect workflow runs: {exc}")
        return 0

    active_run = next((run for run in runs if str(run.get("status") or "").strip().lower() in ACTIVE_STATUSES), None)
    latest_run = runs[0] if runs else None
    latest_run_age = age_minutes((latest_run or {}).get("updated_at"))

    if active_run:
        emit("notice", "Goalscorer hot-live workflow already active; watchdog did not dispatch a duplicate run.")
        return 0

    if status_state == "running" and started_age is not None and started_age <= args.running_grace_minutes:
        emit("notice", "Goalscorer status already reports a fresh running poll; watchdog stayed idle.")
        return 0

    if status_age is not None and status_age <= args.stale_minutes:
        emit("notice", f"Goalscorer heartbeat is fresh ({status_age:.1f}m old); watchdog stayed idle.")
        return 0

    if latest_run_age is not None and latest_run_age <= args.cooldown_minutes:
        emit(
            "warning",
            f"Goalscorer heartbeat looks stale, but the latest hot-live run was updated {latest_run_age:.1f}m ago; waiting out cooldown.",
        )
        return 0

    reason = "watchdog_stale_status"
    try:
        dispatch_hot_live_with_retry(
            repo,
            args.workflow_file,
            args.branch,
            token,
            reason,
            attempts=args.dispatch_attempts,
            retry_delay_seconds=args.dispatch_retry_delay_seconds,
        )
    except urllib.error.HTTPError as exc:
        emit("error", f"Goalscorer watchdog failed to dispatch hot-live workflow: HTTP {exc.code}")
        return 1
    except urllib.error.URLError as exc:
        emit("error", f"Goalscorer watchdog failed to dispatch hot-live workflow: {exc}")
        return 1

    stale_text = "missing heartbeat" if status_age is None else f"stale heartbeat ({status_age:.1f}m old)"
    emit("warning", f"Goalscorer watchdog dispatched a fresh hot-live run because of {stale_text}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
