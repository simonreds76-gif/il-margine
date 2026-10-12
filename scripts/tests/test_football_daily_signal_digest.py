from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "football-daily-signal-digest.py"
SPEC = importlib.util.spec_from_file_location("football_daily_signal_digest", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def count_row(**updates):
    row = {
        "pick_id": "pick-1",
        "kickoff_utc": "2026-08-27T18:30:00Z",
        "match_id": "fixture-1",
        "match_date": "2026-08-27",
        "match": "Home vs Away",
        "selection": "Home under 13.5",
        "bookmaker": "Bet365",
        "model": "team_shots_v4",
        "model_fair_odds": "1.80",
        "book_odds": "2.00",
        "edge": "0.111",
        "blocked_reason": "matchdays_1_to_3",
    }
    row.update(updates)
    return row


def gk_row(**updates):
    row = {
        "event_id": "event-1",
        "match_date": "2026-08-27",
        "kickoff_at": "2026-08-27T19:00:00Z",
        "home_team": "Home",
        "away_team": "Away",
        "goalkeeper": "Keeper One",
        "line": "3.5",
        "side": "over",
        "odds_decimal": "2.20",
        "fair_odds": "1.90",
        "edge": "0.1579",
        "candidate_status": "eligible_shadow",
        "blockers": "",
    }
    row.update(updates)
    return row


class FootballDailySignalDigestTests(unittest.TestCase):
    def test_count_lane_keeps_one_strongest_candidate_per_fixture(self):
        rows = [count_row(), count_row(pick_id="pick-2", selection="Home under 12.5", edge="0.05")]
        result = MODULE.count_candidates(rows, "2026-08-27", "team_shots_v4")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "pick-1")
        self.assertEqual(result[0]["status"], "WARM-UP TRACK")

    def test_count_lane_excludes_low_edge_and_extra_blockers(self):
        rows = [
            count_row(edge="0.029"),
            count_row(pick_id="blocked", blocked_reason="matchdays_1_to_3;early_neff_below_6"),
        ]
        self.assertEqual(MODULE.count_candidates(rows, "2026-08-27", "team_shots_v4"), [])

    def test_goalkeeper_lane_keeps_eligible_and_positive_value_ladder(self):
        rows = [
            gk_row(),
            gk_row(line="4.5", odds_decimal="4.00", edge="0.08", candidate_status="value_ladder"),
            gk_row(line="5.5", edge="-0.01", candidate_status="no_value"),
        ]
        result = MODULE.goalkeeper_candidates(rows, "2026-08-27")
        self.assertEqual(len(result), 2)
        self.assertEqual({row["status"] for row in result}, {"SHADOW", "VALUE LADDER"})

    def test_sent_candidates_are_not_repeated(self):
        groups = {"TEAM SHOTS V4": [{"id": "sent"}, {"id": "new"}]}
        filtered = MODULE.unseen_candidates(groups, {"sent": {"sent": {}}})
        self.assertEqual([row["id"] for row in filtered["TEAM SHOTS V4"]], ["new"])

    def test_latest_view_retains_original_tracking_terms(self):
        import copy
        original = gk_row(status="pending", odds_decimal="2.75", fair_odds="2.486",
                          edge="0.105983", captured_at="2026-08-26T20:34:12Z")
        before = copy.deepcopy(original)
        latest = gk_row(odds_decimal="2.625", fair_odds="2.549", edge="0.029826",
                        candidate_status="value_ladder", captured_at="2026-08-27T15:00:37Z")
        row = MODULE.goalkeeper_candidates([latest], "2026-08-27", [original])[0]
        message = MODULE.candidate_block(row)
        self.assertIn("TRACKED: LATEST VIEW", message)
        self.assertIn("fair 2.55", message)
        self.assertIn("Original tracking: @2.75 | fair 2.49", message)
        self.assertIn("2026-08-27T15:00:37Z", message)
        self.assertEqual(original, before)

    def test_original_must_match_exact_contract_and_be_unambiguous(self):
        original = gk_row(status="pending", bookmaker="Bet365")
        for change in ({"bookmaker":"Kambi"}, {"line":"4.5"}, {"kickoff_at":"2026-08-28T19:00:00Z"},
                       {"goalkeeper":"Keeper Two"}, {"status":"void"}):
            wrong = {**original, **change}
            row = MODULE.goalkeeper_candidates([gk_row()], "2026-08-27", [wrong])[0]
            self.assertIsNone(row["original"])
        ambiguous = MODULE.goalkeeper_candidates([gk_row()], "2026-08-27", [original, original])[0]
        self.assertIsNone(ambiguous["original"])

    def test_untracked_ladder_is_not_presented_as_new_selection(self):
        row = MODULE.goalkeeper_candidates([gk_row(candidate_status="value_ladder")], "2026-08-27")[0]
        self.assertIn("not a new tracked selection", MODULE.candidate_block(row))

    def test_rendered_messages_respect_telegram_limit(self):
        rows = []
        for index in range(80):
            row = MODULE.goalkeeper_candidates([gk_row(event_id=str(index), goalkeeper=f"Keeper {index}")], "2026-08-27")[0]
            rows.append(row)
        messages = MODULE.render_messages({"GK SAVES V1": rows}, "2026-08-27", include_empty=True)
        self.assertGreater(len(messages), 1)
        self.assertTrue(all(len(message) <= MODULE.TELEGRAM_LIMIT for message, _ in messages))


if __name__ == "__main__":
    unittest.main()
