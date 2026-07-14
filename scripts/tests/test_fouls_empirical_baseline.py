from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("fouls_empirical_baseline", SCRIPTS / "fouls-empirical-baseline.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FoulsEmpiricalBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = MODULE.load_rows(MODULE.DEFAULT_SOURCE)
        cls.payload = MODULE.build_payload(cls.rows, MODULE.DEFAULT_SOURCE)

    def test_registered_sample_and_pooled_structure(self) -> None:
        self.assertEqual(self.payload["usable_rows"], 21_587)
        pooled = self.payload["leg_structure"]["pooled"]
        self.assertAlmostEqual(pooled["home_mean"], 12.37, places=2)
        self.assertAlmostEqual(pooled["away_mean"], 12.68, places=2)
        self.assertAlmostEqual(pooled["total_vmr"], 1.588, places=3)
        self.assertAlmostEqual(pooled["home_away_correlation"], 0.182, places=3)

    def test_registered_referee_prior(self) -> None:
        referee = self.payload["referee"]
        self.assertEqual(referee["eligible_epl_referees"], 36)
        self.assertAlmostEqual(referee["within_referee_sd"], 4.97, places=2)
        self.assertAlmostEqual(referee["true_between_referee_sd"], 1.15, places=2)
        self.assertAlmostEqual(referee["empirical_k"], 18.6, places=1)
        self.assertEqual(referee["registered_k"], 18)

    def test_registered_feature_priors_and_lines(self) -> None:
        priors = self.payload["feature_priors"]
        self.assertAlmostEqual(priors["home_fouls_vs_home_yellows_correlation"], 0.371, places=3)
        self.assertAlmostEqual(priors["opening_1x2_closeness_vs_total_fouls_correlation"], 0.202, places=2)
        self.assertAlmostEqual(priors["total_shots_vs_total_fouls_correlation"], -0.183, places=3)
        self.assertAlmostEqual(self.payload["cards"]["match_total_vmr"], 1.123, places=3)
        self.assertEqual(
            self.payload["line_grid_and_span"]["registered_line_grid"],
            [9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5],
        )


if __name__ == "__main__":
    unittest.main()
