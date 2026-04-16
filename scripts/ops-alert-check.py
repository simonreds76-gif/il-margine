#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ENV_FILES = [ROOT / ".env.local", ROOT / "env.local"]


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


def get_required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def fetch_rows(
    *,
    base_url: str,
    service_role_key: str,
    view_name: str,
    query: dict[str, str],
) -> list[dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/rest/v1/{view_name}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(
        url,
        headers={
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{view_name} query failed: HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{view_name} query failed: {exc}") from exc

    data = json.loads(payload or "[]")
    if not isinstance(data, list):
        raise RuntimeError(f"{view_name} query returned unexpected payload")
    return data


def parse_pipeline_list(values: list[str], env_name: str) -> set[str]:
    parsed = {value.strip() for value in values if value.strip()}
    env_value = os.environ.get(env_name, "")
    if env_value.strip():
        parsed.update(part.strip() for part in env_value.split(",") if part.strip())
    return parsed


def format_seconds(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "-"
    if numeric < 60:
        return f"{round(numeric)}s"
    if numeric < 3600:
        return f"{numeric / 60:.1f}m"
    if numeric < 86400:
        return f"{numeric / 3600:.1f}h"
    return f"{numeric / 86400:.1f}d"


def build_run_url() -> str | None:
    server_url = os.environ.get("GITHUB_SERVER_URL")
    repository = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if server_url and repository and run_id:
        return f"{server_url}/{repository}/actions/runs/{run_id}"
    return None


def render_message(
    *,
    stuck: list[dict[str, Any]],
    silent: list[dict[str, Any]],
) -> str:
    lines: list[str] = []
    lines.append("Ops alert check found pipeline issues.")
    lines.append(f"Stuck runs: {len(stuck)}")
    for row in stuck[:5]:
        lines.append(
            f"- stuck {row.get('pipeline', 'unknown')} on {row.get('host', 'unknown')} "
            f"for {format_seconds(row.get('age_seconds'))}"
        )
    if len(stuck) > 5:
        lines.append(f"- ... plus {len(stuck) - 5} more stuck run(s)")

    lines.append(f"Silent pipelines: {len(silent)}")
    for row in silent[:5]:
        lines.append(
            f"- silent {row.get('pipeline', 'unknown')} "
            f"(last start {row.get('last_started_at') or 'never'}, "
            f"age {format_seconds(row.get('seconds_since_last_start'))})"
        )
    if len(silent) > 5:
        lines.append(f"- ... plus {len(silent) - 5} more silent pipeline(s)")

    run_url = build_run_url()
    if run_url:
        lines.append(f"GitHub run: {run_url}")

    return "\n".join(lines)


def post_webhook(webhook_url: str, message: str) -> None:
    payload = json.dumps({"text": message, "content": message}).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response.read()
    except Exception as exc:
        print(f"Warning: webhook post failed: {exc}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check run_status alert views and fail on issues.")
    parser.add_argument(
        "--ignore-silent-pipeline",
        action="append",
        default=[],
        help="Pipeline name to ignore in the silent-pipeline alert check. May be repeated.",
    )
    parser.add_argument(
        "--ignore-stuck-pipeline",
        action="append",
        default=[],
        help="Pipeline name to ignore in the stuck-run alert check. May be repeated.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    load_env_files()
    args = build_parser().parse_args(argv)

    try:
        base_url = get_required_env("NEXT_PUBLIC_SUPABASE_URL")
        service_role_key = get_required_env("SUPABASE_SERVICE_ROLE_KEY")
    except RuntimeError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    ignore_silent = parse_pipeline_list(args.ignore_silent_pipeline, "OPS_ALERT_IGNORE_SILENT_PIPELINES")
    ignore_stuck = parse_pipeline_list(args.ignore_stuck_pipeline, "OPS_ALERT_IGNORE_STUCK_PIPELINES")

    try:
        stuck_rows = fetch_rows(
            base_url=base_url,
            service_role_key=service_role_key,
            view_name="v_stuck_runs",
            query={
                "select": "pipeline,host,trigger_kind,run_id,started_at,age_seconds",
                "order": "started_at.asc",
            },
        )
        silent_rows = fetch_rows(
            base_url=base_url,
            service_role_key=service_role_key,
            view_name="v_silent_pipelines",
            query={
                "select": "pipeline,expected_interval,grace_interval,last_started_at,last_finished_at,seconds_since_last_start",
                "order": "pipeline.asc",
            },
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    stuck = [row for row in stuck_rows if row.get("pipeline") not in ignore_stuck]
    silent = [row for row in silent_rows if row.get("pipeline") not in ignore_silent]

    if not stuck and not silent:
        print("OPS_ALERT_OK stuck=0 silent=0")
        return 0

    message = render_message(stuck=stuck, silent=silent)
    print(message)

    webhook_url = os.environ.get("OPS_ALERT_WEBHOOK_URL", "").strip()
    if webhook_url:
        post_webhook(webhook_url, message)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
