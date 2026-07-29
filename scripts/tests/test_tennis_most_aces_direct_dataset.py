from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPTS = Path(__file__).resolve().parents[1]
PATH = SCRIPTS / "build-tennis-most-aces-direct-dataset.py"
SPEC = importlib.util.spec_from_file_location("most_aces_direct_dataset", PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def side(player_id: str, opponent_id: str, aces: int) -> dict[str, object]:
    row: dict[str, object] = {
        "date": "2025-01-01",
        "year": 2025,
        "tour": "ATP",
        "tournament": "Test Open",
        "surface": "Hard",
        "level": "A",
        "round": "R32",
        "best_of": 3,
        "player_id": player_id,
        "opponent_id": opponent_id,
        "player": f"Player {player_id}",
        "opponent": f"Player {opponent_id}",
        "actual_aces": aces,
        "player_l12m_matches": 10,
        "player_l12m_svpt": 700,
        "player_l24m_matches": 20,
        "player_l24m_svpt": 1400,
        "player_career4y_matches": 30,
        "player_career4y_svpt": 2100,
        "surface_prior_ace_rate": 0.08,
        "venue_ace_factor": 1.1,
        "expected_match_games": 22.0,
    }
    for index, metric in enumerate(MODULE.SIDE_METRICS, start=1):
        row[metric] = float(index)
    return row


class MostAcesDirectDatasetTests(unittest.TestCase):
    def test_pair_is_canonical_and_target_comes_from_realised_counts(self) -> None:
        rows = MODULE.pairwise_rows(pd.DataFrame([
            side("20", "10", 4),
            side("10", "20", 9),
        ]))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["player1_id"], "10")
        self.assertEqual(rows[0]["player2_id"], "20")
        self.assertEqual(rows[0]["outcome"], "P1")
        self.assertEqual(rows[0]["evidence_tier"], "RECENT")

    def test_pair_features_are_symmetric_sum_and_signed_difference(self) -> None:
        left = side("10", "20", 9)
        right = side("20", "10", 4)
        left["incumbent_aces"] = 8.0
        right["incumbent_aces"] = 5.0
        row = MODULE.pairwise_rows(pd.DataFrame([left, right]))[0]
        self.assertEqual(row["incumbent_aces_diff"], 3.0)
        self.assertEqual(row["incumbent_aces_sum"], 13.0)
        self.assertEqual(row["incumbent_aces_abs_diff"], 3.0)


if __name__ == "__main__":
    unittest.main()
