from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from fotmob_match_stats import _extract_stat_pair, _fixture_targeted, fetch_fotmob_recent_results


class FotMobMatchStatsTests(unittest.TestCase):
    def test_grouped_league_recovers_exact_alias_once_with_a_zero_count(self) -> None:
        day = "2026-11-21"
        match = dict(id=42, home=dict(id=1, name="Lens"), away=dict(id=2, name="Toulouse"),
                     status=dict(finished=True, utcTime=day + "T17:00:00Z"))
        board = {"leagues": [
            {"id": 900, "primaryId": 53, "matches": [match]},
            {"id": 53, "matches": [match]},
            {"id": 54, "matches": [dict(match, id=43)]},
        ]}
        general = dict(finished=True, matchId="42", leagueId=53, matchTimeUTCDate=day + "T17:00:00Z",
                       homeTeam=match["home"], awayTeam=match["away"])
        stats = {"Periods": {"All": {"stats": [{"stats": [{"key": "corners", "stats": [0, 5]}]}]}}}
        targets = [dict(date=day, home_team="Racing Club De Lens", away_team="Toulouse FC")]
        for changed, expected in [({}, True), ({"matchId": 44}, False), ({"finished": False}, False),
                                  ({"leagueId": 54}, False), ({"homeTeam": match["away"]}, False),
                                  ({"matchTimeUTCDate": "2026-11-20T17:00:00Z"}, False)]:
            with self.subTest(changed=changed), patch("fotmob_match_stats._fetch_json", return_value=board), patch(
                "fotmob_match_stats._fetch_page_props",
                return_value={"general": {**general, **changed}, "content": {"stats": stats}},
            ) as detail:
                rows = fetch_fotmob_recent_results("ligue-1", [day], targets)
                detail.assert_called_once_with(42)
                self.assertEqual(bool(rows), expected)
                if expected:
                    row = rows[day + "|lens|toulouse"]
                    self.assertEqual((row["home_corners"], row["away_corners"], row["total_corners"]), (0, 5, 5))

    def test_target_filter_avoids_unrelated_match_detail_requests(self) -> None:
        match = {
            "home": {"longName": "Real Sociedad"},
            "away": {"longName": "Celta Vigo"},
        }
        targets = [
            {
                "date": "2026-09-03",
                "home_team": "Real Sociedad San Sebastian",
                "away_team": "RC Celta de Vigo",
            }
        ]
        self.assertTrue(_fixture_targeted(match, "2026-09-03", targets))
        self.assertFalse(_fixture_targeted(match, "2026-09-04", targets))

    def test_extracts_foul_pair(self) -> None:
        payload = {
            "Periods": {
                "All": {
                    "stats": [{"stats": [{"key": "fouls", "stats": [11, 14]}]}]
                }
            }
        }
        self.assertEqual(_extract_stat_pair(payload, "fouls"), (11, 14))


if __name__ == "__main__":
    unittest.main()
