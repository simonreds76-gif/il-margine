#!/usr/bin/env python3
"""Alert Telegram when a published penalty taker is absent from a current squad."""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT = ROOT / "data" / "goalscorer" / "club-penalty-squad-audit.json"


def load_audit(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def issue_rows(payload: dict) -> list[dict]:
    rows = payload.get("rows") or []
    return [row for row in rows if isinstance(row, dict) and row.get("status") != "present"]


def build_message(payload: dict, run_url: str = "") -> str:
    issues = issue_rows(payload)
    status_counts = payload.get("status_counts") or {}
    lines = [
        "CLUB PENALTY SQUAD AUDIT",
        f"{payload.get('clubs_checked', 0)} clubs / {payload.get('slots_checked', 0)} hierarchy slots",
        f"Issues: {len(issues)} | Present: {status_counts.get('present', 0)}",
        "",
    ]
    grouped_fetch_errors: set[tuple[str, str]] = set()
    shown = 0
    for row in issues:
        status = str(row.get("status") or "unknown")
        key = (str(row.get("league") or ""), str(row.get("club") or ""))
        if status == "fetch_error":
            if key in grouped_fetch_errors:
                continue
            grouped_fetch_errors.add(key)
            label = f"[{status.upper()}] {key[0].upper()} | {key[1]} | squad unavailable"
        else:
            label = (
                f"[{status.upper()}] {key[0].upper()} | {key[1]} | "
                f"{row.get('rank', '?')} {row.get('player', 'unknown')}"
            )
        lines.append(label)
        shown += 1
        if shown >= 15:
            break
    remaining = len(issues) - shown
    if remaining > 0:
        lines.append(f"Plus {remaining} additional affected slot(s) in the audit artifact.")
    lines.extend(
        [
            "",
            "Public hierarchies were not changed automatically.",
            "Verify the transfer/squad source, then edit and close the exception.",
        ]
    )
    if run_url:
        lines.extend(["", f"Workflow: {run_url}"])
    return "\n".join(lines)[:4096]


def send_telegram(message: str, token: str, chat_id: str) -> None:
    body = json.dumps(
        {"chat_id": chat_id, "text": message, "disable_web_page_preview": True}
    ).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        response.read()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    payload = load_audit(args.audit)
    issues = issue_rows(payload)
    if not issues:
        print("PENALTY_SQUAD_TELEGRAM audit_clean")
        return 0

    message = build_message(payload, os.environ.get("GITHUB_RUN_URL", "").strip())
    if args.dry_run:
        print(message)
        return 0

    token = os.environ.get("OPS_ALERT_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("OPS_ALERT_TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("PENALTY_SQUAD_TELEGRAM skipped_missing_credentials")
        return 1
    send_telegram(message, token, chat_id)
    print(f"PENALTY_SQUAD_TELEGRAM sent issues={len(issues)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
