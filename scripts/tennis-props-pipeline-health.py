#!/usr/bin/env python3
"""Write an explicit health state for the tennis props evidence pipeline."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROPS = ROOT / "data" / "tennis-props"
DEFAULT_SIGNALS = PROPS / "shadow" / "aces-dfs-shadow-signals.csv"
DEFAULT_JSON = PROPS / "pipeline-health.json"
DEFAULT_REPORT = PROPS / "pipeline-health.txt"


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
    eligible_line_count, past_line_count = event_date_counts(line_rows, as_of)
    trackable_count = sum(row.get("trackable_shadow") == "true" for row in comparison_rows)
    bettable_count = sum(row.get("bettable") == "true" for row in comparison_rows)
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
    break_blockers = Counter(
        str(row.get("shadow_block_reasons") or "none").split("|")[0]
        for row in break_matched_rows
        if row.get("trackable_shadow") != "true"
    )
    if not break_line_rows:
        break_state = "PRICE_FEED_MISSING"
    elif not break_comparison_rows or not break_matched_rows:
        break_state = "BOARD_MATCH_FAILED"
    elif break_trackable_rows:
        break_state = "SHADOW_WATCHLIST_READY"
    else:
        break_state = "NO_QUALIFYING_EDGE"

    structural_error = False
    if not line_rows:
        state = "FEED_MISSING"
    elif not comparison_path.exists() or not comparison_rows:
        state = "COMPARISON_MISSING"
        structural_error = True
    elif not match_count:
        state = "BOARD_MATCH_FAILED"
        structural_error = True
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

    return {
        "generated_at": now_utc.isoformat(timespec="seconds"),
        "as_of": as_of,
        "state": state,
        "structural_error": structural_error,
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
        "two_way_rate_pct": round(two_way_count / len(comparison_rows) * 100.0, 1)
        if comparison_rows
        else 0.0,
        "trackable_shadow_rows": trackable_count,
        "public_bettable_rows": bettable_count,
        "shadow_signals_for_event_date": len(as_of_signals),
        "break_state": break_state,
        "break_line_rows": len(break_line_rows),
        "break_comparison_rows": len(break_comparison_rows),
        "break_matched_rows": len(break_matched_rows),
        "break_trackable_rows": len(break_trackable_rows),
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
        "",
        f"Captured lines: {payload['line_rows']} ({payload['lines_file']})",
        f"Eligible event-date lines: {payload['eligible_line_rows']} (past excluded: {payload['past_event_line_rows']})",
        f"Comparison rows: {payload['comparison_rows']} ({payload['comparison_file']})",
        f"Board matches: {payload['matched_rows']} ({payload['match_rate_pct']}%; unmatched={payload['unmatched_rows']})",
        f"Price shape: two-way={payload['two_way_rows']} ({payload['two_way_rate_pct']}%), over-only={payload['over_only_rows']}",
        f"Prospective shadow candidates: {payload['trackable_shadow_rows']}",
        f"Public bettable candidates: {payload['public_bettable_rows']}",
        f"Signals for event date: {payload['shadow_signals_for_event_date']}",
        f"Service breaks: {payload['break_state']} | captured={payload['break_line_rows']} compared={payload['break_comparison_rows']} matched={payload['break_matched_rows']} watchlist={payload['break_trackable_rows']}",
        f"Top service-break blocker: {payload['top_break_blocker']}",
        f"Latest capture: {payload['latest_capture_utc']} (age {payload['capture_age_hours']}h)",
        f"Top shadow blocker: {payload['top_shadow_blocker']}",
        "",
        "Interpretation:",
        "- Over-only prices are prospective research evidence, not public recommendations.",
        "- A populated comparison with zero two-way prices is a feed-shape failure, not a no-edge day.",
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

    lines_path = Path(args.lines) if args.lines else PROPS / "inbox" / f"bet365-lines-{args.date}.csv"
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
