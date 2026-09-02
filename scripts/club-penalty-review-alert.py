#!/usr/bin/env python3
"""Send one private Telegram alert for newly created club penalty review tickets."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
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
DEFAULT_ALERT_STATE = Path("data/goalscorer/club-penalty-alert-state.json")
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
    Path("data/goalscorer/club-penalty-roster-audit.json"),
)
ACTIONABLE_PRIORITIES = {"high", "medium"}
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
HIERARCHY_FILES = {
    "serie-a": Path("data/goalscorer/serie-a-penalty-takers.json"),
    "epl": Path("data/goalscorer/epl-penalty-takers.json"),
    "la-liga": Path("data/goalscorer/la-liga-penalty-takers.json"),
    "bundesliga": Path("data/goalscorer/bundesliga-penalty-takers.json"),
    "ligue-1": Path("data/goalscorer/ligue-1-penalty-takers.json"),
}
PRIORITY_HIERARCHY_STATUSES = {"conditional", "disputed"}


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

def team_identity(row: dict) -> str:
    return f"{str(row.get('league') or '').strip().lower()}|{normalise(row.get('team'))}"


def priority_hierarchy_teams() -> dict[str, str]:
    teams: dict[str, str] = {}
    for league, relative in HIERARCHY_FILES.items():
        path = ROOT / relative
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        for team, entry in payload.items():
            if str(team).startswith("_") or not isinstance(entry, dict):
                continue
            status = str(entry.get("hierarchy_status") or "unknown").strip().lower()
            if status in PRIORITY_HIERARCHY_STATUSES:
                teams[f"{league}|{normalise(team)}"] = status
    return teams


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


def load_alert_state(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": 1, "updated_at": None, "items": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": 1, "updated_at": None, "items": {}}
    items = payload.get("items", {}) if isinstance(payload, dict) else {}
    if not isinstance(items, dict):
        items = {}
    return {"schema_version": 1, "updated_at": payload.get("updated_at"), "items": items}


def write_alert_state(path: Path, state: dict, rows: Iterable[dict]) -> None:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    items = dict(state.get("items") or {})
    for row in rows:
        identity = row_identity(row)
        items[identity] = {
            "alerted_at": now,
            "date": str(row.get("date") or ""),
            "league": str(row.get("league") or ""),
            "team": str(row.get("team") or ""),
            "opponent": str(row.get("opponent") or ""),
            "actual_taker": str(row.get("actual_taker") or ""),
        }
    payload = {"schema_version": 1, "updated_at": now, "items": items}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def new_actionable_rows(
    current: Iterable[dict],
    previous: Iterable[dict],
    priority_teams: dict[str, str] | None = None,
    alerted_identities: set[str] | None = None,
) -> list[dict]:
    previous_ids = set(dedupe_rows(previous))
    priority_teams = priority_teams or {}
    alerted_identities = alerted_identities or set()
    rows = []
    for identity, row in dedupe_rows(current).items():
        hierarchy_status = priority_teams.get(team_identity(row), "")
        review_priority = str(row.get("review_priority") or "").lower()
        if identity in previous_ids or identity in alerted_identities:
            continue
        if review_priority not in ACTIONABLE_PRIORITIES and not hierarchy_status:
            continue
        rows.append({**row, "public_hierarchy_status": hierarchy_status or "stable"})
    rows.sort(
        key=lambda row: (
            0 if str(row.get("public_hierarchy_status") or "") in PRIORITY_HIERARCHY_STATUSES else 1,
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
        secondary = compact(row.get("secondary_pre_match"), 42) or "not filed"
        tertiary = compact(row.get("tertiary_pre_match"), 42) or "not filed"
        hierarchy_status = compact(row.get("public_hierarchy_status"), 20).upper()
        role = str(row.get("actual_role_pre_match") or "none").strip().lower()
        role_label = {
            "primary": "No.1 primary",
            "secondary": "No.2 backup",
            "tertiary": "No.3 backup",
            "none": "Unranked",
        }.get(role, role.replace("_", " ").title() or "Unranked")
        actual_status = compact(
            row.get("actual_taker_match_status") or row.get("actual_taker_on_pitch_at_penalty"),
            62,
        ) or "lineup unavailable"
        minute = compact(row.get("minute"), 12)
        penalty_minute = f" | pen {minute}'" if minute else ""
        lines.extend(
            [
                f"[{priority}] {league} | {team}",
                f"Public hierarchy: {hierarchy_status}",
                f"{taker}: {result} vs {opponent}",
                f"Taker rank: {role_label} | {actual_status}{penalty_minute}",
                "Top three at the penalty:",
                f"1. {primary} - {compact(row.get('primary_on_pitch_at_penalty'), 58) or 'unknown'}",
                f"2. {secondary} - {compact(row.get('secondary_on_pitch_at_penalty'), 58) or 'unknown'}",
                f"3. {tertiary} - {compact(row.get('tertiary_on_pitch_at_penalty'), 58) or 'unknown'}",
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
            "Done = reviewed and close the ticket",
            "Defer = park for more evidence",
            "Hierarchy changes remain a separate editorial action",
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
    parser.add_argument("--state", default=str(DEFAULT_ALERT_STATE), help="Durable ledger of tickets already sent")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    state_path = Path(args.state)
    if not state_path.is_absolute():
        state_path = ROOT / state_path
    alert_state = load_alert_state(state_path)

    rows = new_actionable_rows(
        current_rows(REVIEW_FILES),
        previous_rows(REVIEW_FILES, args.base_ref),
        priority_hierarchy_teams(),
        set(alert_state["items"]),
    )
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
    write_alert_state(state_path, alert_state, rows)
    print(f"PENALTY_REVIEW_TELEGRAM sent tickets={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
