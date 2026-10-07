#!/usr/bin/env python3
"""Write an explicit health state for the tennis props evidence pipeline."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROPS = ROOT / "data" / "tennis-props"
DEFAULT_SIGNALS = PROPS / "shadow" / "aces-dfs-shadow-signals.csv"
DEFAULT_JSON = PROPS / "pipeline-health.json"
DEFAULT_REPORT = PROPS / "pipeline-health.txt"
MAX_CAPTURE_AGE_HOURS = 6.0
FUTURE_CLOCK_TOLERANCE_SECONDS = 300


def upcoming_row(row: dict[str, str], as_of: str, now: datetime) -> bool:
    event_day = str(row.get("date") or "")
    if event_day and event_day < as_of:
        return False
    start = parse_timestamp(row.get("match_start_utc"))
    return start is None or start > now


def capture_problem(row: dict[str, str], now: datetime) -> str | None:
    captured = parse_timestamp(row.get("capture_ts") or row.get("captured_at"))
    if captured is None:
        return "CAPTURE_TIME_MISSING"
    age = (now - captured).total_seconds()
    if age < -FUTURE_CLOCK_TOLERANCE_SECONDS:
        return "CAPTURE_TIME_IN_FUTURE"
    if age > MAX_CAPTURE_AGE_HOURS * 3600:
        return "CAPTURE_STALE"
    return None


def observation_key(row: dict[str, str]) -> tuple[str, ...] | None:
    # Only compare fully identified observations; diagnostic counts still accept
    # historical rows without identities, but cannot establish their parity.
    fields = ("event_id", "bookmaker", "player", "opponent", "market", "line", "capture_ts")
    values = tuple(str(row.get(field) or "").strip() for field in fields)
    if not all(values):
        return None
    captured = parse_timestamp(values[-1])
    try:
        line = Decimal(values[-2])
    except InvalidOperation:
        return None
    if captured is None or not line.is_finite():
        return None
    return (*(" ".join(value.casefold().split()) for value in values[:-2]),
            str(line.normalize()), captured.isoformat())


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def parse_timestamp(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def event_date_counts(rows: list[dict[str, str]], as_of: str) -> tuple[int, int]:
    target = date.fromisoformat(as_of)
    eligible = 0
    past = 0
    for row in rows:
        raw = str(row.get("date") or "").strip()
        if not raw:
            eligible += 1
            continue
        try:
            event_date = date.fromisoformat(raw)
        except ValueError:
            eligible += 1
            continue
        if event_date < target:
            past += 1
        else:
            eligible += 1
    return eligible, past


def build_health(
    as_of: str,
    lines_path: Path,
    comparison_path: Path,
    signals_path: Path,
    *,
    now: datetime | None = None,
    baseline_directory: Path | None = None,
) -> dict[str, object]:
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    line_rows = read_csv(lines_path)
    comparison_rows = read_csv(comparison_path)
    signals = read_csv(signals_path)
    latest_capture = max(
        (
            parse_timestamp(row.get("capture_ts") or row.get("captured_at"))
            for row in line_rows
        ),
        default=None,
        key=lambda value: value or datetime.min.replace(tzinfo=timezone.utc),
    )
    capture_age = (
        max(0.0, (now_utc - latest_capture).total_seconds() / 3600.0)
        if latest_capture
        else None
    )
    match_count = sum(row.get("matched_board") == "yes" for row in comparison_rows)
    two_way_count = sum(row.get("price_pair_status") == "two_way" for row in comparison_rows)
    over_only_count = sum(row.get("price_pair_status") == "over_only" for row in comparison_rows)
    milestone_count = sum(row.get("price_pair_status") == "over_only"
                          and row.get("market") in {"aces", "double_faults", "match_aces", "match_double_faults"}
                          for row in comparison_rows)
    eligible_line_count, past_line_count = event_date_counts(line_rows, as_of)
    trackable_count = sum(row.get("trackable_shadow") == "true" for row in comparison_rows)
    bettable_count = sum(row.get("bettable") == "true" for row in comparison_rows)
    upcoming_lines = [row for row in line_rows if upcoming_row(row, as_of, now_utc)]
    freshness_problems = Counter(
        problem for row in upcoming_lines if (problem := capture_problem(row, now_utc))
    )
    fresh_upcoming_lines = [row for row in upcoming_lines if capture_problem(row, now_utc) is None]
    comparison_keys = {key for row in comparison_rows if (key := observation_key(row))}
    missing_comparison_rows = sum(
        bool(key and key not in comparison_keys)
        for row in upcoming_lines
        for key in [observation_key(row)]
    )
    market_health = []
    groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in upcoming_lines:
        groups.setdefault((row.get("bookmaker") or "unknown", row.get("market") or "unknown"), []).append(row)
    for (bookmaker, market), rows in sorted(groups.items()):
        fresh = sum(capture_problem(row, now_utc) is None for row in rows)
        missing = sum(bool(key and key not in comparison_keys) for row in rows for key in [observation_key(row)])
        market_health.append({"bookmaker": bookmaker, "market": market, "upcoming_rows": len(rows),
                              "fresh_rows": fresh, "uncompared_rows": missing,
                              "state": "CAPTURE_STALE_OR_INVALID" if fresh < len(rows) else "COMPARISON_BEHIND_CAPTURE" if missing else "CURRENT"})
    blockers = Counter(
        str(row.get("shadow_block_reasons") or row.get("block_reasons") or "none").split("|")[0]
        for row in comparison_rows
        if row.get("trackable_shadow") != "true" and row.get("bettable") != "true"
    )
    as_of_signals = [row for row in signals if str(row.get("date") or "") == as_of]
    break_markets = {"player_breaks", "match_breaks"}
    break_line_rows = [row for row in line_rows if str(row.get("market") or "").lower() in break_markets]
    break_comparison_rows = [row for row in comparison_rows if str(row.get("market") or "").lower() in break_markets]
    break_matched_rows = [row for row in break_comparison_rows if row.get("matched_board") == "yes"]
    break_trackable_rows = [row for row in break_matched_rows if row.get("trackable_shadow") == "true"]
    break_strict_rows = [
        row for row in break_trackable_rows if row.get("decision_mode") == "breaks_prospective_shadow"
    ]
    break_single_source_rows = [
        row for row in break_trackable_rows if row.get("decision_mode") == "breaks_single_source_shadow"
    ]
    break_calibration_rows = [row for row in break_comparison_rows if row.get("calibration_eligible") == "true"]
    break_blockers = Counter(
        str(row.get("shadow_block_reasons") or "none").split("|")[0]
        for row in break_matched_rows
        if row.get("trackable_shadow") != "true"
    )
    if not break_line_rows:
        break_state = "PRICE_FEED_MISSING"
    elif not break_comparison_rows or not break_matched_rows:
        break_state = "BOARD_MATCH_FAILED"
    elif break_strict_rows:
        break_state = "STRICT_PROSPECTIVE_READY"
    elif break_single_source_rows:
        break_state = "BET365_PROSPECTIVE_READY"
    elif break_calibration_rows:
        break_state = "CALIBRATION_ONLY"
    else:
        break_state = "NO_QUALIFYING_EDGE"

    from tennis_props_current_history import history_health
    current_history = history_health(ROOT / "data/tennis-props", as_of) if baseline_directory is None else None
    structural_error = False
    if not line_rows:
        state = "FEED_MISSING"
        structural_error = True
    elif not comparison_path.exists() or not comparison_rows:
        state = "COMPARISON_MISSING"
        structural_error = True
    elif not match_count:
        state = "BOARD_MATCH_FAILED"
        structural_error = True
    elif not two_way_count and over_only_count and milestone_count == over_only_count:
        # Bet365 ace/DF ladders legitimately offer only the milestone back price.
        # Model EV remains available; paired-market de-vig does not.
        state = "MILESTONE_SHADOW_READY" if trackable_count else "MILESTONE_MARKETS_AVAILABLE"
    elif not two_way_count and over_only_count:
        state = "TWO_WAY_PRICES_MISSING"
        structural_error = True
    elif trackable_count:
        state = "SHADOW_EVIDENCE_READY"
    elif two_way_count:
        state = "HEALTHY_NO_QUALIFYING_EDGE"
    elif over_only_count:
        state = "ONE_SIDED_FEED_NO_QUALIFYING_EDGE"
    else:
        state = "PRICE_SHAPE_UNUSABLE"
        structural_error = True

    # A newly generated JSON file must never reset the age of its source data.
    # Preserve more specific structural failures before inspecting freshness.
    if not structural_error and upcoming_lines:
        if freshness_problems:
            state = ("CAPTURE_PARTIALLY_STALE_OR_INVALID" if fresh_upcoming_lines
                     else freshness_problems.most_common(1)[0][0])
            structural_error = True
        elif missing_comparison_rows:
            state = "COMPARISON_BEHIND_CAPTURE"
            structural_error = True
    if line_rows and not upcoming_lines and not structural_error:
        state = "NO_UPCOMING_CAPTURED_EVENTS"
    actionable = not structural_error and bool(upcoming_lines)
    current_comparisons = [row for row in comparison_rows
                           if upcoming_row(row, as_of, now_utc) and capture_problem(row, now_utc) is None]
    actionable_shadow = sum(row.get("trackable_shadow") == "true" for row in current_comparisons) if actionable else 0
    actionable_public = sum(row.get("bettable") == "true" for row in current_comparisons) if actionable else 0
    if structural_error and break_line_rows:
        break_state = "PIPELINE_UNHEALTHY"

    if current_history and current_history.get('output_hashes'):
        stale_inputs = [row for row in current_comparisons
                       if row.get('market') in ('aces', 'double_faults') and row.get('matched_board') == 'yes'
                       and (row.get('history_version') != current_history.get('version')
                            or row.get('history_as_of') != as_of
                            or row.get('history_fingerprint') != current_history['output_hashes'].get('player-props-baseline.csv'))]
        if stale_inputs:
            state = 'PLAYER_HISTORY_COMPARISON_STALE'
            structural_error = True
            actionable_shadow = actionable_public = 0
            if break_line_rows: break_state = 'PIPELINE_UNHEALTHY'
    if current_history is not None and current_history['state'] != 'CURRENT':
        state = 'PLAYER_HISTORY_BLOCKED'
        structural_error = True
        actionable_shadow = actionable_public = 0
        if break_line_rows: break_state = "PIPELINE_UNHEALTHY"
    return {
        "player_history": current_history,
        "generated_at": now_utc.isoformat(timespec="seconds"),
        "as_of": as_of,
        "state": state,
        "structural_error": structural_error,
        "max_capture_age_hours": MAX_CAPTURE_AGE_HOURS,
        "upcoming_line_rows": len(upcoming_lines),
        "fresh_upcoming_line_rows": len(fresh_upcoming_lines),
        "freshness_problems": dict(freshness_problems),
        "uncompared_upcoming_rows": missing_comparison_rows,
        "markets": market_health,
        "lines_file": str(lines_path),
        "comparison_file": str(comparison_path),
        "line_rows": len(line_rows),
        "eligible_line_rows": eligible_line_count,
        "past_event_line_rows": past_line_count,
        "comparison_rows": len(comparison_rows),
        "matched_rows": match_count,
        "unmatched_rows": max(0, len(comparison_rows) - match_count),
        "match_rate_pct": round(match_count / len(comparison_rows) * 100.0, 1)
        if comparison_rows
        else 0.0,
        "two_way_rows": two_way_count,
        "over_only_rows": over_only_count,
        "milestone_rows": milestone_count,
        "market_devig_available": two_way_count > 0,
        "milestone_note": "One-sided ace/DF milestones are valid offered bets. Evaluate model probability against the offered odds; no margin-free market probability can be inferred from one price.",
        "two_way_rate_pct": round(two_way_count / len(comparison_rows) * 100.0, 1)
        if comparison_rows
        else 0.0,
        "trackable_shadow_rows": trackable_count,
        "public_bettable_rows": bettable_count,
        "actionable_shadow_rows": actionable_shadow,
        "actionable_public_rows": actionable_public,
        "shadow_signals_for_event_date": len(as_of_signals),
        "break_state": break_state,
        "break_line_rows": len(break_line_rows),
        "break_comparison_rows": len(break_comparison_rows),
        "break_matched_rows": len(break_matched_rows),
        "break_trackable_rows": len(break_trackable_rows),
        "break_strict_rows": len(break_strict_rows),
        "break_single_source_rows": len(break_single_source_rows),
        "break_calibration_rows": len(break_calibration_rows),
        "top_break_blocker": break_blockers.most_common(1)[0][0] if break_blockers else "none",
        "latest_capture_utc": latest_capture.isoformat(timespec="seconds")
        if latest_capture
        else None,
        "capture_age_hours": round(capture_age, 2) if capture_age is not None else None,
        "top_shadow_blocker": blockers.most_common(1)[0][0] if blockers else "none",
    }


def write_report(path: Path, payload: dict[str, object]) -> None:
    lines = [
        "Tennis props pipeline health",
        f"Generated: {payload['generated_at']}",
        f"As of: {payload['as_of']}",
        f"State: {payload['state']}",
        f"Upcoming capture freshness: {payload['fresh_upcoming_line_rows']}/{payload['upcoming_line_rows']} rows; uncompared={payload['uncompared_upcoming_rows']}",
        f"Actionable now: shadow={payload['actionable_shadow_rows']} public={payload['actionable_public_rows']}",
        "",
        f"Captured lines: {payload['line_rows']} ({payload['lines_file']})",
        f"Eligible event-date lines: {payload['eligible_line_rows']} (past excluded: {payload['past_event_line_rows']})",
        f"Comparison rows: {payload['comparison_rows']} ({payload['comparison_file']})",
        f"Board matches: {payload['matched_rows']} ({payload['match_rate_pct']}%; unmatched={payload['unmatched_rows']})",
        f"Price shape: two-way={payload['two_way_rows']} ({payload['two_way_rate_pct']}%), over-only={payload['over_only_rows']}",
        f"Prospective shadow candidates: {payload['trackable_shadow_rows']}",
        f"Public bettable candidates: {payload['public_bettable_rows']}",
        f"Signals for event date: {payload['shadow_signals_for_event_date']}",
        f"Service breaks: {payload['break_state']} | captured={payload['break_line_rows']} compared={payload['break_comparison_rows']} matched={payload['break_matched_rows']} strict={payload['break_strict_rows']} Bet365-only={payload['break_single_source_rows']} calibration={payload['break_calibration_rows']}",
        f"Top service-break blocker: {payload['top_break_blocker']}",
        f"Latest capture: {payload['latest_capture_utc']} (age {payload['capture_age_hours']}h)",
        f"Top shadow blocker: {payload['top_shadow_blocker']}",
        "",
        "Interpretation:",
        "- Over-only prices are prospective research evidence, not public recommendations.",
        "- Ace/DF milestones can legitimately have one price; missing opposite prices prevent market de-vig, not model EV.",
        "- No qualifying edge is a valid result; a missing comparison after capture is not.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit tennis props capture-to-shadow plumbing")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--lines", default="")
    parser.add_argument("--comparison", default="")
    parser.add_argument("--signals", default=str(DEFAULT_SIGNALS))
    parser.add_argument("--json", default=str(DEFAULT_JSON))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    combined = PROPS / "inbox" / f"tennis-props-lines-{args.date}.csv"
    lines_path = Path(args.lines) if args.lines else (combined if combined.exists() else PROPS / "inbox" / f"bet365-lines-{args.date}.csv")
    comparison_path = (
        Path(args.comparison)
        if args.comparison
        else PROPS / f"comparison-{args.date}.csv"
    )
    payload = build_health(args.date, lines_path, comparison_path, Path(args.signals))
    json_path = Path(args.json)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_report(Path(args.report), payload)
    print(
        f"Tennis props health: {payload['state']} | "
        f"lines={payload['line_rows']} matched={payload['matched_rows']} "
        f"shadow={payload['trackable_shadow_rows']}"
    )
    return 1 if args.strict and payload["structural_error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
