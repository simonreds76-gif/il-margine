from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import corners_nb  # noqa: E402
import football_counts as counts  # noqa: E402
import team_shots_probability as shots  # noqa: E402


def legacy_r_pmf(k: int, mean: float, r: float) -> float:
    mean = max(0.05, float(mean))
    r = max(1.25, min(500.0, float(r)))
    p = r / (r + mean)
    return math.exp(
        math.lgamma(k + r)
        - math.lgamma(r)
        - math.lgamma(k + 1)
        + r * math.log(p)
        + k * math.log1p(-p)
    )


def legacy_alpha_cdf(k: int, mean: float, alpha: float) -> float:
    if k < 0:
        return 0.0
    if alpha <= 0.0:
        return counts.poisson_cdf(k, mean)
    r = 1.0 / alpha
    return min(1.0, sum(legacy_r_pmf(value, mean, r) for value in range(k + 1)))


class FootballCountsTests(unittest.TestCase):
    def test_dispersion_converters_round_trip(self) -> None:
        for r in (1.25, 4.0, 40.0, 80.0, 500.0):
            self.assertAlmostEqual(counts.alpha_to_r(counts.r_to_alpha(r)), r, places=12)
        self.assertTrue(math.isinf(counts.alpha_to_r(0.0)))

    def test_corners_r_wrapper_matches_legacy_values(self) -> None:
        for mean in (7.5, 10.2, 14.0):
            for r in (1.25, 12.0, 80.0, 500.0):
                for k in (0, 5, 10, 18):
                    self.assertAlmostEqual(
                        corners_nb.nb_pmf(k, mean, r),
                        legacy_r_pmf(k, mean, r),
                        places=12,
                    )

    def test_team_shots_alpha_wrapper_matches_legacy_values(self) -> None:
        for mean in (8.0, 12.0, 18.0):
            for alpha in (0.0, 0.03, 0.10, 0.25):
                for k in (5, 10, 15, 25):
                    self.assertAlmostEqual(
                        shots.negbin_cdf(k, mean, alpha),
                        legacy_alpha_cdf(k, mean, alpha),
                        places=12,
                    )

    def test_integer_line_probabilities_include_push_separately(self) -> None:
        over, under, push = counts.total_probs(
            10.0,
            11.5,
            distribution="negative_binomial",
            alpha=0.08,
        )
        self.assertAlmostEqual(over + under + push, 1.0, places=12)
        self.assertAlmostEqual(push, counts.nb_pmf(10, 11.5, 0.08), places=12)

    def test_half_line_has_no_push(self) -> None:
        over, under, push = counts.total_probs(
            10.5,
            11.5,
            distribution="negative_binomial",
            alpha=0.08,
        )
        self.assertAlmostEqual(over + under, 1.0, places=12)
        self.assertEqual(push, 0.0)

    def test_dispersion_fit_is_equivalent_in_alpha_and_r(self) -> None:
        values = [7, 8, 9, 10, 12, 14, 6, 16, 11, 13] * 4
        alpha = counts.fit_dispersion_alpha(values)
        r = corners_nb.fit_dispersion(values)
        self.assertAlmostEqual(counts.alpha_to_r(alpha), r, places=12)

    def test_mle_dispersion_uses_frozen_means(self) -> None:
        observations = [(value, 10.0) for value in [2, 4, 6, 8, 10, 12, 14, 16, 18, 20] * 5]
        alpha = counts.fit_dispersion_alpha_mle(observations)
        self.assertGreater(alpha, counts.MIN_ALPHA)
        self.assertLessEqual(alpha, counts.MAX_ALPHA)


if __name__ == "__main__":
    unittest.main()
