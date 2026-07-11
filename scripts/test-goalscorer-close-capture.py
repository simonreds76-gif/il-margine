#!/usr/bin/env python3
"""Regression checks for tracked-fixture close scheduling and labels."""

from __future__ import annotations

import runpy
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def classify(function, *, minutes: int, confirmed: bool, tracked: bool, include_confirmed: bool = False):
    now = datetime(2026, 8, 15, 14, 0, tzinfo=timezone.utc)
    return function(
        now,
        now + timedelta(minutes=minutes),
        already_confirmed=confirmed,
        tracked_signal=tracked,
        lineup_window_before_minutes=75,
        lineup_grace_after_minutes=20,
        close_window_before_minutes=40,
        include_distant=False,
        include_confirmed=include_confirmed,
    )


def main() -> None:
    schedule = runpy.run_path(str(ROOT / "scripts" / "goalscorer-live-schedule.py"))
    effective_tier = schedule["_effective_fixture_tier"]
    assert classify(effective_tier, minutes=30, confirmed=True, tracked=True) == "close"
    assert classify(effective_tier, minutes=30, confirmed=True, tracked=False) is None
    assert classify(effective_tier, minutes=30, confirmed=True, tracked=False, include_confirmed=True) == "lineup"
    assert classify(effective_tier, minutes=30, confirmed=False, tracked=True) == "lineup"
    assert classify(effective_tier, minutes=50, confirmed=True, tracked=True) is None

    scraper = runpy.run_path(str(ROOT / "scripts" / "odds-api-scrape-goalscorer.py"))
    snapshot_kind = scraper["snapshot_kind_for"]
    assert snapshot_kind("2026-08-15T14:55:00Z", "2026-08-15T15:00:00Z") == "pre_kickoff_5"
    assert snapshot_kind("2026-08-15T14:30:00Z", "2026-08-15T15:00:00Z") == "pre_kickoff_30"
    assert snapshot_kind("2026-08-15T13:00:00Z", "2026-08-15T15:00:00Z") == "live_capture"
    print("GOALSCORER_CLOSE_CAPTURE_OK")


if __name__ == "__main__":
    main()
