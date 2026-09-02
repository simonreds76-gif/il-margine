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
            "date": now.date().isoformat(),
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

    def test_one_sided_match_total_remains_fail_closed(self) -> None:
        rows = [self.row()]
        MODULE.apply_decision_gates(rows, self.args(), datetime.now(timezone.utc))
        self.assertEqual(rows[0]["best_available_line"], "true")
        self.assertEqual(rows[0]["decision_mode"], "blocked")
        self.assertEqual(rows[0]["bettable"], "false")
        self.assertIn("LINE_ONE_SIDED", rows[0]["block_reasons"])

    def test_over_only_price_below_stricter_ev_gate_is_blocked(self) -> None:
        rows = [self.row("12.0")]
        MODULE.apply_decision_gates(rows, self.args(), datetime.now(timezone.utc))
        self.assertEqual(rows[0]["bettable"], "false")
        self.assertIn("EDGE_BELOW_GATE", rows[0]["block_reasons"])

    def test_complete_two_way_player_line_enters_shadow_only(self) -> None:
        now = datetime.now(timezone.utc)
        row = {
            "market": "aces",
            "scope": "player",
            "price_pair_status": "two_way",
            "line_quality": "complete",
            "matched_board": "yes",
            "confidence": "MED",
            "combined_surface_svpt_sample": "1800",
            "capture_ts": now.isoformat(),
            "match_start_utc": (now + timedelta(hours=5)).isoformat(),
            "over_odds": "2.10",
            "under_odds": "1.70",
            "value_over_pct": "20.0",
            "value_under_pct": "-10.0",
            "edge_over_novig_pct": "12.0",
            "edge_under_novig_pct": "-8.0",
            "model_market_gap_pp": "5.0",
            "notes": "EVENT_ENV_N63",
        }
        MODULE.apply_decision_gates([row], self.args(), now)
        self.assertEqual(row["trackable_shadow"], "true")
        self.assertEqual(row["shadow_side"], "OVER")
        self.assertEqual(row["decision_mode"], "two_way_player_shadow")
        self.assertEqual(row["bettable"], "false")

    def test_two_way_player_shadow_rejects_unresolved_opponent(self) -> None:
        now = datetime.now(timezone.utc)
        row = {
            "market": "double_faults",
            "scope": "player",
            "price_pair_status": "two_way",
            "line_quality": "complete",
            "matched_board": "yes",
            "confidence": "MED",
            "combined_surface_svpt_sample": "1800",
            "capture_ts": now.isoformat(),
            "match_start_utc": (now + timedelta(hours=5)).isoformat(),
            "over_odds": "2.10",
            "under_odds": "1.70",
            "value_over_pct": "20.0",
            "value_under_pct": "-10.0",
            "edge_over_novig_pct": "12.0",
            "edge_under_novig_pct": "-8.0",
            "model_market_gap_pp": "5.0",
            "notes": "OPPONENT_NAME_UNRESOLVED",
        }
        MODULE.apply_decision_gates([row], self.args(), now)
        self.assertEqual(row["trackable_shadow"], "false")
        self.assertIn("NAME_OR_DATA_WARNING", row["shadow_block_reasons"])


class BreakMarketTests(unittest.TestCase):
    @staticmethod
    def priced_row(bookmaker: str = "Bet365") -> dict[str, str]:
        now = datetime.now(timezone.utc)
        return {
            "date": now.date().isoformat(),
            "tour": "ATP",
            "tournament": "US Open",
            "event_id": "event-1",
            "market": "match_breaks",
            "scope": "match_total",
            "player": "Player One",
            "opponent": "Player Two",
            "line": "6.5",
            "breaks_stage0_passed": "true",
            "matched_board": "yes",
            "confidence": "HIGH",
            "combined_surface_svpt_sample": "2400",
            "capture_ts": now.isoformat(),
            "match_start_utc": (now + timedelta(hours=5)).isoformat(),
            "over_odds": "1.90",
            "under_odds": "1.90",
            "price_pair_status": "two_way",
            "line_quality": "complete",
            "main_line": "true",
            "model_market_gap_pp": "6.0",
            "value_over_pct": "7.0",
            "value_under_pct": "-7.0",
            "notes": "",
            "bookmaker": bookmaker,
        }

    def test_break_means_use_player_break_projection(self) -> None:
        board = {"projected_breaks_for": "3.125", "projected_total_breaks": "7.0"}
        self.assertEqual(MODULE.market_mean(board, "player_breaks"), 3.125)
        self.assertEqual(MODULE.market_mean(board, "match_breaks"), 3.125)

    def test_break_gate_selects_registered_distribution(self) -> None:
        gate = {
            "scopes": {
                "match_breaks": {
                    "passed": True,
                    "tours": {"ATP": {"passed": True, "distribution": "negative_binomial", "model_alpha": 0.02}},
                }
            }
        }
        self.assertEqual(
            MODULE.break_gate_result(gate, "ATP", "match_breaks"),
            (True, "negative_binomial", 0.02),
        )

    def test_single_source_bet365_break_price_enters_separate_prospective_shadow(self) -> None:
        row = self.priced_row()
        MODULE.apply_break_shadow_gates([row], datetime.now(timezone.utc))
        self.assertEqual(row["decision_mode"], "breaks_single_source_shadow")
        self.assertEqual(row["shadow_side"], "OVER")
        self.assertEqual(row["trackable_shadow"], "true")
        self.assertEqual(row["calibration_eligible"], "true")
        self.assertEqual(row["shadow_block_reasons"], "")
        self.assertEqual(row["bettable"], "false")

    def test_unsupported_single_source_remains_calibration_only(self) -> None:
        row = self.priced_row("Other Book")
        MODULE.apply_break_shadow_gates([row], datetime.now(timezone.utc))
        self.assertEqual(row["decision_mode"], "breaks_calibration_unfiltered")
        self.assertEqual(row["trackable_shadow"], "false")
        self.assertIn("PRICE_SOURCE_UNVERIFIED", row["shadow_block_reasons"])

    def test_two_agreeing_sources_can_enter_strict_prospective_shadow(self) -> None:
        rows = [self.priced_row("Bet365"), self.priced_row("BetsBK")]
        MODULE.apply_break_shadow_gates(rows, datetime.now(timezone.utc))
        self.assertTrue(all(row["source_agreement"] == "true" for row in rows))
        self.assertTrue(all(row["decision_mode"] == "breaks_prospective_shadow" for row in rows))
        self.assertTrue(all(row["trackable_shadow"] == "true" for row in rows))
        self.assertTrue(all(row["shadow_side"] == "OVER" for row in rows))

    def test_stale_second_source_does_not_verify_a_price(self) -> None:
        now = datetime.now(timezone.utc)
        rows = [self.priced_row("Bet365"), self.priced_row("BetsBK")]
        rows[1]["capture_ts"] = (now - timedelta(hours=2)).isoformat()
        MODULE.apply_break_shadow_gates(rows, now)
        self.assertTrue(all(row["source_agreement"] == "false" for row in rows))
        self.assertEqual(rows[0]["decision_mode"], "breaks_single_source_shadow")
        self.assertEqual(rows[1]["decision_mode"], "breaks_calibration_unfiltered")

    def test_model_market_gap_and_deep_alternate_fail_strict_gate(self) -> None:
        rows = [self.priced_row("Bet365"), self.priced_row("BetsBK")]
        for row in rows:
            row["model_market_gap_pp"] = "18.0"
            row["line_quality"] = "deep_alt"
            row["main_line"] = "false"
        MODULE.apply_break_shadow_gates(rows, datetime.now(timezone.utc))
        self.assertTrue(all(row["decision_mode"] == "breaks_calibration_unfiltered" for row in rows))
        self.assertTrue(all("MODEL_MARKET_GAP" in row["shadow_block_reasons"] for row in rows))
        self.assertTrue(all("LINE_NOT_COMPLETE" in row["shadow_block_reasons"] for row in rows))

    def test_unmatched_break_line_still_preserves_raw_count_calibration(self) -> None:
        row = self.priced_row()
        row["matched_board"] = "no"
        row["breaks_stage0_passed"] = "false"
        MODULE.apply_break_shadow_gates([row], datetime.now(timezone.utc))
        self.assertEqual(row["decision_mode"], "breaks_calibration_unfiltered")
        self.assertEqual(row["calibration_eligible"], "true")
        self.assertIn("NO_BOARD_MATCH", row["shadow_block_reasons"])


if __name__ == "__main__":
    unittest.main()
