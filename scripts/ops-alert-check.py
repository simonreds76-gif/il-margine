#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
ENV_FILES = [ROOT / ".env.local", ROOT / "env.local"]
FOOTBALL_VNEXT_GATE = ROOT / "data" / "football-form" / "football-counts-vnext-gate.json"
VERCEL_ISR_POLICY_GUARD = ROOT / "scripts" / "audit-vercel-isr-policy.py"
LONDON_TZ = ZoneInfo("Europe/London")
PINNACLE_PIPELINE = "pinnacle-capture-history"
PINNACLE_SLOT_START = time(hour=8, minute=0)
PINNACLE_SLOT_END = time(hour=23, minute=30)
PINNACLE_SLOT_INTERVAL = timedelta(minutes=30)
# GitHub scheduled workflows are best-effort and can be delayed/skipped,
# especially near busy cron boundaries. Alert on real drift, not cron jitter.
PINNACLE_GRACE = timedelta(minutes=int(os.environ.get("OPS_ALERT_PINNACLE_GRACE_MINUTES", "180")))
PINNACLE_SLOT_TOLERANCE = timedelta(
    minutes=int(os.environ.get("OPS_ALERT_PINNACLE_SLOT_TOLERANCE_MINUTES", "5"))
)

# The database view intentionally exposes every run older than 15 minutes.
# Long local OnCourt pipelines need a higher alert ceiling because their
# bounded extraction/model stages routinely exceed that global floor.
PIPELINE_STUCK_LIMITS_SECONDS = {
    "oncourt-daily": 90 * 60,
    "oncourt-am-refresh": 60 * 60,
    "oncourt-weekly": 180 * 60,
}


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


def get_database_url() -> str:
    return (os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL") or "").strip()


def fetch_rows_via_rest(
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


def fetch_rows_via_db(*, database_url: str, sql: str) -> list[dict[str, Any]]:
    try:
        import psycopg2
    except ImportError as exc:
        raise RuntimeError("psycopg2-binary is required for DATABASE_URL-backed alert checks") from exc

    try:
        conn = psycopg2.connect(database_url, connect_timeout=10)
    except Exception as exc:
        raise RuntimeError(f"database connect failed: {exc}") from exc

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                columns = [desc[0] for desc in cur.description or []]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
    except Exception as exc:
        raise RuntimeError(f"database query failed: {exc}") from exc
    finally:
        try:
            conn.close()
        except Exception:
            pass


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


def parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def iter_pinnacle_slots(local_day) -> list[datetime]:
    slots: list[datetime] = []
    current = datetime.combine(local_day, PINNACLE_SLOT_START, tzinfo=LONDON_TZ)
    end = datetime.combine(local_day, PINNACLE_SLOT_END, tzinfo=LONDON_TZ)
    while current <= end:
        slots.append(current)
        current += PINNACLE_SLOT_INTERVAL
    return slots


def latest_due_pinnacle_slot(now_utc: datetime) -> datetime | None:
    cutoff_local = now_utc.astimezone(LONDON_TZ) - PINNACLE_GRACE
    candidate_days = [cutoff_local.date(), cutoff_local.date() - timedelta(days=1)]
    due_slots = [
        slot
        for day in candidate_days
        for slot in iter_pinnacle_slots(day)
        if slot <= cutoff_local
    ]
    if not due_slots:
        return None
    return max(due_slots)


def filter_schedule_aware_silent_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now_utc = datetime.now(timezone.utc)
    latest_pinnacle_slot = latest_due_pinnacle_slot(now_utc)
    filtered: list[dict[str, Any]] = []

    for row in rows:
        pipeline = str(row.get("pipeline") or "").strip()
        if pipeline != PINNACLE_PIPELINE:
            filtered.append(row)
            continue

        if latest_pinnacle_slot is None:
            continue

        last_started_at = parse_timestamp(row.get("last_started_at"))
        if last_started_at and last_started_at.astimezone(LONDON_TZ) >= (
            latest_pinnacle_slot - PINNACLE_SLOT_TOLERANCE
        ):
            continue
        filtered.append(row)

    return filtered


def filter_pipeline_aware_stuck_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep long-running pipelines only after their realistic alert ceiling."""
    filtered: list[dict[str, Any]] = []
    for row in rows:
        pipeline = str(row.get("pipeline") or "").strip()
        limit_seconds = PIPELINE_STUCK_LIMITS_SECONDS.get(pipeline)
        if limit_seconds is None:
            filtered.append(row)
            continue
        try:
            age_seconds = float(row.get("age_seconds"))
        except (TypeError, ValueError):
            filtered.append(row)
            continue
        if age_seconds >= limit_seconds:
            filtered.append(row)
    return filtered


def build_run_url() -> str | None:
    server_url = os.environ.get("GITHUB_SERVER_URL")
    repository = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if server_url and repository and run_id:
        return f"{server_url}/{repository}/actions/runs/{run_id}"
    return None


def load_football_model_alerts(path: Path = FOOTBALL_VNEXT_GATE) -> list[str]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    alerts: list[str] = []
    for model, label in (("team_shots_v4", "Team Shots v4"), ("corners_v3", "Corners v3")):
        scan = (payload.get(model) or {}).get("latest_scan") or {}
        if not scan.get("operational_alert_required"):
            continue
        alerts.append(
            f"{label}: {scan.get('operational_alert_code') or scan.get('state') or 'UNKNOWN'} "
            f"({scan.get('scored_rows', 0)} rows / {scan.get('scored_fixtures', 0)} fixtures scored)"
        )
    return alerts


def load_vercel_isr_policy_alerts(path: Path = VERCEL_ISR_POLICY_GUARD) -> list[str]:
    """Run the static ISR guard so caching regressions reach Telegram."""
    if not path.exists():
        return ["Vercel ISR guard missing"]
    try:
        result = subprocess.run(
            [sys.executable, str(path), "--json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [f"Vercel ISR guard could not run: {exc}"]
    if result.returncode == 0:
        return []
    try:
        payload = json.loads(result.stdout.strip())
        issues = payload.get("issues") or []
    except (json.JSONDecodeError, AttributeError):
        issues = []
    if not issues:
        detail = (result.stderr or result.stdout or "unknown failure").strip().splitlines()[-1]
        return [f"Vercel ISR policy failed: {detail}"]
    return [f"Vercel ISR policy: {issue}" for issue in issues]


def render_message(
    *,
    stuck: list[dict[str, Any]],
    silent: list[dict[str, Any]],
    model_alerts: list[str] | None = None,
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

    model_alerts = model_alerts or []
    lines.append(f"Model pipeline alerts: {len(model_alerts)}")
    lines.extend(f"- {alert}" for alert in model_alerts[:5])

    run_url = build_run_url()
    if run_url:
        lines.append(f"GitHub run: {run_url}")

    return "\n".join(lines)


def post_webhook(webhook_url: str, message: str) -> bool:
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
        return True
    except Exception as exc:
        print(f"Warning: webhook post failed: {exc}", file=sys.stderr)
        return False


def post_telegram(bot_token: str, chat_id: str, message: str) -> bool:
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response.read()
        return True
    except Exception as exc:
        print(f"Warning: telegram post failed: {exc}", file=sys.stderr)
        return False


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

    database_url = get_database_url()
    base_url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "").strip()
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    has_db = bool(database_url)
    has_rest = bool(base_url and service_role_key)

    if not has_db and not has_rest:
        print(
            "OPS_ALERT_ERROR missing DATABASE_URL/SUPABASE_DB_URL and NEXT_PUBLIC_SUPABASE_URL+SUPABASE_SERVICE_ROLE_KEY",
            file=sys.stderr,
        )
        return 2

    ignore_silent = parse_pipeline_list(args.ignore_silent_pipeline, "OPS_ALERT_IGNORE_SILENT_PIPELINES")
    ignore_stuck = parse_pipeline_list(args.ignore_stuck_pipeline, "OPS_ALERT_IGNORE_STUCK_PIPELINES")
    print(
        "OPS_ALERT_CONFIG "
        f"db={'yes' if has_db else 'no'} "
        f"rest={'yes' if has_rest else 'no'} "
        f"ignore_silent={','.join(sorted(ignore_silent)) or '-'} "
        f"ignore_stuck={','.join(sorted(ignore_stuck)) or '-'}"
    )

    stuck_rows: list[dict[str, Any]] | None = None
    silent_rows: list[dict[str, Any]] | None = None
    db_error: RuntimeError | None = None
    backend_used = "unknown"

    if database_url:
        try:
            stuck_rows = fetch_rows_via_db(
                database_url=database_url,
                sql="""
                select pipeline, host, trigger_kind, run_id::text as run_id, started_at, age_seconds
                from v_stuck_runs
                order by started_at asc
                """,
            )
            silent_rows = fetch_rows_via_db(
                database_url=database_url,
                sql="""
                select
                    pipeline,
                    expected_interval::text as expected_interval,
                    grace_interval::text as grace_interval,
                    last_started_at,
                    last_finished_at,
                    seconds_since_last_start
                from v_silent_pipelines
                order by pipeline asc
                """,
            )
            backend_used = "database"
        except RuntimeError as exc:
            db_error = exc

    if stuck_rows is None or silent_rows is None:
        if base_url and service_role_key:
            try:
                stuck_rows = fetch_rows_via_rest(
                    base_url=base_url,
                    service_role_key=service_role_key,
                    view_name="v_stuck_runs",
                    query={
                        "select": "pipeline,host,trigger_kind,run_id,started_at,age_seconds",
                        "order": "started_at.asc",
                    },
                )
                silent_rows = fetch_rows_via_rest(
                    base_url=base_url,
                    service_role_key=service_role_key,
                    view_name="v_silent_pipelines",
                    query={
                        "select": "pipeline,expected_interval,grace_interval,last_started_at,last_finished_at,seconds_since_last_start",
                        "order": "pipeline.asc",
                    },
                )
                backend_used = "rest"
            except RuntimeError as exc:
                if db_error:
                    print(f"{db_error}; rest fallback failed: {exc}", file=sys.stderr)
                else:
                    print(str(exc), file=sys.stderr)
                return 2
        else:
            print(str(db_error), file=sys.stderr)
            return 2
    print(f"OPS_ALERT_BACKEND {backend_used}")

    stuck = [row for row in stuck_rows if row.get("pipeline") not in ignore_stuck]
    stuck = filter_pipeline_aware_stuck_rows(stuck)
    silent = [row for row in silent_rows if row.get("pipeline") not in ignore_silent]
    silent = filter_schedule_aware_silent_rows(silent)
    model_alerts = load_football_model_alerts() + load_vercel_isr_policy_alerts()

    if not stuck and not silent and not model_alerts:
        print("OPS_ALERT_OK stuck=0 silent=0 model_alerts=0")
        return 0

    message = render_message(stuck=stuck, silent=silent, model_alerts=model_alerts)
    print(message)

    bot_token = os.environ.get("OPS_ALERT_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("OPS_ALERT_TELEGRAM_CHAT_ID", "").strip()
    if bot_token and chat_id:
        if post_telegram(bot_token, chat_id, message):
            print("OPS_ALERT_TELEGRAM sent")
        else:
            print("OPS_ALERT_TELEGRAM failed", file=sys.stderr)
    else:
        print("OPS_ALERT_TELEGRAM skipped missing creds")

    webhook_url = os.environ.get("OPS_ALERT_WEBHOOK_URL", "").strip()
    if webhook_url:
        if post_webhook(webhook_url, message):
            print("OPS_ALERT_WEBHOOK sent")
        else:
            print("OPS_ALERT_WEBHOOK failed", file=sys.stderr)
    else:
        print("OPS_ALERT_WEBHOOK skipped missing creds")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
