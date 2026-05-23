#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ENV_FILES = [ROOT / ".env.local", ROOT / "env.local"]
TERMINAL_STATUSES = ("ok", "failed", "timeout", "aborted")
CROSS_HOST_RECOVERY_PIPELINES = {"pinnacle-capture-history"}


def should_allow_cross_host_recovery(row: dict[str, Any]) -> bool:
    return (
        str(row.get("pipeline") or "") in CROSS_HOST_RECOVERY_PIPELINES
        and str(row.get("host") or "") != "github-actions"
    )


def build_cleanup_payload(
    *,
    row: dict[str, Any],
    successor: dict[str, Any],
    error_type: str,
    reason: str,
) -> dict[str, Any]:
    cleaned_at = datetime.now(timezone.utc).isoformat()
    message = (
        f"Marked aborted by cleanup-run-status-orphans because {reason} "
        f"{successor['run_id']} ({successor['status']}) started at "
        f"{successor['started_at']} for pipeline {row['pipeline']}."
    )
    return {
        "message": message,
        "patch": {
            "finished_at": cleaned_at,
            "status": "aborted",
            "error_type": error_type,
            "error_message": message,
            "details": {
                "orphan_cleanup": {
                    "cleaned_at": cleaned_at,
                    "successor_run_id": successor["run_id"],
                    "successor_status": successor["status"],
                    "successor_started_at": str(successor["started_at"]),
                    "successor_host": successor.get("host"),
                    "stale_host": row.get("host"),
                }
            },
        },
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


def rest_base_and_headers() -> tuple[str, dict[str, str]] | None:
    base_url = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL") or "").strip()
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or "").strip()
    if not base_url or not key:
        return None
    return base_url.rstrip("/"), {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def fetch_json_rest(path: str, query: dict[str, str]) -> list[dict[str, Any]]:
    rest = rest_base_and_headers()
    if rest is None:
        raise RuntimeError("missing Supabase REST credentials")
    base_url, headers = rest
    url = f"{base_url}/rest/v1/{path}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{path} query failed: HTTP {exc.code}: {body}") from exc
    data = json.loads(payload or "[]")
    if not isinstance(data, list):
        raise RuntimeError(f"{path} query returned unexpected payload")
    return data


def patch_rest(path: str, query: dict[str, str], payload: dict[str, Any]) -> None:
    rest = rest_base_and_headers()
    if rest is None:
        raise RuntimeError("missing Supabase REST credentials")
    base_url, headers = rest
    url = f"{base_url}/rest/v1/{path}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, default=str).encode("utf-8"),
        headers=headers,
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{path} patch failed: HTTP {exc.code}: {body}") from exc


def connect_db(database_url: str):
    try:
        import psycopg2
    except ImportError as exc:
        raise RuntimeError("psycopg2-binary is required for DATABASE_URL cleanup") from exc
    return psycopg2.connect(database_url, connect_timeout=10)


def cleanup_via_db(database_url: str, dry_run: bool) -> int:
    conn = connect_db(database_url)
    cleaned = 0
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select pipeline, host, trigger_kind, run_id::text as run_id, started_at, age_seconds
                    from v_stuck_runs
                    order by started_at asc
                    """
                )
                columns = [desc[0] for desc in cur.description or []]
                stuck_rows = [dict(zip(columns, row)) for row in cur.fetchall()]

                for row in stuck_rows:
                    cur.execute(
                        """
                        select run_id::text, status, host, started_at, finished_at
                        from run_status
                        where pipeline = %s
                          and host = %s
                          and started_at > %s
                          and status in ('ok', 'failed', 'timeout', 'aborted')
                        order by started_at desc
                        limit 1
                        """,
                        (row["pipeline"], row["host"], row["started_at"]),
                    )
                    successor = cur.fetchone()
                    error_type = "SupersededStaleRun"
                    reason = "a later terminal run"
                    if successor is None and should_allow_cross_host_recovery(row):
                        cur.execute(
                            """
                            select run_id::text, status, host, started_at, finished_at
                            from run_status
                            where pipeline = %s
                              and started_at > %s
                              and status in ('ok', 'failed', 'timeout', 'aborted')
                            order by started_at desc
                            limit 1
                            """,
                            (row["pipeline"], row["started_at"]),
                        )
                        successor = cur.fetchone()
                        error_type = "RecoveredByPeerHost"
                        reason = "a later terminal run on another host"
                    if successor is None:
                        continue
                    successor_row = dict(zip([desc[0] for desc in cur.description or []], successor))
                    payload = build_cleanup_payload(
                        row=row,
                        successor=successor_row,
                        error_type=error_type,
                        reason=reason,
                    )
                    print(f"ORPHAN {row['run_id']} -> aborted; {payload['message']}")
                    if dry_run:
                        cleaned += 1
                        continue
                    cur.execute(
                        """
                        update run_status
                        set finished_at = now(),
                            status = 'aborted',
                            error_type = %s,
                            error_message = %s,
                            details = details || %s::jsonb
                        where run_id = %s
                          and status = 'running'
                        """,
                        (
                            payload["patch"]["error_type"],
                            payload["patch"]["error_message"],
                            json.dumps(payload["patch"]["details"]),
                            row["run_id"],
                        ),
                    )
                    cleaned += cur.rowcount
    finally:
        conn.close()
    return cleaned


def cleanup_via_rest(dry_run: bool) -> int:
    stuck_rows = fetch_json_rest(
        "v_stuck_runs",
        {
            "select": "pipeline,host,trigger_kind,run_id,started_at,age_seconds",
            "order": "started_at.asc",
        },
    )
    cleaned = 0
    for row in stuck_rows:
        successors = fetch_json_rest(
            "run_status",
            {
                "select": "run_id,status,host,started_at,finished_at",
                "pipeline": f"eq.{row['pipeline']}",
                "host": f"eq.{row['host']}",
                "started_at": f"gt.{row['started_at']}",
                "status": f"in.({','.join(TERMINAL_STATUSES)})",
                "order": "started_at.desc",
                "limit": "1",
            },
        )
        error_type = "SupersededStaleRun"
        reason = "a later terminal run"
        if not successors and should_allow_cross_host_recovery(row):
            successors = fetch_json_rest(
                "run_status",
                {
                    "select": "run_id,status,host,started_at,finished_at",
                    "pipeline": f"eq.{row['pipeline']}",
                    "started_at": f"gt.{row['started_at']}",
                    "status": f"in.({','.join(TERMINAL_STATUSES)})",
                    "order": "started_at.desc",
                    "limit": "1",
                },
            )
            error_type = "RecoveredByPeerHost"
            reason = "a later terminal run on another host"
        if not successors:
            continue
        successor = successors[0]
        payload = build_cleanup_payload(
            row=row,
            successor=successor,
            error_type=error_type,
            reason=reason,
        )
        print(f"ORPHAN {row['run_id']} -> aborted; {payload['message']}")
        if dry_run:
            cleaned += 1
            continue
        patch_rest(
            "run_status",
            {"run_id": f"eq.{row['run_id']}", "status": "eq.running"},
            payload["patch"],
        )
        cleaned += 1
    return cleaned


def main(argv: list[str] | None = None) -> int:
    load_env_files()
    parser = argparse.ArgumentParser(
        description="Mark superseded run_status rows as aborted before alert checks."
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    database_url = get_database_url()
    if database_url:
        try:
            cleaned = cleanup_via_db(database_url, dry_run=args.dry_run)
            print(f"RUN_STATUS_ORPHAN_CLEANUP backend=database cleaned={cleaned} dry_run={args.dry_run}")
            return 0
        except RuntimeError as exc:
            print(f"database cleanup failed, falling back to REST: {exc}", file=sys.stderr)

    cleaned = cleanup_via_rest(dry_run=args.dry_run)
    print(f"RUN_STATUS_ORPHAN_CLEANUP backend=rest cleaned={cleaned} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
