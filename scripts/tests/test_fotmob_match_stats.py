from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from fotmob_match_stats import _extract_stat_pair


class FotMobMatchStatsTests(unittest.TestCase):
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
