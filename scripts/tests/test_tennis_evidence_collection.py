from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import date
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]


def load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


COVERAGE = load_script("tennis_derivatives_pinnacle_coverage", "tennis-derivatives-pinnacle-coverage.py")
EVIDENCE = load_script("tennis_derivatives_evidence_report", "tennis-derivatives-evidence-report.py")


class TennisEvidenceCollectionTests(unittest.TestCase):
    def test_pinnacle_snapshots_do_not_inflate_unique_offers(self) -> None:
        base = {
            "capture_date": "2026-07-12",
            "capture_mode": "close",
            "league": "ATP",
            "player1_name": "Player One",
            "player2_name": "Player Two",
            "match_date": "2026-07-13",
            "spread_line": 2.5,
            "spread_odds1": 1.91,
            "spread_odds2": 1.95,
            "ou_line": 22.5,
            "ou_over": 1.90,
            "ou_under": 1.96,
        }
        rows = [{**base, "captured_at": f"2026-07-12T0{hour}:00:00Z"} for hour in range(3)]
        summary = COVERAGE.summarise(rows, date(2026, 7, 12), date(2026, 7, 13))
        self.assertEqual(summary["snapshot_rows"], 3)
        self.assertEqual(summary["spread"]["complete_snapshot_rows"], 3)
        self.assertEqual(summary["spread"]["unique_line_offers"], 1)
        self.assertEqual(summary["spread"]["unique_line_offers_by_league"]["ATP"], 1)
        self.assertEqual(summary["total"]["unique_line_offers"], 1)
        self.assertEqual(summary["total"]["unique_matches"], 1)

    def test_props_status_reads_real_settlement_and_clv(self) -> None:
        capture = {
            "event_id": "123",
            "date": "2026-07-12",
            "tour": "ATP",
            "player": "Player One",
            "opponent": "Player Two",
            "market": "match_aces",
            "line": "9.5",
        }
        captures = [
            {**capture, "capture_ts": "2026-07-12T08:00:00Z"},
            {**capture, "capture_ts": "2026-07-12T15:00:00Z"},
        ]
        shadow = [{"settlement_status": "settled", "clv_pct": "1.20", "pnl": "0.91"}]
        status = EVIDENCE.props_status(captures, shadow)
        self.assertEqual(status["snapshot_rows"], 2)
        self.assertEqual(status["line_rows"], 1)
        self.assertEqual(status["settled_shadow_bets"], 1)
        self.assertEqual(status["mean_clv_pct"], 1.2)
        self.assertEqual(status["pnl_units"], 0.91)

    def test_totals_registered_rejection_replaces_false_sample_block(self) -> None:
        evaluation = {
            "status": "TESTED_AND_REJECTED",
            "settled_joined_rows": 7673,
            "scored_non_push_rows": 7427,
            "priced_bets": 6676,
            "edge_threshold_pct": 5.0,
            "roi_pct": -3.84,
            "roi_ci95_pct": [-6.12, -1.74],
            "mean_clv_pct": -0.086,
            "positive_clv_share_moved_pct": 38.3,
            "market_brier": 0.24982,
            "best_model_brier": 0.26040,
            "best_model": "corrected_empirical_spw",
            "decision": "No totals betting lane.",
        }
        coverage = {
            "unique_line_offers_by_league": {"ATP": 157, "Challenger": 228},
            "unique_matches_by_league": {"ATP": 150},
        }

        status = EVIDENCE.total_games_status(evaluation, coverage)

        self.assertEqual(status["promotion_status"], "TESTED_AND_REJECTED")
        self.assertEqual(status["real_line_rows"], 7427)
        self.assertEqual(status["settled_joined_rows"], 7673)
        self.assertLess(status["roi_pct"], 0)
        self.assertGreater(status["model_brier"], status["market_brier"])

    def test_spread_status_uses_canonical_scored_rows(self) -> None:
        scored = [
            {
                "p1_cover_result": "WIN",
                "market_brier": "0.24",
                "publication_timing_quality": "verified_prestart",
                "clv_eligible": "1",
            },
            {
                "p1_cover_result": "LOSS",
                "market_brier": "0.26",
                "publication_timing_quality": "inferred_prior_day",
                "clv_eligible": "0",
            },
            {
                "p1_cover_result": "PUSH",
                "market_brier": "",
                "publication_timing_quality": "same_day_unverified",
                "clv_eligible": "0",
            },
        ]
        status = EVIDENCE.spread_status(scored, [], {})
        self.assertEqual(status["real_line_rows"], 3)
        self.assertEqual(status["non_push_rows"], 2)
        self.assertEqual(status["market_brier"], 0.25)
        self.assertEqual(status["verified_prestart_rows"], 1)
        self.assertEqual(status["true_close_rows"], 1)
        self.assertEqual(status["promotion_status"], "BLOCKED_REAL_LINE_SAMPLE")

    def test_spread_status_moves_to_prospective_gate_after_600_rows(self) -> None:
        scored = [
            {
                "p1_cover_result": "WIN",
                "market_brier": "0.24",
                "publication_timing_quality": "verified_prestart",
                "clv_eligible": "1",
            }
            for _ in range(600)
        ]
        status = EVIDENCE.spread_status(scored, [], {})
        self.assertTrue(status["gates"]["real_line_rows_600"])
        self.assertEqual(
            status["promotion_status"],
            "BLOCKED_PROSPECTIVE_EVIDENCE",
        )

    def test_spread_status_exposes_registered_shape_rejection(self) -> None:
        evaluation = {
            "status": "TESTED_AND_REJECTED",
            "best_model": "push_bo3_bo5",
            "best_model_brier": 0.26099,
            "market_brier": 0.24992,
            "roi_pct": -6.04,
            "mean_clv_pct": -0.004,
            "decision": "No standalone shape lane.",
        }
        status = EVIDENCE.spread_status([], [], {}, evaluation)
        self.assertEqual(status["shape_model_status"], "TESTED_AND_REJECTED")
        self.assertGreater(
            status["shape_model_brier"],
            status["shape_market_brier"],
        )
        self.assertLess(status["shape_roi_pct"], 0)

    def test_remote_and_local_duplicate_snapshots_are_merged(self) -> None:
        row = {
            "captured_at": "2026-07-12T08:00:00Z",
            "league": "ATP",
            "player1_name": "Player One",
            "player2_name": "Player Two",
            "spread_line": "2.5",
            "spread_odds1": "1.91",
            "spread_odds2": "1.95",
            "ou_line": "22.5",
            "ou_over": "1.90",
            "ou_under": "1.96",
        }

        merged = COVERAGE.merge_rows(
            [{**row, "_coverage_source": "supabase"}],
            [{**row, "_coverage_source": "local"}],
        )

        self.assertEqual(len(merged), 1)


if __name__ == "__main__":
    unittest.main()
