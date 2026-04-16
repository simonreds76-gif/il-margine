"""Write-side pipeline observability.

Every pipeline entrypoint opens a run_status context manager. The context
writes a 'running' row on enter and updates it to 'ok' or 'failed' on exit.

Design rules:
- Never raise from the helper itself. Pipeline observability must not
  break the pipeline.
- If the database is unreachable or the DSN env var is unset, log a
  warning and continue silently. The pipeline still runs.
- psycopg2 is imported lazily inside _connect() so this module imports
  cleanly even on hosts that don't have psycopg2 installed.

Usage (Python callers):
    from scripts._lib.run_status import run_status

    with run_status("pinnacle-capture-history") as rs:
        rows = do_work()
        rs.rows_out = len(rows)
        rs.details["source_freshness_minutes"] = 5

If do_work() raises, the row is marked status='failed' with error_type,
error_message, and a tail of the traceback recorded in details. The
exception then propagates normally.

Environment variables:
    DATABASE_URL       Primary Postgres DSN. Preferred if set.
    SUPABASE_DB_URL    Fallback Postgres DSN. Used if DATABASE_URL is unset.
    RUN_STATUS_HOST    Optional override for the 'host' column. If unset,
                       host is inferred: 'github-actions' on GHA runners,
                       'laptop-win' on Windows, otherwise 'unknown'.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

log = logging.getLogger(__name__)

_CONNECT_TIMEOUT_SECONDS = 5
_HOST_ENV = "RUN_STATUS_HOST"


def _dsn() -> Optional[str]:
    return os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")


def _host() -> str:
    override = os.environ.get(_HOST_ENV)
    if override:
        return override
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return "github-actions"
    if os.name == "nt":
        return "laptop-win"
    return "unknown"


def _connect():
    dsn = _dsn()
    if not dsn:
        log.warning(
            "run_status disabled: neither DATABASE_URL nor SUPABASE_DB_URL is set"
        )
        return None
    try:
        import psycopg2

        return psycopg2.connect(dsn, connect_timeout=_CONNECT_TIMEOUT_SECONDS)
    except Exception as exc:
        log.warning("run_status connect failed: %s", exc)
        return None


def _json(d: dict) -> str:
    return json.dumps(d, default=str)


class RunHandle:
    """Mutable handle exposed to the `with` block."""

    __slots__ = ("run_id", "rows_in", "rows_out", "details")

    def __init__(self, run_id: uuid.UUID, details: dict):
        self.run_id: uuid.UUID = run_id
        self.rows_in: Optional[int] = None
        self.rows_out: Optional[int] = None
        self.details: dict = details


@contextlib.contextmanager
def run_status(
    pipeline: str,
    trigger_kind: str = "schedule",
    details: Optional[dict[str, Any]] = None,
) -> Iterator[RunHandle]:
    """Context manager for recording a pipeline run."""
    run_id = uuid.uuid4()
    handle = RunHandle(run_id=run_id, details=dict(details or {}))
    started = datetime.now(timezone.utc)

    _insert_running(run_id, pipeline, trigger_kind, started, handle.details)

    try:
        yield handle
    except BaseException as exc:
        _finalize(run_id, status="failed", handle=handle, error=exc)
        raise
    else:
        _finalize(run_id, status="ok", handle=handle)


def _insert_running(
    run_id: uuid.UUID,
    pipeline: str,
    trigger_kind: str,
    started: datetime,
    details: dict,
) -> None:
    conn = _connect()
    if conn is None:
        return
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into run_status
                        (run_id, pipeline, host, trigger_kind, started_at, status, details)
                    values (%s, %s, %s, %s, %s, 'running', %s::jsonb)
                    """,
                    (
                        str(run_id),
                        pipeline,
                        _host(),
                        trigger_kind,
                        started,
                        _json(details),
                    ),
                )
    except Exception as exc:
        log.warning("run_status insert failed (continuing): %s", exc)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _finalize(
    run_id: uuid.UUID,
    status: str,
    handle: RunHandle,
    error: Optional[BaseException] = None,
) -> None:
    finished = datetime.now(timezone.utc)
    error_type = type(error).__name__ if error is not None else None
    error_message = str(error)[:2000] if error is not None else None
    if error is not None:
        handle.details.setdefault("traceback", traceback.format_exc()[-4000:])

    conn = _connect()
    if conn is None:
        return
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update run_status
                    set finished_at   = %s,
                        status        = %s,
                        rows_in       = %s,
                        rows_out      = %s,
                        error_type    = %s,
                        error_message = %s,
                        details       = details || %s::jsonb
                    where run_id = %s
                    """,
                    (
                        finished,
                        status,
                        handle.rows_in,
                        handle.rows_out,
                        error_type,
                        error_message,
                        _json(handle.details),
                        str(run_id),
                    ),
                )
    except Exception as exc:
        log.warning("run_status finalize failed: %s", exc)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def cli_insert_running(
    run_id: str,
    pipeline: str,
    trigger_kind: str,
) -> None:
    """Insert a running row from the CLI wrapper."""
    try:
        uid = uuid.UUID(run_id)
    except ValueError:
        log.warning("run_status cli: invalid run_id %r", run_id)
        return
    _insert_running(uid, pipeline, trigger_kind, datetime.now(timezone.utc), {})


def cli_update_finished(
    run_id: str,
    status: str,
    rows_out: Optional[int] = None,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """Update a run to a terminal status from the CLI wrapper."""
    try:
        uid = uuid.UUID(run_id)
    except ValueError:
        log.warning("run_status cli: invalid run_id %r", run_id)
        return
    if status not in ("ok", "failed", "timeout", "aborted"):
        log.warning("run_status cli: invalid status %r", status)
        return

    conn = _connect()
    if conn is None:
        return
    details_update: dict = {}
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update run_status
                    set finished_at   = now(),
                        status        = %s,
                        rows_out      = %s,
                        error_type    = %s,
                        error_message = %s,
                        details       = details || %s::jsonb
                    where run_id = %s
                    """,
                    (
                        status,
                        rows_out,
                        error_type,
                        (error_message[:2000] if error_message else None),
                        _json(details_update),
                        str(uid),
                    ),
                )
    except Exception as exc:
        log.warning("run_status cli finalize failed: %s", exc)
    finally:
        try:
            conn.close()
        except Exception:
            pass
