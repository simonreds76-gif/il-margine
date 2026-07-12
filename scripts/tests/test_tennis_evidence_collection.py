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


if __name__ == "__main__":
    unittest.main()
