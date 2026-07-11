#!/usr/bin/env python3
"""Regression checks for shared goalscorer minutes and share allocation."""

from __future__ import annotations

import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    model = runpy.run_path(str(ROOT / "scripts" / "goalscorer-model.py"), run_name="goalscorer_core_test")
    allocate = model["allocate_team_shares"]
    lineup_minutes = model["expected_minutes_for_lineup"]

    base = [
        {"raw_share": 0.20, "fallback_share_weight": 0.20},
        {"raw_share": 0.10, "fallback_share_weight": 0.10},
    ]
    assert allocate(base) == [0.20, 0.10]
    # Removing another market runner must not inflate the remaining player.
    assert allocate(base[:1]) == [0.20]

    scaled = allocate([
        {"raw_share": 0.70, "fallback_share_weight": 1.0},
        {"raw_share": 0.50, "fallback_share_weight": 1.0},
    ])
    assert abs(sum(scaled) - 0.90) < 1e-12
    assert abs(scaled[0] / scaled[1] - 1.4) < 1e-12

    fallback = allocate([
        {"raw_share": 0.20, "fallback_share_weight": 1.0},
        {"raw_share": 0.0, "fallback_share_weight": 2.0},
    ])
    assert fallback == [0.20, 0.02]
    all_fallback = allocate([
        {"raw_share": 0.0, "fallback_share_weight": 1.0},
        {"raw_share": 0.0, "fallback_share_weight": 3.0},
    ])
    assert all_fallback == [0.005, 0.015]
    assert abs(sum(all_fallback) - 0.02) < 1e-12

    summary = {
        "avg_start_minutes": 72.0,
        "avg_sub_minutes": 21.0,
        "avg_minutes": 55.0,
        "expected_minutes": 54.0,
    }
    assert lineup_minutes(summary, "starter") == 72.0
    assert lineup_minutes(summary, "expected_starter") == 72.0
    assert lineup_minutes(summary, "bench") == 21.0
    assert lineup_minutes(summary, "unknown") == 54.0
    assert lineup_minutes(summary, "not_in_squad") == 0.0
    print("GOALSCORER_CORE_OK")


if __name__ == "__main__":
    main()
