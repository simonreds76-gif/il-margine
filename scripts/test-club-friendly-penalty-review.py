#!/usr/bin/env python3
"""Regression checks for club-friendly penalty evidence."""

from __future__ import annotations

import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    review_mod = runpy.run_path(str(ROOT / "scripts" / "goalscorer-live-penalty-review.py"))
    build_rows = review_mod["build_live_review_rows"]
    resolve_active_team = review_mod["_resolve_active_team"]
    globals_map = build_rows.__globals__

    settlement_mod = runpy.run_path(str(ROOT / "scripts" / "settlement_utils.py"))
    team_name_match_score = settlement_mod["team_name_match_score"]
    assert resolve_active_team(
        "Newcastle United",
        ["Manchester United"],
        team_name_match_score,
    ) == ""
    assert resolve_active_team(
        "Elversberg",
        ["SV Elversberg"],
        team_name_match_score,
    ) == "SV Elversberg"

    globals_map["_fetch_json"] = lambda *_args, **_kwargs: {
        "leagues": [
            {
                "id": 915708,
                "name": "Club Friendlies",
                "matches": [
                    {
                        "id": 5900295,
                        "home": {"id": 1, "name": "Nancy"},
                        "away": {"id": 2, "name": "Troyes"},
                        "status": {"started": True, "finished": True, "utcTime": "2026-07-11T10:00:00Z"},
                    }
                ],
            }
        ]
    }
    globals_map["_fetch_match_payload"] = lambda _match_id: {
        "props": {
            "pageProps": {
                "general": {
                    "homeTeam": {"id": 1, "name": "Nancy"},
                    "awayTeam": {"id": 2, "name": "Troyes"},
                    "matchTimeUTCDate": "2026-07-11T10:00:00Z",
                },
                "content": {
                    "shotmap": {
                        "shots": [
                            {
                                "situation": "Penalty",
                                "period": "SecondHalf",
                                "teamId": 2,
                                "fullName": "Tawfik Bentayeb",
                                "min": 64,
                                "eventType": "Goal",
                            },
                            {
                                "situation": "Penalty",
                                "period": "SecondHalf",
                                "teamId": 1,
                                "fullName": "Nancy Taker",
                                "min": 80,
                                "eventType": "Goal",
                            },
                        ]
                    }
                },
            }
        }
    }

    rows = build_rows("ligue-1", ["20260711"])
    assert len(rows) == 1, rows
    row = rows[0]
    assert row["team"] == "Troyes", row
    assert row["actual_taker"] == "Tawfik Bentayeb", row
    assert row["competition"] == "Club Friendlies", row
    assert row["review_source"] == "fotmob_friendly", row
    assert row["evidence_strength"] == "supporting", row
    assert row["is_friendly"] == 1, row
    assert row["review_priority"] == "medium", row
    assert "do not change the hierarchy from this event alone" in row["editorial_note"], row

    baseline_mod = runpy.run_path(str(ROOT / "scripts" / "build-penalty-baseline-evidence.py"))
    payload = baseline_mod["build_payload"](
        "ligue-1",
        [],
        [
            row,
            {
                **row,
                "date": "2026-08-22",
                "review_source": "fotmob_live",
                "competition": "Ligue 1",
                "evidence_strength": "competitive",
                "is_friendly": 0,
            },
        ],
    )
    assert payload["excluded_supporting_rows"] == 1, payload
    assert payload["row_count"] == 1, payload
    assert payload["rows"][0]["observed_team_penalties"] == 1, payload

    print("CLUB_FRIENDLY_PENALTY_REVIEW_OK")


if __name__ == "__main__":
    main()
