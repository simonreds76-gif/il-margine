"""Evidence checks for an empty Team Shots capture window; no network calls."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SUPPORTED_LEAGUES = {"epl", "serie-a", "la-liga", "bundesliga", "ligue-1"}


def parse_time(value: Any) -> datetime | None:
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.astimezone(UTC) if result.tzinfo else None
    except (ValueError, TypeError):
        return None


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def load_candidates(path: Path) -> list[dict] | None:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except (OSError, ValueError):
        return None


def verified_empty_window(capture: dict, candidates: list[dict] | None, scan_at: Any) -> dict | None:
    """Require a recent, complete successful scan and no contradictory fixture.

    An absent price alone is never proof of a healthy feed. Unknown timestamps,
    incomplete diagnostics, provider errors and in-window peer fixtures retain
    the existing missing-candidates alert.
    """
    captured = parse_time(capture.get("run_at"))
    scored = parse_time(scan_at)
    if captured is None or scored is None or not timedelta(0) <= scored - captured <= timedelta(hours=3):
        return None
    if capture.get("success") is not True or capture.get("provider_errors") != [] or capture.get("error"):
        return None
    if capture.get("events_found") != 0 or capture.get("rows_scraped") != 0:
        return None
    if set(capture.get("leagues") or []) != SUPPORTED_LEAGUES:
        return None
    try:
        minutes = float(capture.get("kickoff_within_minutes", 0))
        days = float(capture["days_ahead"])
        if not 0 < days <= 7 or not 0 <= minutes <= days * 1440:
            return None
        end = captured + timedelta(minutes=minutes) if minutes else captured + timedelta(days=days)
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    diagnostics = capture.get("discovery_diagnostics")
    if not isinstance(diagnostics, list) or len(diagnostics) != len(SUPPORTED_LEAGUES):
        return None
    if {row.get("league") for row in diagnostics if isinstance(row, dict)} != SUPPORTED_LEAGUES:
        return None
    for row in diagnostics:
        start, stop = parse_time(row.get("from")), parse_time(row.get("to"))
        if start is None or stop is None or start > captured or stop < end:
            return None
        if row.get("selected_events") != 0 or row.get("kickoff_within_minutes") != capture.get("kickoff_within_minutes"):
            return None
        if row.get("state") not in {"NO_LEAGUE_EVENTS_IN_FEED", "NO_EVENTS_IN_KICKOFF_WINDOW"}:
            return None
        if not isinstance(row.get("provider_events"), int) or row["provider_events"] <= 0:
            return None
    if candidates is None:
        return None
    for row in candidates:
        kickoff = parse_time(row.get("kickoff_utc"))
        if row.get("model") != "corners_v3" or kickoff is None or captured <= kickoff <= end:
            return None
    return {
        "capture_at": capture["run_at"],
        "capture_window_end": end.isoformat().replace("+00:00", "Z"),
        "capture_run_url": capture.get("run_url"),
        "leagues_checked": sorted(SUPPORTED_LEAGUES),
        "events_found": 0,
        "peer_rows_outside_window": len(candidates),
    }
