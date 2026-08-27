#!/usr/bin/env python3
"""Send one compact daily Telegram digest from existing football model artifacts."""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
COUNTS_BOARD = ROOT / "data/football-form/football-counts-vnext-candidates.csv"
GK_BOARD = ROOT / "data/goalkeeper-saves/gk-saves-v1-candidates.csv"
DEFAULT_STATE = ROOT / "data/football-form/football-daily-signal-digest-state.json"
TELEGRAM_LIMIT = 3900
COUNT_MIN_EDGE = 0.03


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value: object) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def row_day(row: dict[str, str]) -> str:
    return str(row.get("match_date") or "").strip()


def kickoff_label(value: object) -> str:
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return "time unavailable"
    return parsed.astimezone(timezone.utc).strftime("%H:%M UTC")


def count_candidates(rows: list[dict[str, str]], target_day: str, model: str) -> list[dict[str, object]]:
    strongest: dict[str, dict[str, object]] = {}
    for row in rows:
        if row_day(row) != target_day or str(row.get("model") or "") != model:
            continue
        edge = number(row.get("edge"))
        if edge is None or edge < COUNT_MIN_EDGE:
            continue
        blockers = {item for item in str(row.get("blocked_reason") or "").split(";") if item}
        if blockers - {"matchdays_1_to_3"}:
            continue
        match_id = str(row.get("match_id") or row.get("match") or "").strip()
        if not match_id:
            continue
        candidate = {
            "id": str(row.get("pick_id") or f"{model}|{match_id}|{row.get('selection')}").strip(),
            "model": model,
            "status": "WARM-UP TRACK" if blockers else "SHADOW",
            "kickoff": kickoff_label(row.get("kickoff_utc")),
            "match": str(row.get("match") or "").strip(),
            "selection": str(row.get("selection") or "").strip(),
            "bookmaker": str(row.get("bookmaker") or "").strip(),
            "odds": number(row.get("book_odds")),
            "fair": number(row.get("model_fair_odds")),
            "edge": edge,
        }
        existing = strongest.get(match_id)
        if existing is None or float(candidate["edge"]) > float(existing["edge"]):
            strongest[match_id] = candidate
    return sorted(strongest.values(), key=lambda row: (str(row["kickoff"]), str(row["match"])))


def goalkeeper_candidates(rows: list[dict[str, str]], target_day: str) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for row in rows:
        if row_day(row) != target_day:
            continue
        edge = number(row.get("edge"))
        status = str(row.get("candidate_status") or "").strip()
        if edge is None or edge <= 0 or status not in {"eligible_shadow", "value_ladder"}:
            continue
        if str(row.get("blockers") or "").strip():
            continue
        event_id = str(row.get("event_id") or "").strip()
        goalkeeper = str(row.get("goalkeeper") or "").strip()
        line = str(row.get("line") or "").strip()
        side = str(row.get("side") or "").strip().lower()
        candidates.append(
            {
                "id": f"gk_saves_v1|{event_id}|{goalkeeper.casefold()}|{line}|{side}",
                "model": "gk_saves_v1",
                "status": "SHADOW" if status == "eligible_shadow" else "VALUE LADDER",
                "kickoff": kickoff_label(row.get("kickoff_at")),
                "match": f"{row.get('home_team', '').strip()} vs {row.get('away_team', '').strip()}",
                "selection": f"{goalkeeper} {side.title()} {line} saves",
                "bookmaker": "Bet365",
                "odds": number(row.get("odds_decimal")),
                "fair": number(row.get("fair_odds")),
                "edge": edge,
            }
        )
    return sorted(candidates, key=lambda row: (str(row["kickoff"]), str(row["match"]), -float(row["edge"])))


def build_candidates(target_day: str) -> dict[str, list[dict[str, object]]]:
    counts = read_csv(COUNTS_BOARD)
    return {
        "TEAM SHOTS V4": count_candidates(counts, target_day, "team_shots_v4"),
        "CORNERS V3": count_candidates(counts, target_day, "corners_v3"),
        "GK SAVES V1": goalkeeper_candidates(read_csv(GK_BOARD), target_day),
    }


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": 1, "sent": {}, "summary_dates": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": 1, "sent": {}, "summary_dates": []}
    return {
        "schema_version": 1,
        "sent": payload.get("sent", {}) if isinstance(payload.get("sent"), dict) else {},
        "summary_dates": payload.get("summary_dates", []) if isinstance(payload.get("summary_dates"), list) else [],
    }


def write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def unseen_candidates(groups: dict[str, list[dict[str, object]]], state: dict) -> dict[str, list[dict[str, object]]]:
    sent = state.get("sent", {})
    return {label: [row for row in rows if str(row["id"]) not in sent] for label, rows in groups.items()}


def candidate_block(row: dict[str, object]) -> str:
    odds = float(row["odds"]) if row.get("odds") is not None else 0.0
    fair = float(row["fair"]) if row.get("fair") is not None else 0.0
    edge = float(row["edge"])
    bookmaker = f" {row['bookmaker']}" if row.get("bookmaker") else ""
    return "\n".join(
        [
            f"[{row['status']}] {row['match']} | {row['kickoff']}",
            f"{row['selection']} @{odds:.2f}{bookmaker} | fair {fair:.2f} | EV {edge:+.1%}",
        ]
    )


def render_messages(groups: dict[str, list[dict[str, object]]], target_day: str, include_empty: bool) -> list[tuple[str, list[str]]]:
    header = "\n".join(
        [
            "IL MARGINE FOOTBALL MODEL ALERTS",
            f"Fixtures: {target_day}",
            "Internal shadow evidence - not public tips.",
        ]
    )
    blocks: list[tuple[str, list[str]]] = []
    for label, rows in groups.items():
        if not rows:
            if include_empty:
                blocks.append((f"{label}\nNo new qualifying +EV candidate.", []))
            continue
        for index, row in enumerate(rows):
            prefix = f"{label}\n" if index == 0 else ""
            blocks.append((prefix + candidate_block(row), [str(row["id"])]))
    if not blocks:
        return []

    messages: list[tuple[str, list[str]]] = []
    current = header
    current_ids: list[str] = []
    for block, ids in blocks:
        candidate = f"{current}\n\n{block}"
        if len(candidate) > TELEGRAM_LIMIT and current != header:
            messages.append((current, current_ids))
            current = f"{header}\nContinuation\n\n{block}"
            current_ids = list(ids)
        else:
            current = candidate
            current_ids.extend(ids)
    messages.append((current, current_ids))
    return messages


def send_telegram(message: str, token: str, chat_id: str) -> None:
    payload = json.dumps(
        {"chat_id": chat_id, "text": message, "disable_web_page_preview": True}
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    state = load_state(args.state)
    groups = unseen_candidates(build_candidates(args.date), state)
    first_summary_today = args.date not in state["summary_dates"]
    messages = render_messages(groups, args.date, include_empty=first_summary_today)
    if not messages:
        print("FOOTBALL_DAILY_DIGEST unchanged; skipped")
        return 0
    if args.dry_run:
        for message, _ in messages:
            print(message)
            print("---")
        return 0

    token = os.environ.get("OPS_ALERT_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("OPS_ALERT_TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("FOOTBALL_DAILY_DIGEST skipped_missing_credentials")
        return 0

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for message, identities in messages:
        send_telegram(message, token, chat_id)
        for identity in identities:
            state["sent"][identity] = {"sent_at": now, "fixture_date": args.date}
        write_state(args.state, state)
    if args.date not in state["summary_dates"]:
        state["summary_dates"].append(args.date)
        state["summary_dates"] = state["summary_dates"][-60:]
    state["updated_at"] = now
    write_state(args.state, state)
    count = sum(len(rows) for rows in groups.values())
    print(f"FOOTBALL_DAILY_DIGEST sent candidates={count} messages={len(messages)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
