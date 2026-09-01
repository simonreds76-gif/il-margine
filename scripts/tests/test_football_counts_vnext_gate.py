from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("football_counts_vnext_gate", SCRIPTS / "football-counts-vnext-gate.py")
assert SPEC is not None and SPEC.loader is not None
GATE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = GATE
SPEC.loader.exec_module(GATE)


class FootballCountsVnextGateTests(unittest.TestCase):
    def test_team_gate_requires_both_folds_to_improve(self) -> None:
        passing = {
            "status": "OK",
            "hierarchical_mle_brier": "0.19",
            "fixed_alpha_025_brier": "0.20",
            "hierarchical_mle_log_loss": "0.56",
            "fixed_alpha_025_log_loss": "0.57",
        }
        report = "Count-distribution gate: **PASS**"
        self.assertTrue(GATE.team_count_gate([passing, passing], report))
        failing = {**passing, "hierarchical_mle_brier": "0.21"}
        self.assertFalse(GATE.team_count_gate([passing, failing], report))

    def test_corners_gate_requires_all_three_count_metrics(self) -> None:
        passing = {
            "status": "OK",
            "v3_mae": "2.70",
            "baseline_mae": "2.80",
            "v3_brier": "0.21",
            "baseline_brier": "0.22",
            "v3_log_loss": "0.61",
            "baseline_log_loss": "0.64",
        }
        report = "Count-model gate: **PASS**"
        self.assertTrue(GATE.corners_count_gate([passing, passing], report))
        failing = {**passing, "v3_log_loss": "0.65"}
        self.assertFalse(GATE.corners_count_gate([passing, failing], report))

    def test_live_summary_excludes_blocked_and_guarded_rows(self) -> None:
        rows = [
            {"side": "over", "result": "won", "pnl_units": "1.0", "true_close": "true", "published_to_close_clv": "0.02"},
            {"side": "under", "result": "lost", "pnl_units": "-1.0", "true_close": "false"},
            {"side": "over", "result": "won", "pnl_units": "1.0", "blocked_reason": "matchdays_1_to_3"},
            {"side": "over", "result": "won", "pnl_units": "1.0", "confidence_guard_applied": "true"},
        ]
        summary = GATE.live_summary(rows)
        self.assertEqual(summary["signals"], 2)
        self.assertEqual(summary["settled"], 2)
        self.assertEqual(summary["pnl_units"], 0.0)
        self.assertEqual(summary["true_close_n"], 1)
        self.assertEqual(summary["mean_true_close_clv"], 0.02)

    def test_live_summary_keeps_warmup_tracking_separate_from_authorized_sample(self) -> None:
        rows = [
            {"signal_status": "eligible", "side": "over", "result": "won", "pnl_units": "0.9"},
            {"signal_status": "warmup_tracking", "side": "under", "result": "lost", "pnl_units": "-1"},
        ]

        authorized = GATE.live_summary(rows)
        warmup = GATE.live_summary(rows, cohort="warmup_tracking")

        self.assertEqual(authorized["signals"], 1)
        self.assertEqual(authorized["pnl_units"], 0.9)
        self.assertEqual(warmup["signals"], 1)
        self.assertEqual(warmup["pnl_units"], -1.0)

    def test_corners_zero_clv_can_pass_at_the_registered_threshold(self) -> None:
        team_fold = {
            "status": "OK", "hierarchical_mle_brier": "0.19", "fixed_alpha_025_brier": "0.20",
            "hierarchical_mle_log_loss": "0.56", "fixed_alpha_025_log_loss": "0.57",
        }
        corners_fold = {
            "status": "OK", "v3_mae": "2.70", "baseline_mae": "2.80", "v3_brier": "0.21",
            "baseline_brier": "0.22", "v3_log_loss": "0.61", "baseline_log_loss": "0.64",
        }
        corners_live = [
            {
                "side": "over" if index % 2 == 0 else "under",
                "result": "won" if index % 2 == 0 else "lost",
                "pnl_units": "1" if index % 2 == 0 else "-1",
                "true_close": "true",
                "published_to_close_clv": "0.0",
            }
            for index in range(100)
        ]
        payload = GATE.build_payload(
            [team_fold, team_fold], "Count-distribution gate: **PASS**",
            [corners_fold, corners_fold], "Count-model gate: **PASS**",
            [], corners_live,
        )
        self.assertEqual(payload["corners_v3"]["promotion_gate"], "PASS")


if __name__ == "__main__":
    unittest.main()
