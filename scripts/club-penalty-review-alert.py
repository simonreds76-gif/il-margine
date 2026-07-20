#!/usr/bin/env python3
"""Send one private Telegram alert for newly created club penalty review tickets."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import unicodedata
import urllib.request
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEW_URL = "http://localhost:3000/model-monitor/goalscorer#penalty-watchlist"
REVIEW_FILES = (
    Path("data/goalscorer/penalty-duty-review.json"),
    Path("data/goalscorer/epl-penalty-duty-review.json"),
    Path("data/goalscorer/la-liga-penalty-duty-review.json"),
    Path("data/goalscorer/bundesliga-penalty-duty-review.json"),
    Path("data/goalscorer/ligue-1-penalty-duty-review.json"),
    Path("data/goalscorer/penalty-duty-live-review.json"),
    Path("data/goalscorer/epl-penalty-duty-live-review.json"),
    Path("data/goalscorer/la-liga-penalty-duty-live-review.json"),
    Path("data/goalscorer/bundesliga-penalty-duty-live-review.json"),
    Path("data/goalscorer/ligue-1-penalty-duty-live-review.json"),
)
ACTIONABLE_PRIORITIES = {"high", "medium"}
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def normalise(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = text.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "", ascii_text)


def row_identity(row: dict) -> str:
    return "|".join(
        [
            str(row.get("date") or "").strip().lower(),
            str(row.get("league") or "").strip().lower(),
            normalise(row.get("team")),
            normalise(row.get("opponent")),
            normalise(row.get("actual_taker")),
        ]
    )


def payload_rows(raw: bytes | str) -> list[dict]:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []
    rows = payload.get("rows", []) if isinstance(payload, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def current_rows(paths: Iterable[Path]) -> list[dict]:
    rows: list[dict] = []
    for relative in paths:
        path = ROOT / relative
        if path.exists():
            rows.extend(payload_rows(path.read_bytes()))
    return rows


def previous_rows(paths: Iterable[Path], base_ref: str) -> list[dict]:
    rows: list[dict] = []
    for relative in paths:
        result = subprocess.run(
            ["git", "show", f"{base_ref}:{relative.as_posix()}"],
            cwd=ROOT,
            check=False,
            capture_output=True,
        )
        if result.returncode == 0:
            rows.extend(payload_rows(result.stdout))
    return rows


def dedupe_rows(rows: Iterable[dict]) -> dict[str, dict]:
    deduped: dict[str, dict] = {}
    for row in rows:
        identity = row_identity(row)
        if identity.replace("|", ""):
            existing = deduped.get(identity)
            if existing is None or PRIORITY_ORDER.get(str(row.get("review_priority") or "low").lower(), 9) < PRIORITY_ORDER.get(str(existing.get("review_priority") or "low").lower(), 9):
                deduped[identity] = row
    return deduped


def new_actionable_rows(current: Iterable[dict], previous: Iterable[dict]) -> list[dict]:
    previous_ids = set(dedupe_rows(previous))
    rows = [
        row
        for identity, row in dedupe_rows(current).items()
        if identity not in previous_ids and str(row.get("review_priority") or "").lower() in ACTIONABLE_PRIORITIES
    ]
    rows.sort(
        key=lambda row: (
            PRIORITY_ORDER.get(str(row.get("review_priority") or "low").lower(), 9),
            str(row.get("date") or ""),
            str(row.get("team") or ""),
        )
    )
    return rows


def compact(value: object, limit: int = 120) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else f"{text[: max(0, limit - 3)].rstrip()}..."


def build_message(rows: list[dict], review_url: str, run_url: str = "") -> str:
    counts = {priority: sum(str(row.get("review_priority") or "").lower() == priority for row in rows) for priority in ACTIONABLE_PRIORITIES}
    lines = [
        "CLUB PENALTY REVIEW",
        f"{len(rows)} new ticket(s): {counts['high']} high, {counts['medium']} medium",
        "",
    ]
    for row in rows[:8]:
        priority = str(row.get("review_priority") or "medium").upper()
        league = compact(row.get("league"), 20).upper()
        team = compact(row.get("team"), 36)
        opponent = compact(row.get("opponent"), 36)
        taker = compact(row.get("actual_taker"), 42)
        result = compact(row.get("event_result") or row.get("event_type"), 32)
        primary = compact(row.get("primary_pre_match"), 42) or "not filed"
        lines.extend(
            [
                f"[{priority}] {league} | {team}",
                f"{taker}: {result} vs {opponent}",
                f"Filed primary: {primary}",
                f"Reason: {compact(row.get('review_type'), 55)}",
                "",
            ]
        )
    if len(rows) > 8:
        lines.extend([f"Plus {len(rows) - 8} more ticket(s) in the queue.", ""])
    lines.extend(
        [
            "Review on your PC:",
            review_url,
            "",
            "After editing: Hierarchy updated = sorted",
            "Keep current order = ignore",
        ]
    )
    if run_url:
        lines.extend(["", f"Workflow: {run_url}"])
    return "\n".join(lines)[:4096]


def send_telegram(message: str, token: str, chat_id: str) -> None:
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        response.read()


def main() -> int:
    parser = argparse.ArgumentParser(description="Alert on newly created club penalty review tickets")
    parser.add_argument("--base-ref", default="HEAD", help="Git ref containing the previously published review queues")
    parser.add_argument("--review-url", default=os.environ.get("PENALTY_REVIEW_URL", DEFAULT_REVIEW_URL))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = new_actionable_rows(current_rows(REVIEW_FILES), previous_rows(REVIEW_FILES, args.base_ref))
    if not rows:
        print("PENALTY_REVIEW_TELEGRAM no_new_actionable_tickets")
        return 0

    message = build_message(rows, args.review_url, os.environ.get("GITHUB_RUN_URL", "").strip())
    if args.dry_run:
        print(message)
        return 0

    token = os.environ.get("OPS_ALERT_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("OPS_ALERT_TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("PENALTY_REVIEW_TELEGRAM skipped_missing_credentials")
        return 0

    send_telegram(message, token, chat_id)
    print(f"PENALTY_REVIEW_TELEGRAM sent tickets={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
