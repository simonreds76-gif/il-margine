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


if __name__ == "__main__":
    unittest.main()
