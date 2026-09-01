from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from fotmob_match_stats import _extract_stat_pair, _fixture_targeted


class FotMobMatchStatsTests(unittest.TestCase):
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
