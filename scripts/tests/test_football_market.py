from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from football_market import (  # noqa: E402
    blend_logit,
    fit_blend_weight,
    fit_over_vig_share,
    proportional_devig,
    shading_aware_devig,
)


class FootballMarketTests(unittest.TestCase):
    def test_proportional_devig_sums_to_one(self) -> None:
        over, under, overround = proportional_devig(1.91, 1.91)
        self.assertAlmostEqual(over + under, 1.0, places=12)
        self.assertGreater(overround, 0.0)

    def test_equal_shading_is_symmetric_for_equal_odds(self) -> None:
        over, under, _ = shading_aware_devig(1.91, 1.91, over_vig_share=0.5)
        self.assertAlmostEqual(over, 0.5, places=12)
        self.assertAlmostEqual(under, 0.5, places=12)

    def test_fitted_shading_moves_toward_observed_side(self) -> None:
        mostly_unders = [(1.91, 1.91, False) for _ in range(80)] + [(1.91, 1.91, True) for _ in range(20)]
        share = fit_over_vig_share(mostly_unders)
        over, _, _ = shading_aware_devig(1.91, 1.91, over_vig_share=share)
        self.assertLess(over, 0.5)

    def test_blend_fit_can_reject_a_bad_model(self) -> None:
        rows = [(0.90, 0.25, False) for _ in range(50)] + [(0.10, 0.75, True) for _ in range(50)]
        self.assertEqual(fit_blend_weight(rows), 0.0)
        self.assertAlmostEqual(blend_logit(0.9, 0.25, 0.0), 0.25, places=12)


if __name__ == "__main__":
    unittest.main()
