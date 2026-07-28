from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import UTC, date, datetime
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]


def load_script():
    spec = importlib.util.spec_from_file_location(
        "score_tennis_spread_history",
        SCRIPTS / "score-tennis-spread-history.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SCORER = load_script()


class ScoreTennisSpreadHistoryTests(unittest.TestCase):
    def snapshot(self, **changes):
        base = {
            "lane": "ATP",
            "league_name": "ATP Test",
            "player1_name": "Player One",
            "player2_name": "Player Two",
            "player1_id": 10,
            "player2_id": 20,
            "captured_at": datetime(2026, 7, 20, 8, tzinfo=UTC),
            "capture_date": date(2026, 7, 20),
            "capture_mode": "daily",
            "match_date": date(2026, 7, 20),
            "kickoff": datetime(2026, 7, 20, 12, tzinfo=UTC),
            "ml_odds1": 1.8,
            "ml_odds2": 2.1,
            "spread_line": -2.0,
            "spread_odds1": 1.95,
            "spread_odds2": 1.9,
            "source_file": "history.csv",
            "resolve_method1": "full_exact",
            "resolve_method2": "full_exact",
        }
        base.update(changes)
        return SCORER.Snapshot(**base)

    def game(self, **changes):
        base = {
            "winner_id": 10,
            "loser_id": 20,
            "tour_id": 100,
            "round_id": 4,
            "result": "6-4 6-4",
            "match_date": date(2026, 7, 20),
        }
        base.update(changes)
        return SCORER.Game(**base)

    def test_full_name_resolver_rejects_collisions_and_surname_fallback(self):
        resolver = SCORER.FullNameResolver(
            [
                {"id": "1", "name": "Francisco Cerundolo"},
                {"id": "2", "name": "Juan Manuel Cerundolo"},
                {"id": "3", "name": "Yunchaokete Bu"},
            ]
        )
        self.assertIsNone(resolver.resolve("Cerundolo").player_id)
        self.assertEqual(
            resolver.resolve("Bu Yunchaokete").player_id,
            3,
        )

    def test_reversed_capture_orientation_flips_line_and_prices(self):
        reversed_snapshot = self.snapshot(
            player1_name="Player Two",
            player2_name="Player One",
            player1_id=20,
            player2_id=10,
            spread_line=2.5,
            spread_odds1=1.88,
            spread_odds2=2.02,
            ml_odds1=2.4,
            ml_odds2=1.6,
        )
        oriented = SCORER.orient_snapshot(reversed_snapshot, 10)
        self.assertEqual(oriented.line_p1, -2.5)
        self.assertEqual(oriented.spread_odds1, 2.02)
        self.assertEqual(oriented.ml_odds1, 1.6)

    def test_integer_push_is_not_graded_as_a_loss(self):
        self.assertEqual(SCORER.grade_spread(2, -2), "PUSH")
        self.assertEqual(SCORER.opposite_result("PUSH"), "PUSH")
        self.assertEqual(SCORER.flat_pnl("PUSH", 1.95), 0.0)

    def test_retirement_is_not_scored(self):
        self.assertIsNone(SCORER.score_margin("6-4 2-1 RET"))
        self.assertEqual(SCORER.score_margin("7-6(5) 6-4"), (13, 10, 3))

    def test_exact_date_wins_over_capture_window_candidate(self):
        snapshot = self.snapshot()
        exact = self.game()
        later = self.game(
            tour_id=101,
            match_date=date(2026, 7, 22),
        )
        game, method, reason = SCORER.resolve_snapshot_game(
            snapshot,
            {snapshot.pair: [exact, later]},
            {},
            4,
        )
        self.assertEqual(game, exact)
        self.assertEqual(method, "pair_exact_match_date")
        self.assertEqual(reason, "")

    def test_ambiguous_window_without_tour_overlap_is_rejected(self):
        snapshot = self.snapshot(
            league_name="ATP Unknown",
            match_date=None,
        )
        first = self.game()
        second = self.game(
            tour_id=101,
            match_date=date(2026, 7, 21),
        )
        game, _, reason = SCORER.resolve_snapshot_game(
            snapshot,
            {snapshot.pair: [first, second]},
            {
                100: SCORER.Tour(100, "Alpha", 2),
                101: SCORER.Tour(101, "Beta", 2),
            },
            4,
        )
        self.assertIsNone(game)
        self.assertEqual(reason, "ambiguous_capture_window")

    def test_score_match_uses_close_mode_on_same_line(self):
        publication = self.snapshot(spread_line=-4.0)
        later_daily = self.snapshot(
            captured_at=datetime(2026, 7, 20, 10, tzinfo=UTC),
            spread_line=-4.0,
            spread_odds1=1.9,
            spread_odds2=1.95,
        )
        close = self.snapshot(
            captured_at=datetime(2026, 7, 20, 9, tzinfo=UTC),
            capture_mode="close",
            spread_line=-4.0,
            spread_odds1=1.85,
            spread_odds2=2.0,
        )
        row, reason = SCORER.score_match(
            "ATP",
            self.game(),
            [
                (publication, "pair_exact_match_date"),
                (later_daily, "pair_exact_match_date"),
                (close, "pair_exact_match_date"),
            ],
            {100: SCORER.Tour(100, "ATP Test", 2)},
        )
        self.assertEqual(reason, "")
        self.assertEqual(row["close_capture_mode"], "close")
        self.assertEqual(row["close_odds1"], 1.85)
        self.assertEqual(row["p1_cover_result"], "PUSH")
        self.assertEqual(row["p2_cover_result"], "PUSH")
        self.assertEqual(row["p1_cover_binary"], "")

    def test_score_history_outputs_one_row_per_match(self):
        snapshot1 = self.snapshot()
        snapshot2 = self.snapshot(
            captured_at=datetime(2026, 7, 20, 9, tzinfo=UTC),
        )
        game = self.game(result="6-3 6-4")
        diagnostics = SCORER.Diagnostics()
        scored = SCORER.score_history(
            [snapshot1, snapshot2],
            {snapshot1.pair: [game]},
            {100: SCORER.Tour(100, "ATP Test", 2)},
            4,
            diagnostics,
        )
        self.assertEqual(len(scored["ATP"]), 1)
        self.assertEqual(scored["ATP"][0]["snapshot_count"], 2)


if __name__ == "__main__":
    unittest.main()
