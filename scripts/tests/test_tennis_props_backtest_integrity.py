from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
STAGE0_PATH = SCRIPTS / "backtest-tennis-player-props.py"
SPEC = importlib.util.spec_from_file_location("tennis_props_stage0_integrity", STAGE0_PATH)
assert SPEC and SPEC.loader
STAGE0 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = STAGE0
SPEC.loader.exec_module(STAGE0)

sys.path.insert(0, str(SCRIPTS))
from tennis_props_model import project_player  # noqa: E402


class TennisPropsBacktestIntegrityTests(unittest.TestCase):
    def test_venue_factor_is_shrunk_toward_one(self) -> None:
        self.assertAlmostEqual(STAGE0.shrink_venue_factor(1.20, 100), 1.10)
        self.assertAlmostEqual(STAGE0.shrink_venue_factor(0.80, 100), 0.90)
        self.assertAlmostEqual(STAGE0.shrink_venue_factor(1.20, 0), 1.00)

    def test_historical_backtest_can_disable_posthoc_slam_correction(self) -> None:
        factor = {
            "tour": "ATP",
            "tournament": "Wimbledon",
            "surface": "Grass",
            "matches": "100",
            "tour_surface_baseline_ace": "0.065",
            "tour_surface_baseline_df": "0.035",
            "ace_factor": "1.0",
            "df_factor": "1.0",
            "svpt_per_svgame": "6.35",
        }
        uncorrected = project_player(
            tour="atp",
            player_rows={},
            opponent_rows={},
            factor_row=factor,
            expected_match_games=38.5,
            slam_matches=0,
            apply_slam_bias_correction=False,
        )
        corrected = project_player(
            tour="atp",
            player_rows={},
            opponent_rows={},
            factor_row=factor,
            expected_match_games=38.5,
            slam_matches=0,
            apply_slam_bias_correction=True,
        )

        self.assertEqual(uncorrected.ace_count_correction, 0.0)
        self.assertAlmostEqual(corrected.ace_count_correction, 0.589)
        self.assertAlmostEqual(corrected.expected_aces - uncorrected.expected_aces, 0.589)


if __name__ == "__main__":
    unittest.main()
