from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]


def load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


AUDIT = load_script("tennis_model_market_gap_audit", "tennis-model-market-gap-audit.py")
REPORT = load_script("tennis_model_market_gap_report", "tennis-model-market-gap-report.py")


class TennisModelMarketGapAuditTests(unittest.TestCase):
    def sample_fair(self) -> dict:
        return {
            "id": 1,
            "tour_id": 99,
            "player1_id": 10,
            "player2_id": 20,
            "surface": "Clay",
            "p1_win_prob": 0.64,
            "p2_win_prob": 0.36,
            "p1_win_prob_raw": 0.63,
            "p_a": 0.65,
            "p_b": 0.61,
            "confidence": "medium",
            "spread_line": 4.5,
            "spread_odds1": 1.95,
            "spread_odds2": 1.87,
            "handicap_edge_p1": 12.0,
            "handicap_edge_p2": -8.0,
            "match_count_12m_p1": 32,
            "match_count_12m_p2": 41,
            "data_coverage_tag": "FULL",
        }

    def test_reversed_pinnacle_order_preserves_spread_orientation(self) -> None:
        pin = {
            "player1_name": "Player Two",
            "player2_name": "Player One",
            "odds1": "1.28",
            "odds2": "3.90",
            "spread_line": "-4.5",
            "spread_odds1": "1.87",
            "spread_odds2": "1.95",
            "league": "ATP",
            "league_name": "ATP Test",
            "match_date": "2026-07-13",
        }
        oriented, reason = AUDIT.orient_pinnacle("Player One", "Player Two", [pin])
        self.assertEqual(reason, "matched")
        self.assertEqual(oriented["odds1_oriented"], 3.90)
        self.assertEqual(oriented["spread_line_oriented"], 4.5)
        self.assertEqual(oriented["spread_odds1_oriented"], 1.95)

    def test_extreme_ml_gap_creates_separate_ml_and_spread_hypotheses(self) -> None:
        pin = {
            "player1_name": "Player One",
            "player2_name": "Player Two",
            "odds1": "3.90",
            "odds2": "1.28",
            "spread_line": "4.5",
            "spread_odds1": "1.95",
            "spread_odds2": "1.87",
            "league": "ATP",
            "league_name": "ATP Test",
            "match_date": "2026-07-13",
        }
        rows, status = AUDIT.anomaly_rows(
            [self.sample_fair()],
            [pin],
            {10: "Player One", 20: "Player Two"},
            {99: {"name": "ATP Test", "rank": 2}},
            datetime(2026, 7, 13, 8, tzinfo=timezone.utc),
            30.0,
            10.0,
        )
        self.assertEqual(status["anomaly_pairs"], 1)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["signal_profile"], "model_market_gap_ml_audit")
        self.assertEqual(rows[0]["side"], "P1")
        self.assertEqual(rows[1]["signal_profile"], "model_market_gap_spread_audit")
        self.assertEqual(rows[1]["side"], "P1+")
        self.assertEqual(rows[1]["spread_line"], 4.5)
        self.assertEqual(rows[1]["spread_odds"], 1.95)
        self.assertIn(rows[0]["guard_cohort"], {"gap_only", "side_flip_and_gap", "side_flip_only", "ev_only_control"})
        self.assertIn("replacement_forward_eligible", rows[0])

    def test_first_observation_dedup_does_not_replace_price(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "archive.csv"
            first = {"date": "2026-07-13", "player1_id": 10, "player2_id": 20, "signal_profile": "model_market_gap_ml_audit", "selected_odds": 3.9}
            second = {**first, "selected_odds": 4.2}
            self.assertEqual(AUDIT.append_first_observation(path, [first]), 1)
            self.assertEqual(AUDIT.append_first_observation(path, [second]), 0)
            self.assertEqual(AUDIT.load_csv(path)[0]["selected_odds"], "3.9")

    def test_report_counts_spread_rescue_separately(self) -> None:
        base = {
            "anomaly_id": "a",
            "settlement_status": "settled",
            "stake_units": "1",
            "diagnosis_primary": "component_disagreement",
        }
        rows = [
            {**base, "hypothesis": "extreme_ml_side", "bet_type": "match", "bet_outcome": "LOSS", "selected_odds": "3.9"},
            {**base, "hypothesis": "same_player_spread", "bet_type": "spread", "bet_outcome": "WIN", "selected_odds": "1.95"},
        ]
        report = REPORT.build_report(rows, [], [])
        self.assertEqual(report["paired_settled"], 1)
        self.assertEqual(report["paired_outcomes"]["ml_loss__spread_win"], 1)
        self.assertEqual(report["spread"]["pnl_units"], 0.95)
        self.assertEqual(report["weekly_review"]["verdict"], "KEEP_COLLECTING")
        self.assertFalse(report["weekly_review"]["automatic_promotion"])

    def test_long_ev_handicap_subset_is_reported_separately(self) -> None:
        base = {
            "anomaly_id": "long-ev",
            "date": "2026-07-13",
            "player1_id": "10",
            "player2_id": "20",
            "settlement_status": "settled",
            "stake_units": "1",
            "diagnosis_primary": "component_disagreement",
            "surface": "Hard",
            "series": "ATP",
            "ev_bucket": "100-200%",
            "gap_bucket": "25pp+",
            "value_pct": "150",
        }
        rows = [
            {**base, "hypothesis": "extreme_ml_side", "bet_type": "match", "bet_outcome": "LOSS", "selected_odds": "3.9"},
            {**base, "hypothesis": "same_player_spread", "bet_type": "spread", "bet_outcome": "WIN", "selected_odds": "1.95"},
        ]
        report = REPORT.build_report(rows, [], [], today=date(2026, 7, 13))
        self.assertEqual(report["long_ev_100_plus"]["spread"]["settled"], 1)
        self.assertEqual(report["segments"]["ev_bucket"]["100-200%"]["spread_rescues"], 1)

    def test_weekly_snapshot_is_upserted_by_week(self) -> None:
        report = REPORT.build_report([], [], [], today=date(2026, 7, 13))
        generated = datetime(2026, 7, 13, 9, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "weekly.csv"
            REPORT.write_weekly_snapshot(path, report, generated=generated)
            REPORT.write_weekly_snapshot(path, report, generated=generated)
            rows = REPORT.load_csv(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["week_start"], "2026-07-13")

    def test_guard_replacement_forward_gate_never_auto_promotes(self) -> None:
        historical = {
            "threshold_audit": {
                "registered_replacement_experiments": {
                    "experiments": {
                        "strict_gap_10_20_same_side": {"passes_retrospective_screen": True},
                    }
                }
            }
        }
        row = {
            "anomaly_id": "guard-1",
            "date": "2026-07-13",
            "player1_id": "1",
            "player2_id": "2",
            "settlement_status": "settled",
            "bet_outcome": "WIN",
            "bet_type": "match",
            "selected_odds": "2.0",
            "stake_units": "1",
            "surface": "Hard",
            "series": "Masters 1000",
            "confidence": "high",
            "value_pct": "20",
            "model_p1": "0.62",
            "market_p1_devig": "0.50",
            "model_market_gap_pp": "12",
            "side_flip": "0",
            "diagnostic_quality": "HIGH",
            "replacement_forward_eligible": "1",
            "replacement_cohorts": "strict_gap_10_20_same_side",
        }
        report = REPORT.build_report([row], [], [], historical_report=historical)
        experiment = report["ml_guard_replacement"]["experiments"]["strict_gap_10_20_same_side"]
        self.assertEqual(experiment["verdict"], "FORWARD_SAMPLE_BUILDING")
        self.assertFalse(report["ml_guard_replacement"]["automatic_promotion"])


if __name__ == "__main__":
    unittest.main()
