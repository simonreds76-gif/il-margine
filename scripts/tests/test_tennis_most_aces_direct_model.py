from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPTS = Path(__file__).resolve().parents[1]
PATH = SCRIPTS / "fit-tennis-most-aces-direct-1x2.py"
SPEC = importlib.util.spec_from_file_location("most_aces_direct_model", PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class MostAcesDirectModelTests(unittest.TestCase):
    def test_mirror_negates_only_signed_differences(self) -> None:
        source = pd.DataFrame([{
            "surface": "Hard",
            "ace_rate_diff": 0.2,
            "ace_rate_sum": 0.3,
            "expected_match_games": 22.0,
        }])
        mirrored = MODULE.mirror_features(source)
        self.assertEqual(mirrored.loc[0, "ace_rate_diff"], -0.2)
        self.assertEqual(mirrored.loc[0, "ace_rate_sum"], 0.3)
        self.assertEqual(mirrored.loc[0, "expected_match_games"], 22.0)

    def test_mirror_labels_swaps_player_outcomes_and_keeps_draw(self) -> None:
        actual = MODULE.mirror_labels(np.asarray([0, 1, 2]))
        np.testing.assert_array_equal(actual, np.asarray([2, 1, 0]))

    def test_temperature_probabilities_remain_normalised(self) -> None:
        probabilities = np.asarray([[0.6, 0.2, 0.2], [0.1, 0.3, 0.6]])
        adjusted = MODULE.apply_temperature(probabilities, 1.4)
        np.testing.assert_allclose(adjusted.sum(axis=1), np.ones(2))
        self.assertTrue(np.all(adjusted > 0))


if __name__ == "__main__":
    unittest.main()
