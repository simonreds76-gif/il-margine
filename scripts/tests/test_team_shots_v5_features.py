from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from team_shots_v5_features import build_feature_rows, previous_season  # noqa: E402


def row(day: str, season: str, shots: int, *, venue: str = "home") -> dict[str, str]:
    return {
        "date": day,
        "league": "epl",
        "season": season,
        "team": "Example FC",
        "team_key": "example fc",
        "opponent": "Other FC",
        "opponent_key": "other fc",
        "venue": venue,
        "home_team": "Example FC" if venue == "home" else "Other FC",
        "away_team": "Other FC" if venue == "home" else "Example FC",
        "shots_for": str(shots),
        "shots_against": "10",
        "sot_for": "4",
        "sot_against": "3",
        "corners_for": "5",
        "corners_against": "4",
        "market_team_win_prob": "0.55",
        "market_opp_win_prob": "0.25",
    }


class TeamShotsV5FeatureTests(unittest.TestCase):
    def test_previous_season(self) -> None:
        self.assertEqual(previous_season("2026-2027"), "2025-2026")
        self.assertEqual(previous_season("bad"), "")

    def test_separates_current_and_prior_seasons(self) -> None:
        rows = [
            row("2026-05-20", "2025-2026", 10),
            row("2026-08-15", "2026-2027", 20),
            row("2026-08-22", "2026-2027", 30),
        ]
        features = build_feature_rows(rows)
        opening = features[1]
        second = features[2]
        self.assertEqual(opening["current_matches"], 0)
        self.assertEqual(opening["prior_matches"], 1)
        self.assertEqual(opening["prior_season_fresh"], 1)
        self.assertEqual(float(opening["prior_ema20_shots_for"]), 10.0)
        self.assertEqual(second["current_matches"], 1)
        self.assertEqual(float(second["current_ema20_shots_for"]), 20.0)

    def test_same_day_rows_do_not_leak(self) -> None:
        rows = [
            row("2026-08-15", "2026-2027", 20),
            row("2026-08-15", "2026-2027", 30, venue="away"),
        ]
        features = build_feature_rows(rows)
        self.assertEqual([item["current_matches"] for item in features], [0, 0])

    def test_stale_prior_features_are_blank(self) -> None:
        rows = [
            row("2024-05-20", "2023-2024", 10),
            row("2026-08-15", "2024-2025", 20),
        ]
        features = build_feature_rows(rows)
        self.assertEqual(features[1]["prior_season_fresh"], 0)
        self.assertEqual(features[1]["prior_ema20_shots_for"], "")


if __name__ == "__main__":
    unittest.main()
