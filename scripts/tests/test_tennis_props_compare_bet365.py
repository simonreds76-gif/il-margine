from __future__ import annotations

import importlib.util
import sys
import unittest
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
MODULE_PATH = SCRIPTS / "tennis-props-compare-bet365.py"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("tennis_props_compare_bet365", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class LegacyTeamTotalNormalizationTests(unittest.TestCase):
    def test_away_team_total_becomes_away_player_market(self) -> None:
        row = {
            "player": "Gonzalo Bueno",
            "opponent": "Tiago Pereira",
            "market": "match_aces",
            "raw_market_name": "Team Total (Aces) Away",
        }
        result = MODULE.normalize_legacy_team_total_row(row)
        self.assertEqual(result["market"], "aces")
        self.assertEqual(result["player"], "Tiago Pereira")
        self.assertEqual(result["opponent"], "Gonzalo Bueno")
        self.assertEqual(row["market"], "match_aces")

    def test_home_team_total_keeps_home_player(self) -> None:
        row = {
            "player": "Gonzalo Bueno",
            "opponent": "Tiago Pereira",
            "market": "match_double_faults",
            "raw_market_name": "Team Total (Double Faults) Home",
        }
        result = MODULE.normalize_legacy_team_total_row(row)
        self.assertEqual(result["market"], "double_faults")
        self.assertEqual(result["player"], "Gonzalo Bueno")
        self.assertEqual(result["opponent"], "Tiago Pereira")

    def test_plain_match_total_is_unchanged(self) -> None:
        row = {
            "player": "Gonzalo Bueno",
            "opponent": "Tiago Pereira",
            "market": "match_aces",
            "raw_market_name": "Totals (Aces)",
        }
        self.assertEqual(MODULE.normalize_legacy_team_total_row(row), row)


class PlayerOnlyFallbackTests(unittest.TestCase):
    def test_populated_pair_cannot_fallback_by_player_only(self) -> None:
        self.assertFalse(MODULE.can_fallback_player_only("Gonzalo Bueno", "Tiago Pereira"))

    def test_missing_opponent_can_fallback_by_player_only(self) -> None:
        self.assertTrue(MODULE.can_fallback_player_only("Gonzalo Bueno", ""))

    def test_placeholder_player_can_use_named_opponent(self) -> None:
        self.assertTrue(MODULE.can_fallback_player_only("Total", "Gonzalo Bueno"))


class OverOnlyDecisionTests(unittest.TestCase):
    @staticmethod
    def row(value_over_pct: str = "20.0") -> dict[str, str]:
        now = datetime.now(timezone.utc)
        return {
            "date": "2026-07-22",
            "tour": "ATP",
            "tournament": "Kitzbuhel",
            "player": "Player One",
            "opponent": "Player Two",
            "market": "match_aces",
            "scope": "match_total",
            "line": "10.5",
            "over_odds": "2.10",
            "under_odds": "",
            "price_pair_status": "over_only",
            "line_quality": "one_sided",
            "matched_board": "yes",
            "totals_stage0_passed": "true",
            "projection_mean": "12.0",
            "projection_p1": "6.0",
            "projection_p2": "6.0",
            "confidence": "MED",
            "combined_surface_svpt_sample": "2500",
            "capture_ts": now.isoformat(),
            "match_start_utc": (now + timedelta(hours=12)).isoformat(),
            "notes": "",
            "value_over_pct": value_over_pct,
            "value_under_pct": "",
            "edge_over_novig_pct": "",
            "edge_under_novig_pct": "",
            "model_market_gap_pp": "",
        }

    @staticmethod
    def args() -> Namespace:
        return Namespace(
            min_value=0.10,
            min_novig_edge=0.05,
            min_one_sided_value=0.15,
            max_model_market_gap=0.12,
        )

    def test_central_over_only_price_can_pass_on_raw_ev(self) -> None:
        rows = [self.row()]
        MODULE.apply_decision_gates(rows, self.args(), datetime.now(timezone.utc))
        self.assertEqual(rows[0]["best_available_line"], "true")
        self.assertEqual(rows[0]["decision_mode"], "over_only_raw_ev")
        self.assertEqual(rows[0]["bettable"], "true")
        self.assertEqual(rows[0]["recommended_side"], "OVER")

    def test_over_only_price_below_stricter_ev_gate_is_blocked(self) -> None:
        rows = [self.row("12.0")]
        MODULE.apply_decision_gates(rows, self.args(), datetime.now(timezone.utc))
        self.assertEqual(rows[0]["bettable"], "false")
        self.assertIn("EDGE_BELOW_GATE", rows[0]["block_reasons"])


if __name__ == "__main__":
    unittest.main()
