#!/usr/bin/env python3
"""
Build a manual-review queue for penalty-duty changes from settled player logs.

This script joins actual penalty events (from the player match logs) to the
pre-match hierarchy context emitted by `goalscorer-live-compare.py`.
It does not auto-edit any penalty-taker boards. It produces an editorial
watchlist so club/world-cup penalty pages can be updated deliberately.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import runpy
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTEXT = [
    "data/goalscorer/penalty-duty-context.json",
    "data/goalscorer/live-history/penalty-duty-context-*.json",
]
DEFAULT_DATA = ["data/goalscorer/serie-a-player-match-logs-*.csv"]
DEFAULT_OUTPUT = ROOT / "data" / "goalscorer" / "penalty-duty-review.csv"
DEFAULT_JSON_OUTPUT = ROOT / "data" / "goalscorer" / "penalty-duty-review.json"
HIERARCHY_SLOTS = ("primary", "secondary", "tertiary")
STARTER_STATUSES = {"confirmed_starter", "expected_starter"}
REVIEW_FIELDNAMES = [
    "date",
    "league",
    "review_source",
    "match",
    "team",
    "opponent",
    "actual_taker",
    "actual_role_pre_match",
    "penalties_attempted",
    "penalties_scored",
    "distinct_takers_in_match",
    "primary_pre_match",
    "secondary_pre_match",
    "tertiary_pre_match",
    "primary_lineup_status",
    "secondary_lineup_status",
    "tertiary_lineup_status",
    "active_taker_pre_match",
    "active_slot_pre_match",
    "team_lineup_status",
    "review_type",
    "review_priority",
    "editorial_note",
    "context_generated_at",
    "context_source_path",
]


def _expand_paths(paths: Iterable[str]) -> List[Path]:
    expanded: List[Path] = []
    for value in paths:
        if "*" in value or "?" in value:
            expanded.extend(Path(path) for path in glob.glob(value))
        else:
            expanded.append(Path(value))
    return [path for path in expanded if path.exists()]


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _write_csv(path: Path, rows: List[dict], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _parse_float(value, default: float = 0.0) -> float:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _parse_date(value: str):
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text[:10]).date()
    except ValueError:
        return None


def _pseudo_hierarchy(context_row: dict) -> dict:
    return {
        "primary": context_row.get("primary", ""),
        "secondary": context_row.get("secondary", ""),
        "tertiary": context_row.get("tertiary", ""),
    }


def _context_key(row: dict) -> tuple[str, str, str]:
    return (
        (row.get("match_date") or "").strip(),
        (row.get("team_key") or "").strip(),
        (row.get("opponent_key") or "").strip(),
    )


def load_context_rows(paths: Iterable[str]) -> List[dict]:
    best: Dict[tuple[str, str, str], dict] = {}
    for path in _expand_paths(paths):
        payload = _load_json(path)
        generated_at = str(payload.get("generated_at") or "")
        league = str(payload.get("league") or "")
        rows = payload.get("rows", [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            item = dict(row)
            item.setdefault("league", league)
            item["_generated_at"] = generated_at
            item["_source_path"] = _display_path(path)
            key = _context_key(item)
            if not all(key):
                continue
            current = best.get(key)
            if current is None or item["_generated_at"] > current["_generated_at"]:
                best[key] = item
    return list(best.values())


def _review_priority(review_type: str) -> str:
    if review_type in {"backup_jump_with_primary_available", "unranked_taker", "multiple_penalties_split"}:
        return "high"
    if review_type in {"expected_backup_shift", "needs_manual_review"}:
        return "medium"
    return "low"


def _build_editorial_note(
    *,
    actual_taker: str,
    attempts: int,
    event_result: str = "",
    team: str,
    opponent: str,
    context: dict,
    review_type: str,
) -> str:
    primary = context.get("primary", "")
    secondary = context.get("secondary", "")
    base = f"{actual_taker} took {attempts} penalty"
    if attempts != 1:
        base += " attempts"
    else:
        base += " attempt"
    result_text = (event_result or "").strip().lower()
    if result_text in {"scored", "missed", "mixed"}:
        base += f" and {result_text}"
    base += f" for {team} vs {opponent}."

    context_bits: List[str] = []
    if primary:
        context_bits.append(
            f"Primary pre-match: {primary} ({context.get('primary_lineup_status') or 'unknown'})."
        )
    if secondary:
        context_bits.append(
            f"Secondary pre-match: {secondary} ({context.get('secondary_lineup_status') or 'unknown'})."
        )
    active_taker = context.get("active_taker_pre_match", "")
    active_slot = context.get("active_slot_pre_match", "")
    if active_taker:
        context_bits.append(f"Pre-match active slot was {active_slot or 'unknown'} -> {active_taker}.")

    if review_type == "primary_held":
        context_bits.append("No hierarchy change implied from this event.")
    elif review_type == "primary_reclaimed_from_bench":
        context_bits.append("Low-priority note: the benched primary later reclaimed the duty after coming on, so the hierarchy likely still stands.")
    elif review_type == "expected_backup_shift":
        context_bits.append("Looks like the expected backup took over because the primary was unavailable or inactive.")
    elif review_type == "backup_jump_with_primary_available":
        context_bits.append("Strong review flag: a ranked backup took it while the primary still looked available.")
    elif review_type == "unranked_taker":
        context_bits.append("Strong review flag: the taker was not in the tracked top three.")
    elif review_type == "multiple_penalties_split":
        context_bits.append("Strong review flag: penalty duty was split across multiple takers in the same match.")
    else:
        context_bits.append("Needs manual editorial review.")

    return " ".join([base, *context_bits]).strip()


def _classify_review_type(
    *,
    context: dict,
    actual_role: str,
    distinct_takers_in_match: int,
) -> str:
    if distinct_takers_in_match > 1:
        return "multiple_penalties_split"

    has_hierarchy = any((context.get(slot) or "").strip() for slot in HIERARCHY_SLOTS)
    if not has_hierarchy:
        return "needs_manual_review"

    primary_available = (context.get("primary_lineup_status") or "").strip() in STARTER_STATUSES
    active_slot = (context.get("active_slot_pre_match") or "").strip().lower()
    if actual_role == "primary":
        if active_slot and active_slot != "primary":
            primary_status = (context.get("primary_lineup_status") or "").strip()
            if primary_status in {"confirmed_bench", "expected_bench"}:
                return "primary_reclaimed_from_bench"
            return "needs_manual_review"
        # The tracked primary taking the penalty directly confirms the filed
        # hierarchy even when the upstream lineup source is unavailable.
        return "primary_held"

    if actual_role in {"secondary", "tertiary"}:
        if actual_role == active_slot or not primary_available:
            return "expected_backup_shift"
        return "backup_jump_with_primary_available"

    return "unranked_taker"


def build_review_rows(context_rows: List[dict], data_paths: Iterable[str], days_back: int) -> List[dict]:
    model_mod = runpy.run_path(str(ROOT / "scripts" / "goalscorer-model.py"), run_name="goalscorer_model")
    load_match_logs = model_mod["load_match_logs"]
    penalty_utils = runpy.run_path(
        str(ROOT / "scripts" / "goalscorer_penalty_utils.py"),
        run_name="goalscorer_penalty_utils",
    )
    penalty_role_for_player = penalty_utils["penalty_role_for_player"]

    context_by_key = {_context_key(row): row for row in context_rows}
    historical_rows = load_match_logs(list(data_paths))
    if not historical_rows:
        return []

    min_date = datetime.now(timezone.utc).date() - timedelta(days=max(days_back, 1))
    grouped_events: Dict[tuple[str, str, str], List[object]] = defaultdict(list)
    for row in historical_rows:
        if row.penalties_attempted <= 0:
            continue
        if row.match_date < min_date:
            continue
        key = (row.match_date_str, row.team_key, row.opponent_key)
        if key not in context_by_key:
            continue
        grouped_events[key].append(row)

    review_rows: List[dict] = []
    for key, events in grouped_events.items():
        context = context_by_key[key]
        hierarchy = _pseudo_hierarchy(context)
        distinct_takers = {event.player_name.strip() for event in events if event.player_name.strip()}
        for event in sorted(events, key=lambda item: (-int(item.penalties_attempted), item.player_name)):
            actual_taker = event.player_name.strip()
            actual_role = penalty_role_for_player(hierarchy, actual_taker)
            review_type = _classify_review_type(
                context=context,
                actual_role=actual_role,
                distinct_takers_in_match=len(distinct_takers),
            )
            review_rows.append(
                {
                    "date": event.match_date_str,
                    "league": context.get("league", ""),
                    "review_source": "settled_logs",
                    "match": f"{context.get('home_team', '')} vs {context.get('away_team', '')}",
                    "team": event.team,
                    "opponent": event.opponent,
                    "actual_taker": actual_taker,
                    "actual_role_pre_match": actual_role,
                    "penalties_attempted": int(event.penalties_attempted),
                    "penalties_scored": int(event.penalties_scored),
                    "distinct_takers_in_match": len(distinct_takers),
                    "primary_pre_match": context.get("primary", ""),
                    "secondary_pre_match": context.get("secondary", ""),
                    "tertiary_pre_match": context.get("tertiary", ""),
                    "primary_lineup_status": context.get("primary_lineup_status", ""),
                    "secondary_lineup_status": context.get("secondary_lineup_status", ""),
                    "tertiary_lineup_status": context.get("tertiary_lineup_status", ""),
                    "active_taker_pre_match": context.get("active_taker_pre_match", ""),
                    "active_slot_pre_match": context.get("active_slot_pre_match", ""),
                    "team_lineup_status": context.get("team_lineup_status", ""),
                    "review_type": review_type,
                    "review_priority": _review_priority(review_type),
                    "editorial_note": _build_editorial_note(
                        actual_taker=actual_taker,
                        attempts=int(event.penalties_attempted),
                        team=event.team,
                        opponent=event.opponent,
                        context=context,
                        review_type=review_type,
                    ),
                    "context_generated_at": context.get("_generated_at", ""),
                    "context_source_path": context.get("_source_path", ""),
                }
            )

    priority_order = {"high": 0, "medium": 1, "low": 2}
    review_rows.sort(
        key=lambda row: (
            row.get("date", ""),
            priority_order.get(row.get("review_priority", "medium"), 9),
            row.get("team", ""),
            row.get("actual_taker", ""),
        ),
        reverse=True,
    )
    return review_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a manual penalty-duty review queue from settled player logs")
    parser.add_argument("--context", nargs="+", default=DEFAULT_CONTEXT, help="Penalty-duty context JSON paths or globs")
    parser.add_argument("--data", nargs="+", default=DEFAULT_DATA, help="Historical player-log CSVs or globs")
    parser.add_argument("--days-back", type=int, default=14, help="Only review penalty events within this many days")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Penalty-duty review CSV path")
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT), help="Penalty-duty review JSON path")
    parser.add_argument(
        "--allow-empty-context",
        action="store_true",
        help="Write empty review artifacts instead of failing when no context rows exist.",
    )
    parser.add_argument(
        "--fail-empty-context",
        action="store_true",
        help="Fail when no context rows exist. Default is to write empty review artifacts so scheduled league loops continue.",
    )
    args = parser.parse_args()

    context_rows = load_context_rows(args.context)
    if not context_rows:
        if args.fail_empty_context and not args.allow_empty_context:
            raise SystemExit("No penalty-duty context rows found. Run goalscorer-live-compare.py first.")
        _write_csv(Path(args.output), [], REVIEW_FIELDNAMES)
        _write_json(
            Path(args.json_output),
            {
                "schema_version": 1,
                "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "row_count": 0,
                "context_row_count": 0,
                "status": "empty_context",
                "rows": [],
            },
        )
        if not args.allow_empty_context:
            print("No penalty-duty context rows found; wrote empty review artifacts.")
        print("Loaded context rows: 0")
        print("Review rows:         0")
        print(f"Saved CSV:           {args.output}")
        print(f"Saved JSON:          {args.json_output}")
        return

    review_rows = build_review_rows(context_rows, args.data, args.days_back)
    _write_csv(Path(args.output), review_rows, REVIEW_FIELDNAMES)
    _write_json(
        Path(args.json_output),
        {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "row_count": len(review_rows),
            "rows": review_rows,
        },
    )

    print(f"Loaded context rows: {len(context_rows):,}")
    print(f"Review rows:         {len(review_rows):,}")
    print(f"Saved CSV:           {args.output}")
    print(f"Saved JSON:          {args.json_output}")


if __name__ == "__main__":
    main()
