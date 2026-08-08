#!/usr/bin/env python3
"""Send changed club penalty-role review queues to the private Ops chat."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REVIEW = ROOT / "data" / "goalscorer" / "epl-preseason-penalty-role-review.json"
DEFAULT_STATE = ROOT / "data" / "goalscorer" / "epl-preseason-penalty-role-alert-state.json"
MAX_MESSAGE_LENGTH = 4096


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def active_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    return sorted(
        (row for row in rows if isinstance(row, dict) and row.get("status") == "active"),
        key=lambda row: (
            priority_rank.get(str(row.get("review_priority") or "").lower(), 9),
            str(row.get("row_id") or ""),
        ),
    )


def review_fingerprint(rows: list[dict[str, Any]]) -> str:
    identity = [
        {
            "row_id": str(row.get("row_id") or ""),
            "priority": str(row.get("review_priority") or ""),
            "review_type": str(row.get("review_type") or ""),
            "current_primary": str(row.get("current_primary") or ""),
            "proposed_primary": str(row.get("proposed_primary") or ""),
            "status": str(row.get("status") or ""),
        }
        for row in rows
    ]
    raw = json.dumps(identity, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest() if identity else ""


def build_message(rows: list[dict[str, Any]]) -> str:
    lines = [f"Club penalty hierarchy reviews: {len(rows)} open", ""]
    for row in rows:
        priority = str(row.get("review_priority") or "review").upper()
        team = str(row.get("team") or "Unknown team")
        current = str(row.get("current_primary") or "unknown")
        proposed = str(row.get("proposed_primary") or "no proposal")
        review_type = str(row.get("review_type") or "review").replace("_", " ")
        lines.append(f"{priority} {team}: {current} -> {proposed} ({review_type})")
    lines.extend(["", "Review: Model Monitor > Goalscorer > Preseason Role Review"])
    message = "\n".join(lines)
    if len(message) <= MAX_MESSAGE_LENGTH:
        return message
    return message[: MAX_MESSAGE_LENGTH - 3].rstrip() + "..."


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
        print(f"Warning: penalty-role Telegram alert failed: {exc}", file=sys.stderr)
        return False


def write_state(path: Path, fingerprint: str, row_count: int, *, sent_at: str | None) -> None:
    payload = {
        "schema_version": 1,
        "fingerprint": fingerprint,
        "sent_at": sent_at,
        "row_count": row_count,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = read_json(args.review, {})
    rows = active_rows(payload if isinstance(payload, dict) else {})
    fingerprint = review_fingerprint(rows)
    state = read_json(args.state, {})
    previous = str(state.get("fingerprint") or "") if isinstance(state, dict) else ""

    if not rows:
        if previous:
            write_state(args.state, "", 0, sent_at=None)
        print("Penalty-role Telegram alert skipped: no active reviews.")
        return 0
    if fingerprint == previous:
        print(f"Penalty-role Telegram alert skipped: {len(rows)} unchanged review(s).")
        return 0

    message = build_message(rows)
    if args.dry_run:
        print(message)
        return 0

    bot_token = os.environ.get("OPS_ALERT_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("OPS_ALERT_TELEGRAM_CHAT_ID", "").strip()
    if not bot_token or not chat_id:
        print("Penalty-role Telegram alert skipped: missing Ops Telegram credentials.")
        return 0
    if not post_telegram(bot_token, chat_id, message):
        return 0

    sent_at = utc_now()
    write_state(args.state, fingerprint, len(rows), sent_at=sent_at)
    print(f"Penalty-role Telegram alert sent: {len(rows)} review(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
