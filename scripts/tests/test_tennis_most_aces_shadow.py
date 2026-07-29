from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "tennis_most_aces_shadow", ROOT / "scripts" / "tennis-most-aces-shadow.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MostAcesShadowTests(unittest.TestCase):
    def board(self):
        return {
            "date": "2026-07-29", "tour": "ATP", "tournament": "Washington",
            "round": "R16", "surface": "Hard", "player1": "Player One",
            "player2": "Player Two", "player1_mean": "8.0", "player2_mean": "5.0",
            "rho": "0.22", "p_player1": "0.65", "p_draw": "0.10",
            "p_player2": "0.25", "fair_player1": "1.538", "fair_draw": "10.0",
            "fair_player2": "4.0", "player1_confidence": "MED",
            "player2_confidence": "MED", "model": "test",
        }

    def capture(self, timestamp="2026-07-29T08:00:00Z"):
        return {
            "event_id": "123", "date": "2026-07-29", "bookmaker": "BetMGM",
            "player1": "Player One", "player2": "Player Two", "player1_odds": "1.80",
            "draw_odds": "8.00", "player2_odds": "4.50", "capture_ts": timestamp,
            "match_start_utc": "2026-07-29T17:00:00Z",
        }

    def test_registration_devigs_and_selects_best_value(self):
        row = MODULE.registration_row(self.board(), self.capture())
        self.assertIsNotNone(row)
        self.assertEqual(row["recommended_side"], "P1")
        self.assertEqual(row["bet_eligible"], "yes")
        self.assertAlmostEqual(
            float(row["market_p_player1"]) + float(row["market_p_draw"]) + float(row["market_p_player2"]),
            1.0,
            places=5,
        )

    def test_open_capture_is_not_used_as_close(self):
        row = MODULE.registration_row(self.board(), self.capture())
        self.assertIsNotNone(row)
        ledger = [row]
        MODULE.update_closes(ledger, [self.capture()])
        self.assertEqual(ledger[0]["closing_ts_utc"], "")
        self.assertEqual(ledger[0]["clv_pct"], "")

    def test_later_prestart_capture_updates_close(self):
        row = MODULE.registration_row(self.board(), self.capture())
        self.assertIsNotNone(row)
        later = self.capture("2026-07-29T16:00:00Z")
        later["player1_odds"] = "1.70"
        MODULE.update_closes([row], [self.capture(), later])
        self.assertEqual(row["closing_player1_odds"], "1.700")
        self.assertGreater(float(row["clv_pct"]), 0.0)


if __name__ == "__main__":
    unittest.main()
