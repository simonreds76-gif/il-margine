from __future__ import annotations

import csv
import runpy
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SETTLE = runpy.run_path(
    str(ROOT / "scripts" / "tennis-props-settle-shadow.py"),
    run_name="tennis_props_settle_shadow_test",
)


class TennisPropsSettlementTests(unittest.TestCase):
    @staticmethod
    def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fields = sorted({key for row in rows for key in row})
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_same_day_replacement_match_voids_original_market(self) -> None:
        signal = {
            "date": "2026-08-31",
            "tour": "ATP",
            "tournament": "US Open",
            "player": "Andrey Rublev",
            "opponent": "Marin Cilic",
        }
        with tempfile.TemporaryDirectory() as tmp:
            oncourt = Path(tmp)
            self.write_csv(
                oncourt / "players_atp.csv",
                [
                    {"id": "1", "name": "Andrey Rublev"},
                    {"id": "2", "name": "Otto Virtanen"},
                ],
            )
            self.write_csv(oncourt / "tours_atp.csv", [{"id": "99", "name": "U.S. Open - New York"}])
            self.write_csv(
                oncourt / "games_atp.csv",
                [
                    {
                        "date": "2026-08-31",
                        "winner_id": "1",
                        "loser_id": "2",
                        "tour_id": "99",
                        "result": "6-4 6-4 6-3",
                    }
                ],
            )

            index = SETTLE["load_oncourt_index"](oncourt, [signal])
            key = ("ATP", 2026, SETTLE["participant_key"]("Andrey Rublev"))
            replacement = SETTLE["find_replacement_candidate"](signal, index[key])

        self.assertIsNotNone(replacement)
        self.assertEqual(replacement["loser_name"], "Otto Virtanen")

    def test_replacement_requires_same_date_and_tournament(self) -> None:
        signal = {
            "date": "2026-08-31",
            "tournament": "US Open",
            "player": "Andrey Rublev",
            "opponent": "Marin Cilic",
        }
        candidates = [
            {
                "winner_name": "Andrey Rublev",
                "loser_name": "Otto Virtanen",
                "tourney_name": "Cincinnati",
                "tourney_date": "20260831",
            }
        ]
        self.assertIsNone(SETTLE["find_replacement_candidate"](signal, candidates))

    def test_exact_pair_never_uses_a_different_tournament_fallback(self) -> None:
        signal = {
            "date": "2026-09-01",
            "tournament": "US Open",
            "player": "Fabian Marozsan",
            "opponent": "Michael Zheng",
        }
        candidates = [
            {
                "winner_name": "Fabian Marozsan",
                "loser_name": "Michael Zheng",
                "tourney_name": "Cincinnati Open - Cincinnati",
                "tourney_date": "20260812",
            }
        ]
        self.assertIsNone(SETTLE["choose_candidate"](signal, candidates))

    @staticmethod
    def price_signal() -> dict[str, str]:
        return {
            "date": "2026-09-02",
            "tour": "ATP",
            "tournament": "US Open",
            "player": "Player One",
            "opponent": "Player Two",
            "event_id": "event-1",
            "bookmaker": "Bet365",
            "market": "match_breaks",
            "line": "6.5",
            "side": "OVER",
            "selected_odds": "1.90",
            "capture_ts": "2026-09-02T10:00:00Z",
            "logged_at_utc": "2026-09-02T10:01:00Z",
            "match_start_utc": "2026-09-02T15:00:00Z",
            "decision_mode": "breaks_prospective_shadow",
        }

    def test_single_snapshot_does_not_manufacture_clv(self) -> None:
        signal = self.price_signal()
        history = [{
            **signal,
            "capture_ts": "2026-09-02T10:00:00Z",
            "over_odds": "1.90",
            "under_odds": "1.90",
        }]
        event = {SETTLE["history_key"](signal): history}
        pair = {SETTLE["history_key"](signal, fallback=True): history}
        self.assertFalse(SETTLE["enrich_closing_price"](signal, event, pair))
        self.assertEqual(signal["closing_snapshot_count"], "")
        self.assertEqual(signal["clv_pct"], "")

    def test_two_snapshots_with_a_post_entry_price_produce_clv(self) -> None:
        signal = self.price_signal()
        history = [
            {**signal, "capture_ts": "2026-09-02T10:00:00Z", "over_odds": "1.90", "under_odds": "1.90"},
            {**signal, "capture_ts": "2026-09-02T14:00:00Z", "over_odds": "1.80", "under_odds": "2.00"},
        ]
        event = {SETTLE["history_key"](signal): history}
        pair = {SETTLE["history_key"](signal, fallback=True): history}
        self.assertTrue(SETTLE["enrich_closing_price"](signal, event, pair))
        self.assertEqual(signal["closing_snapshot_count"], "2")
        self.assertAlmostEqual(float(signal["clv_pct"]), (1.90 / 1.80 - 1.0) * 100.0, places=3)
        self.assertIn("min2_postentry", signal["clv_method"])

    def test_player_break_clv_keys_do_not_collide_at_the_same_line(self) -> None:
        first = self.price_signal()
        first["market"] = "player_breaks"
        second = {**first, "player": "Player Two", "opponent": "Player One"}
        self.assertNotEqual(SETTLE["history_key"](first), SETTLE["history_key"](second))
        first["market"] = "match_breaks"
        second["market"] = "match_breaks"
        self.assertEqual(SETTLE["history_key"](first), SETTLE["history_key"](second))

    def test_calibration_rows_never_receive_clv(self) -> None:
        signal = self.price_signal()
        signal["decision_mode"] = "breaks_calibration_unfiltered"
        history = [
            {**signal, "capture_ts": "2026-09-02T10:00:00Z", "over_odds": "1.90", "under_odds": "1.90"},
            {**signal, "capture_ts": "2026-09-02T14:00:00Z", "over_odds": "1.80", "under_odds": "2.00"},
        ]
        event = {SETTLE["history_key"](signal): history}
        self.assertFalse(SETTLE["enrich_closing_price"](signal, event, {}))
        self.assertEqual(signal["clv_pct"], "")

    def test_break_count_falls_back_to_sackmann_when_oncourt_has_no_bp_fields(self) -> None:
        signal = {
            "date": "2026-09-02",
            "tournament": "US Open",
            "player": "Player One",
            "opponent": "Player Two",
            "market": "match_breaks",
        }
        common = {
            "winner_name": "Player One",
            "loser_name": "Player Two",
            "tourney_name": "US Open",
            "tourney_date": "20260902",
            "score": "6-4 6-4",
        }
        oncourt = [{**common, "_settlement_source": "oncourt"}]
        sackmann = [{
            **common,
            "_settlement_source": "sackmann",
            "w_bpFaced": "5",
            "w_bpSaved": "3",
            "l_bpFaced": "7",
            "l_bpSaved": "4",
        }]
        candidate, actual, note = SETTLE["resolve_count_candidate"](signal, oncourt, sackmann)
        self.assertEqual(candidate["_settlement_source"], "sackmann")
        self.assertEqual(actual, 5)
        self.assertEqual(note, "ok")

    def test_oncourt_break_fields_use_export_column_names(self) -> None:
        signal = {
            "date": "2026-09-02",
            "tour": "ATP",
            "tournament": "US Open",
            "player": "Player One",
            "opponent": "Player Two",
            "market": "player_breaks",
        }
        with tempfile.TemporaryDirectory() as tmp:
            oncourt = Path(tmp)
            self.write_csv(
                oncourt / "players_atp.csv",
                [{"id": "1", "name": "Player One"}, {"id": "2", "name": "Player Two"}],
            )
            self.write_csv(oncourt / "tours_atp.csv", [{"id": "99", "name": "US Open"}])
            self.write_csv(
                oncourt / "games_atp.csv",
                [{
                    "date": "2026-09-02",
                    "winner_id": "1",
                    "loser_id": "2",
                    "tour_id": "99",
                    "result": "6-4 6-4",
                }],
            )
            self.write_csv(
                oncourt / "stat_atp.csv",
                [{
                    "winner_id": "1",
                    "loser_id": "2",
                    "tour_id": "99",
                    "w_bpsaved": "2",
                    "w_bpfaced": "5",
                    "l_bpsaved": "4",
                    "l_bpfaced": "6",
                }],
            )

            index = SETTLE["load_oncourt_index"](oncourt, [signal])

        key = ("ATP", 2026, SETTLE["pair_key"]("Player One", "Player Two"))
        result = index[key][0]
        self.assertEqual(result["w_bpSaved"], "2")
        self.assertEqual(result["w_bpFaced"], "5")
        self.assertEqual(result["l_bpSaved"], "4")
        self.assertEqual(result["l_bpFaced"], "6")
        self.assertEqual(SETTLE["market_count"](result, "player one", "player_breaks"), (2, "ok"))
        self.assertEqual(SETTLE["market_count"](result, "player one", "match_breaks"), (5, "ok"))

    def test_settlement_schema_preserves_decision_labels(self) -> None:
        for field in ("decision_mode", "cohort", "gate_version", "price_pair_status", "source_agreement"):
            self.assertIn(field, SETTLE["FIELDNAMES"])


if __name__ == "__main__":
    unittest.main()
