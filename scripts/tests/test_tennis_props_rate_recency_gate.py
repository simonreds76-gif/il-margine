from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "backtest-tennis-props-rate-recency.py"
SPEC = importlib.util.spec_from_file_location("tennis_props_rate_recency_gate", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def side() -> object:
    return MODULE.SideInput(
        current_aces=8.0,
        current_dfs=3.0,
        expected_service_points=100.0,
        prior_ace_rate=0.05,
        prior_df_rate=0.03,
        ace_environment_factor=1.0,
        df_environment_factor=1.0,
        opponent_return_factor=1.0,
        same_tournament_ace_rate=0.0,
        same_tournament_df_rate=0.0,
        same_tournament_ace_weight=0.0,
        same_tournament_df_weight=0.0,
        l12m=MODULE.WindowRate(sample=400, ace_rate=0.10, df_rate=0.06),
        l24m=MODULE.WindowRate(sample=800, ace_rate=0.07, df_rate=0.04),
        career_4y=MODULE.WindowRate(sample=1600, ace_rate=0.06, df_rate=0.035),
    )


class TennisPropsRateRecencyGateTests(unittest.TestCase):
    def test_registered_grid_contains_current_weight(self) -> None:
        self.assertIn(MODULE.CURRENT_L12M_WEIGHT, MODULE.L12M_WEIGHT_GRID)

    def test_more_l12m_weight_moves_rate_toward_recent_form(self) -> None:
        player = side()
        light = MODULE.player_rate(player, "ATP", "aces", 0.25)
        heavy = MODULE.player_rate(player, "ATP", "aces", 2.0)
        self.assertGreater(heavy, light)

    def test_zero_same_tournament_weight_leaves_blend_unchanged(self) -> None:
        player = side()
        rate = MODULE.player_rate(player, "ATP", "aces", MODULE.CURRENT_L12M_WEIGHT)
        expected = rate * player.expected_service_points
        self.assertAlmostEqual(
            MODULE.candidate_side_mean(player, "ATP", "aces", MODULE.CURRENT_L12M_WEIGHT),
            expected,
        )

    def test_df_candidate_does_not_apply_opponent_return_factor(self) -> None:
        player = side()
        changed = MODULE.SideInput(**{**player.__dict__, "opponent_return_factor": 1.22})
        self.assertAlmostEqual(
            MODULE.candidate_side_mean(player, "ATP", "dfs", 1.0),
            MODULE.candidate_side_mean(changed, "ATP", "dfs", 1.0),
        )


if __name__ == "__main__":
    unittest.main()
