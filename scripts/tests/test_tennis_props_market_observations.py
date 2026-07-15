from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "tennis-props-market-observations.py"
SPEC = importlib.util.spec_from_file_location("tennis_props_market_observations", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def clean_row(**overrides: str) -> dict[str, str]:
    row = {
        "date": "2026-07-15",
        "tour": "ATP",
        "tournament": "Gstaad",
        "surface": "Clay",
        "player": "Player One",
        "opponent": "Player Two",
        "market": "match_aces",
        "scope": "match_total",
        "line": "9.5",
        "over_odds": "1.91",
        "under_odds": "1.91",
        "event_id": "event-1",
        "bookmaker": "Bet365",
        "matched_board": "yes",
        "price_pair_status": "two_way",
        "line_quality": "complete",
        "main_line": "true",
        "projection_mean": "9.0",
        "fair_p_over": "0.44",
        "fair_p_under": "0.56",
        "fair_p_push": "0",
        "distribution": "negative_binomial",
        "totals_alpha": "0.20",
    }
    row.update(overrides)
    return row


class TennisPropsMarketObservationTests(unittest.TestCase):
    def test_only_complete_main_match_total_is_observed(self) -> None:
        self.assertTrue(MODULE.is_clean_main_line(clean_row()))
        self.assertFalse(MODULE.is_clean_main_line(clean_row(main_line="false")))
        self.assertFalse(MODULE.is_clean_main_line(clean_row(line_quality="deep_alt")))
        self.assertFalse(MODULE.is_clean_main_line(clean_row(market="aces", scope="player")))

    def test_observation_id_deduplicates_player_order(self) -> None:
        first = clean_row(event_id="")
        second = clean_row(event_id="", player="Player Two", opponent="Player One")
        self.assertEqual(MODULE.observation_id(first), MODULE.observation_id(second))

    def test_metadata_backfill_does_not_rewrite_opening_price(self) -> None:
        observation = MODULE.build_observation(clean_row(surface=""), SCRIPT, "2026-07-15T10:00:00+00:00")
        original_price = observation["observed_over_odds"]
        MODULE.backfill_metadata(observation, clean_row(surface="Clay", over_odds="2.40"))
        self.assertEqual(observation["surface"], "Clay")
        self.assertEqual(observation["observed_over_odds"], original_price)

    def test_implied_mean_inverts_distribution_probability(self) -> None:
        line = 9.5
        mean = 10.8
        over, under, _push = MODULE.count_line_probabilities(
            line,
            mean,
            distribution="negative_binomial",
            alpha=0.20,
            tour="ATP",
            market="match_aces",
        )
        recovered = MODULE.implied_mean(
            line=line,
            target_over=over / (over + under),
            distribution="negative_binomial",
            alpha=0.20,
            tour="ATP",
            market="match_aces",
        )
        self.assertIsNotNone(recovered)
        self.assertAlmostEqual(recovered or 0.0, mean, places=5)

    def test_integer_push_is_excluded_from_binary_scores(self) -> None:
        row = MODULE.build_observation(clean_row(line="10.0"), SCRIPT, "2026-07-15T10:00:00+00:00")
        row["actual"] = "10"
        MODULE.score_settled_row(row)
        self.assertEqual(row["outcome_over"], "push")
        self.assertEqual(row.get("model_brier", ""), "")
        self.assertNotEqual(row.get("model_count_abs_error", ""), "")

    def test_non_push_scores_model_and_market(self) -> None:
        row = MODULE.build_observation(clean_row(), SCRIPT, "2026-07-15T10:00:00+00:00")
        row["actual"] = "12"
        MODULE.score_settled_row(row)
        self.assertEqual(row["outcome_over"], "1")
        self.assertGreater(float(row["model_brier"]), 0.0)
        self.assertGreater(float(row["observed_market_brier"]), 0.0)


if __name__ == "__main__":
    unittest.main()
