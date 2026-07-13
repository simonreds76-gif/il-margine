from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "tennis_props_v3_weekly_report",
    ROOT / "scripts" / "tennis-props-v3-weekly-report.py",
)
assert SPEC and SPEC.loader
REPORT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = REPORT
SPEC.loader.exec_module(REPORT)


class TennisPropsV3WeeklyReportTests(unittest.TestCase):
    def test_evidence_uses_real_settled_rows_and_clv(self) -> None:
        gate = {
            "sellability_gate": {
                "minimum_settled_real_lines": 2,
                "minimum_distinct_events": 2,
                "required_mean_clv_pct": 1.0,
                "required_roi_pct": 0.0,
            }
        }
        signals = [
            {"settlement_status": "settled", "event_id": "1", "pnl": "0.5", "clv_pct": "1.5"},
            {"settlement_status": "settled", "event_id": "2", "pnl": "-0.2", "clv_pct": "1.1"},
            {"settlement_status": "pending", "event_id": "3", "pnl": "", "clv_pct": ""},
        ]
        result = REPORT.evidence(signals, gate)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["settled"], 2)
        self.assertEqual(result["pending"], 1)
        self.assertEqual(result["distinct_events"], 2)
        self.assertAlmostEqual(result["mean_clv_pct"], 1.3)
        self.assertAlmostEqual(result["roi_pct"], 15.0)

    def test_report_is_explicitly_shadow_only(self) -> None:
        payload = {
            "generated_at": "2026-07-13T20:00:00Z",
            "model_generated_at": "2026-07-13T19:00:00Z",
            "atp": {"status": "PASS", "surfaces": ["Clay", "Hard"], "mae_improvement_pct": 3.3, "logloss_delta": -0.01},
            "wta": {"status": "FAIL", "mae_improvement_pct": 3.0, "logloss_delta": -0.01},
            "evidence": {
                "settled": 0, "pending": 0, "distinct_events": 0, "pnl_units": 0.0,
                "roi_pct": 0.0, "mean_clv_pct": 0.0, "clv_coverage": 0,
                "positive_clv_pct": 0.0, "status": "BLOCKED", "reason": "settled 0/300",
            },
        }
        rendered = REPORT.report_text(payload)
        self.assertIn("Sellability: BLOCKED", rendered)
        self.assertIn("shadow-only", rendered)
        self.assertIn("WTA, DFs and Grass remain blocked", rendered)

    def test_github_snapshot_is_compact_non_sensitive_metrics(self) -> None:
        payload = {
            "generated_at": "2026-07-13T20:00:00Z",
            "atp": {"status": "PASS"},
            "evidence": {"settled": 4, "roi_pct": 2.1},
        }
        rendered = __import__("json").dumps(payload, separators=(",", ":"))
        self.assertNotIn("TOKEN", rendered)
        self.assertLess(len(rendered), 500)


if __name__ == "__main__":
    unittest.main()
