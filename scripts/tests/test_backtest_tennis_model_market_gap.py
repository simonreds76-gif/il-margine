from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]


def load_script():
    spec = importlib.util.spec_from_file_location("backtest_tennis_model_market_gap", SCRIPTS / "backtest-tennis-model-market-gap.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODEL = load_script()


class HistoricalGapReplayTests(unittest.TestCase):
    def spread_row(self) -> dict[str, str]:
        return {
            "date_iso": "2026-07-13",
            "captured_at": "2026-07-13T10:00:00+00:00",
            "surface": "Hard",
            "series": "ATP",
            "league": "ATP",
            "player1": "Player One",
            "player2": "Player Two",
            "p1_match_prob": "0.80",
            "spread_line": "-2.5",
            "spread_odds1": "1.90",
            "spread_odds2": "1.90",
            "margin_p1": "3",
        }

    def test_paired_replay_orients_reversed_ml_history(self) -> None:
        history = {
            "capture_date": "2026-07-13",
            "captured_at": "2026-07-13T09:00:00+00:00",
            "player1_name": "Player Two",
            "player2_name": "Player One",
            "odds1": "1.50",
            "odds2": "2.50",
            "league_name": "ATP Test",
        }
        rows, reasons = MODEL.replay_paired_spreads(
            [self.spread_row()],
            MODEL.history_index([history]),
        )
        self.assertFalse(reasons)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["selected_player"], "Player One")
        self.assertEqual(rows[0]["selected_ml_odds"], 2.5)
        self.assertEqual(rows[0]["spread_selected_line"], -2.5)
        self.assertEqual(rows[0]["spread_outcome"], "WIN")

    def test_history_after_spread_capture_is_rejected(self) -> None:
        history = {
            "capture_date": "2026-07-13",
            "captured_at": "2026-07-13T11:00:00+00:00",
            "player1_name": "Player One",
            "player2_name": "Player Two",
            "odds1": "2.50",
            "odds2": "1.50",
        }
        rows, reasons = MODEL.replay_paired_spreads(
            [self.spread_row()],
            MODEL.history_index([history]),
        )
        self.assertEqual(rows, [])
        self.assertEqual(reasons["no_ml_snapshot_before_spread_capture"], 1)

    def test_historical_report_cannot_promote_small_positive_subset(self) -> None:
        paired = []
        for index in range(5):
            paired.append(
                {
                    "ml_outcome": "LOSS",
                    "ml_pnl_units": -1.0,
                    "spread_outcome": "WIN",
                    "spread_pnl_units": 0.9,
                    "spread_available": "1",
                    "ml_ev_pct": 150.0,
                    "year": "2026",
                    "surface": "Hard",
                    "series": "ATP",
                    "ev_bucket": "100-200%",
                    "gap_bucket": "25pp+",
                    "diagnosis_primary": "paired_capture_gap",
                }
            )
        report = MODEL.build_report([], paired, 0, MODEL.Counter())
        self.assertEqual(report["screening_verdict"], "INSUFFICIENT_REAL_SPREAD_SAMPLE")
        self.assertEqual(report["long_ev_100_plus"]["spread"]["settled"], 5)

    def test_threshold_partition_is_disjoint_and_keeps_side_flips_blocked(self) -> None:
        rows = [
            {"ml_outcome": "WIN", "ml_pnl_units": 1.0, "model_market_gap_pp": 8.0, "side_flip": 0},
            {"ml_outcome": "LOSS", "ml_pnl_units": -1.0, "model_market_gap_pp": 12.0, "side_flip": 0},
            {"ml_outcome": "LOSS", "ml_pnl_units": -1.0, "model_market_gap_pp": 4.0, "side_flip": 1},
        ]
        result = MODEL.threshold_partition(rows, 10.0)
        self.assertEqual(result["allowed"]["settled"], 1)
        self.assertEqual(result["blocked"]["settled"], 2)
        self.assertEqual(result["gap_blocked"]["settled"], 1)
        self.assertEqual(result["side_flip_blocked"]["settled"], 1)
        self.assertEqual(result["blocked_side_flips"], 1)

    def test_registered_profiles_are_evaluated_without_the_gap_guard(self) -> None:
        row = {
            "surface": "Hard",
            "series": "Masters 1000",
            "confidence": "high",
            "ml_ev_pct": 16.0,
            "short_favorite_guard": 0,
        }
        self.assertTrue(MODEL.profile_eligible(row, "strict"))
        self.assertTrue(MODEL.profile_eligible(row, "volume_200"))
        row["short_favorite_guard"] = 1
        self.assertFalse(MODEL.profile_eligible(row, "strict"))

    def test_registered_replacement_experiments_are_frozen_and_same_side_only(self) -> None:
        definition = MODEL.REGISTERED_REPLACEMENT_EXPERIMENTS["strict_gap_10_20_same_side"]
        base = {
            "surface": "Hard",
            "series": "Masters 1000",
            "confidence": "high",
            "ml_ev_pct": 18.0,
            "short_favorite_guard": 0,
            "side_flip": 0,
            "ml_outcome": "WIN",
            "ml_pnl_units": 1.0,
        }
        rows = [
            {**base, "model_market_gap_pp": 10.1},
            {**base, "model_market_gap_pp": 20.0},
            {**base, "model_market_gap_pp": 20.1},
            {**base, "model_market_gap_pp": 12.0, "side_flip": 1},
        ]
        selected = MODEL.registered_replacement_rows(rows, definition)
        self.assertEqual(len(selected), 2)
        self.assertEqual([row["model_market_gap_pp"] for row in selected], [10.1, 20.0])


if __name__ == "__main__":
    unittest.main()
