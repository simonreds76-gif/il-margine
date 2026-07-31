from __future__ import annotations

import runpy
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = runpy.run_path(
    str(ROOT / "scripts" / "tennis-venue-ace-factor-v1-report.py"),
    run_name="venue_ace_factor_v1_report_test",
)


class VenueAceFactorV1ReportTests(unittest.TestCase):
    def test_report_is_fail_closed_and_detects_season_leakage(self) -> None:
        factors = [
            {
                "tour": "ATP",
                "tournament": "Gstaad",
                "surface": "Clay",
                "eligible": "true",
                "ace_factor": "1.64",
                "source_end_season": "2025",
                "target_season": "2026",
            },
            {
                "tour": "ATP",
                "tournament": "Bad",
                "surface": "Clay",
                "eligible": "true",
                "ace_factor": "1.20",
                "source_end_season": "2026",
                "target_season": "2026",
            },
            {
                "tour": "WTA",
                "surface": "Hard",
                "tournament": "Out of scope",
                "eligible": "true",
                "ace_factor": "1.80",
                "source_end_season": "2025",
                "target_season": "2026",
            },
        ]
        observations = [
            {
                "event_id": "event-1",
                "settlement_status": "settled",
                "pnl": "1.5",
                "clv_pct": "2.0",
            }
        ]
        payload = REPORT["build_payload"](factors, observations)
        self.assertEqual(payload["decision"], "NOT_SELLABLE")
        self.assertFalse(payload["automatic_promotion"])
        self.assertEqual(payload["integrity"]["same_or_future_season_rows"], 1)
        self.assertFalse(payload["gates"]["strictly_prior_seasons"])
        self.assertFalse(payload["gates"]["brier_improvement"])
        self.assertEqual(payload["coverage"]["eligible_venues"], 2)

    def test_paired_scoring_can_pass_only_after_full_sample(self) -> None:
        factors = [
            {
                "tour": "ATP",
                "surface": "Hard",
                "tournament": "Washington",
                "eligible": "true",
                "ace_factor": "1.10",
                "source_end_season": "2025",
                "target_season": "2026",
            }
        ]
        observations = []
        for idx in range(600):
            outcome = idx % 2
            observations.append(
                {
                    "event_id": f"event-{idx}",
                    "surface": "Hard" if idx < 300 else "Clay",
                    "settlement_status": "settled",
                    "actual": "10" if outcome else "5",
                    "line": "7.5",
                    "control_p_over_no_push": "0.40" if outcome else "0.60",
                    "candidate_p_over_no_push": "0.70" if outcome else "0.30",
                    "pnl": "0",
                }
            )
        payload = REPORT["build_payload"](factors, observations)
        self.assertLess(payload["paired_scoring"]["overall"]["brier_delta"], 0)
        self.assertTrue(payload["gates"]["brier_improvement"])
        self.assertTrue(payload["gates"]["segment_regression"])



if __name__ == "__main__":
    unittest.main()
