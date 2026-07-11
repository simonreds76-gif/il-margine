#!/usr/bin/env python3
"""Forward-schema regression for internal Fair Odds Lab exposure rows."""

from __future__ import annotations

import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FORWARD_FIELDS = (
    "model_version",
    "calibration_version",
    "p_calibrated",
    "edge_vs_novig_pp",
    "pinnacle_odds_at_publish",
    "tracking_tier",
)


def main() -> None:
    module = runpy.run_path(str(ROOT / "scripts" / "generate-fair-odds-lab.py"))
    candidate = module["Candidate"](
        row={
            "match_date": "2026-08-15",
            "home_team": "Arsenal",
            "away_team": "Liverpool",
            "player_name": "Example Player",
            "canonical_player_name": "Example Player",
            "player_team": "Arsenal",
            "opponent": "Liverpool",
            "competition": "England - Premier League",
            "bookmaker": "Bet365",
            "position_group": "FW",
            "lineup_state": "confirmed_starter",
        },
        best_odds=3.5,
        model_prob_pct=32.0,
        fair_odds=3.125,
        implied_pct=28.5714,
        price_gap_pp=3.4286,
        recent_npxg=0.5,
        team_xg=1.7,
        team_share=0.25,
        opponent_xga=1.3,
        fixture_swing=0.1,
        expected_minutes=80.0,
        team_form=None,
        opponent_form=None,
    )
    row = module["exposure_row_from_candidate"](candidate)
    missing = [field for field in REQUIRED_FORWARD_FIELDS if not str(row.get(field) or "").strip()]
    assert not missing, missing
    assert row["model_version"] == "goalscorer_v1_raw"
    assert row["calibration_version"] == "raw_incumbent_v0"
    assert row["p_calibrated"] == row["model_p_atgs"]
    assert row["tracking_tier"] == "display_row"
    assert all(field in module["FAIR_ODDS_LAB_LOG_FIELDS"] for field in REQUIRED_FORWARD_FIELDS)
    print("GOALSCORER_LEDGER_SCHEMA_OK")


if __name__ == "__main__":
    main()
