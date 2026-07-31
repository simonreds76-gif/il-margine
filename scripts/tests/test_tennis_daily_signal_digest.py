from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "tennis-daily-signal-digest.py"
SPEC = importlib.util.spec_from_file_location("tennis_daily_signal_digest", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TennisDailySignalDigestTests(unittest.TestCase):
    def test_ml_signal_formats_price_fair_edge_and_stake(self) -> None:
        lane = MODULE.Lane("VOL200", Path("unused.csv"), "TRACKED EXPANSION", 10)
        signal = MODULE.row_to_signal(
            {
                "date": "2026-07-16",
                "player1": "Player One",
                "player2": "Player Two",
                "side": "P2",
                "bet_type": "match",
                "pin_odds2": "3.18",
                "our_odds2": "2.8058",
                "value_pct": "13.34",
                "stake_units": "1.0",
                "settlement_status": "pending",
            },
            lane,
            "2026-07-16",
        )
        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertEqual(signal.match, "Player One vs Player Two")
        self.assertIn("Player Two ML @ 3.18", signal.selection)
        self.assertIn("fair 2.806", signal.selection)
        self.assertIn("edge +13.3%", signal.selection)
        self.assertTrue(signal.selection.endswith("1u"))

    def test_spread_signal_uses_selected_player_and_handicap(self) -> None:
        lane = MODULE.Lane("CLAY BO3", Path("unused.csv"), "SHADOW / RESEARCH", 30)
        signal = MODULE.row_to_signal(
            {
                "date": "2026-07-16",
                "player1": "Player One",
                "player2": "Player Two",
                "side": "P2-",
                "bet_type": "spread",
                "spread_line": "-4",
                "spread_odds": "1.855",
                "value_pct": "9.67",
                "stake_units": "2",
                "settlement_status": "pending",
            },
            lane,
            "2026-07-16",
        )
        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertIn("Player Two -4 games @ 1.855", signal.selection)

    def test_registered_gap_candidate_is_provisional_half_unit(self) -> None:
        signal = MODULE.gap_replacement_signal(
            {
                "date": "2026-07-16",
                "player1": "Player One",
                "player2": "Player Two",
                "selected_player": "Player One",
                "selected_side": "P1",
                "bet_type": "match",
                "selected_odds": "2.75",
                "fair_odds1": "2.10",
                "value_pct": "30.95",
                "model_market_gap_pp": "12.4",
                "diagnostic_quality": "LOW",
                "replacement_cohorts": "volume200_gap_10_15_same_side",
                "replacement_forward_eligible": "1",
                "settlement_status": "pending",
            },
            "2026-07-16",
        )
        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertEqual(signal.section, "PROVISIONAL ML EXPANSION")
        self.assertEqual(signal.labels, ["VOL200 GAP"])
        self.assertIn("gap 12.4pp", signal.selection)
        self.assertIn("quality LOW", signal.selection)
        self.assertTrue(signal.selection.endswith("0.5u"))

    def test_over_only_trackable_prop_is_rendered_as_shadow_watchlist(self) -> None:
        original_read_csv = MODULE.read_csv
        MODULE.read_csv = lambda _path: [
            {
                "date": "2026-07-29",
                "player": "Aleksandar Vukic",
                "opponent": "Lorenzo Musetti",
                "market": "aces",
                "line": "9.5",
                "over_odds": "3.40",
                "fair_over_odds": "2.515",
                "value_over_pct": "35.17",
                "trackable_shadow": "true",
                "shadow_side": "OVER",
                "bettable": "false",
                "recommended_side": "",
                "match_start_utc": "2026-07-29T17:00:00Z",
            }
        ]
        try:
            signals = MODULE.props_signals("2026-07-29")
        finally:
            MODULE.read_csv = original_read_csv

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].section, "BET365 PROPS WATCHLIST")
        self.assertEqual(signals[0].labels, ["ACES/DF WATCH"])
        self.assertIn("Vukic aces Over 9.5 @ 3.4", signals[0].selection)
        self.assertIn("fair 2.515", signals[0].selection)
        self.assertTrue(signals[0].selection.endswith("shadow evidence only"))

    def test_props_watchlist_excludes_other_event_dates(self) -> None:
        original_read_csv = MODULE.read_csv
        MODULE.read_csv = lambda _path: [
            {
                "date": "2026-07-30",
                "player": "Alejandro Tabilo",
                "opponent": "Terence Atmane",
                "market": "aces",
                "line": "9.5",
                "over_odds": "3.50",
                "trackable_shadow": "true",
                "shadow_side": "OVER",
            }
        ]
        try:
            signals = MODULE.props_signals("2026-07-29")
        finally:
            MODULE.read_csv = original_read_csv

        self.assertEqual(signals, [])

    def test_render_stays_within_telegram_limit(self) -> None:
        signals = [
            MODULE.Signal(
                section="SHADOW / RESEARCH",
                priority=20,
                labels=["TEST"],
                match=f"Player {index} vs Opponent {index}",
                selection="Player selection @ 2.0 | edge +10.0% | 1u " + ("x" * 200),
                edge_pct=10.0,
            )
            for index in range(50)
        ]
        messages = MODULE.render_messages("2026-07-16", signals, [])
        self.assertGreater(len(messages), 1)
        self.assertTrue(all(len(message) <= MODULE.TELEGRAM_LIMIT for message in messages))

    def test_same_digest_state_can_be_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"
            path.write_text('{"date":"2026-07-16","digest_hash":"abc"}', encoding="utf-8")
            self.assertEqual(MODULE.load_state(path)["digest_hash"], "abc")

    def test_ready_state_requires_matching_date_and_ok_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ready.json"
            path.write_text('{"date":"2026-07-16","status":"ok"}', encoding="utf-8")
            self.assertTrue(MODULE.signal_generation_is_ready(path, "2026-07-16"))
            self.assertFalse(MODULE.signal_generation_is_ready(path, "2026-07-17"))
            path.write_text('{"date":"2026-07-16","status":"failed"}', encoding="utf-8")
            self.assertFalse(MODULE.signal_generation_is_ready(path, "2026-07-16"))

    def test_digest_dispatch_defaults_to_golden(self) -> None:
        self.assertEqual(MODULE.DEFAULT_REF, "golden-with-speed-insights")


if __name__ == "__main__":
    unittest.main()
