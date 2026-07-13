from __future__ import annotations

import importlib.util
import csv
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
MODULE_PATH = SCRIPTS / "build-tennis-props-v3-dataset.py"
SPEC = importlib.util.spec_from_file_location("tennis_props_v3_dataset", MODULE_PATH)
assert SPEC and SPEC.loader
V3 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = V3
SPEC.loader.exec_module(V3)

BASELINE_PATH = SCRIPTS / "tennis-props-baseline.py"
BASELINE_SPEC = importlib.util.spec_from_file_location("tennis_props_baseline_v3", BASELINE_PATH)
assert BASELINE_SPEC and BASELINE_SPEC.loader
BASELINE = importlib.util.module_from_spec(BASELINE_SPEC)
sys.modules[BASELINE_SPEC.name] = BASELINE
BASELINE_SPEC.loader.exec_module(BASELINE)

FIT_PATH = SCRIPTS / "fit-tennis-props-v3.py"
FIT_SPEC = importlib.util.spec_from_file_location("tennis_props_v3_fit", FIT_PATH)
assert FIT_SPEC and FIT_SPEC.loader
FIT = importlib.util.module_from_spec(FIT_SPEC)
sys.modules[FIT_SPEC.name] = FIT
FIT_SPEC.loader.exec_module(FIT)


def match_row(day: str, winner_id: str, loser_id: str, match_num: int) -> dict[str, str]:
    row: dict[str, str] = {
        "_tour": "ATP",
        "_date": day,
        "_surface": "Hard",
        "tourney_id": f"{day}-TEST",
        "tourney_name": "Test Open",
        "tourney_level": "A",
        "round": "R32",
        "best_of": "3",
        "draw_size": "32",
        "match_num": str(match_num),
        "score": "6-4 6-4",
        "winner_id": winner_id,
        "loser_id": loser_id,
        "winner_name": f"Player {winner_id}",
        "loser_name": f"Player {loser_id}",
        "winner_rank": "20",
        "loser_rank": "50",
        "winner_age": "26",
        "loser_age": "27",
        "winner_ht": "190",
        "loser_ht": "184",
        "winner_hand": "R",
        "loser_hand": "R",
    }
    for prefix, aces, dfs in (("w", 8, 2), ("l", 4, 3)):
        row.update({
            f"{prefix}_ace": str(aces),
            f"{prefix}_df": str(dfs),
            f"{prefix}_svpt": "64",
            f"{prefix}_SvGms": "10",
            f"{prefix}_1stIn": "40",
            f"{prefix}_1stWon": "30",
            f"{prefix}_2ndWon": "12",
        })
    return row


class TennisPropsV3DatasetTests(unittest.TestCase):
    def test_same_date_results_do_not_enter_prematch_features(self) -> None:
        rows = [
            match_row("2023-01-01", "1", "2", 1),
            match_row("2023-01-01", "1", "3", 2),
            match_row("2023-01-08", "1", "4", 3),
        ]

        output = V3.build_dataset(rows, output_start_year=2023)
        player_one = [row for row in output if row["player_id"] == "1"]

        same_date = [row for row in player_one if row["date"] == "2023-01-01"]
        next_date = [row for row in player_one if row["date"] == "2023-01-08"]
        self.assertEqual(len(same_date), 2)
        self.assertTrue(all(row["player_l12m_matches"] == 0 for row in same_date))
        self.assertEqual(len(next_date), 1)
        self.assertEqual(next_date[0]["player_l12m_matches"], 2)

    def test_shrink_factor_returns_to_one_without_history(self) -> None:
        self.assertEqual(V3.shrink_factor(1.4, 0), 1.0)
        self.assertAlmostEqual(V3.shrink_factor(1.4, 100), 1.2)

    def test_live_baseline_records_opponent_ace_allowance(self) -> None:
        totals = BASELINE.empty_totals()
        row = match_row("2023-01-01", "1", "2", 1)
        BASELINE.add_side(totals, row, won=True, prefix="w", opp_prefix="l")
        rendered = BASELINE.totals_row(
            tour="atp", player_id="1", player_name="Player 1",
            surface="Hard", window="L12M", totals=totals,
        )
        self.assertEqual(rendered["opponent_aces"], "4")
        self.assertEqual(rendered["opponent_svpt"], "64")
        self.assertAlmostEqual(float(rendered["aces_allowed_rate"]), 4 / 64)

    def test_sellability_gate_requires_real_sample_roi_and_clv(self) -> None:
        fields = ["settlement_status", "event_id", "date", "tour", "player", "opponent", "pnl", "clv_pct"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "signals.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                for index in range(300):
                    writer.writerow({
                        "settlement_status": "settled",
                        "event_id": str(index % 100),
                        "date": "2026-01-01",
                        "tour": "ATP",
                        "player": "A",
                        "opponent": "B",
                        "pnl": "0.1",
                        "clv_pct": "1.2",
                    })
            passed = FIT.sellability_metrics(path)
            self.assertEqual(passed["status"], "PASS")
            self.assertEqual(passed["settled_real_lines"], 300)
            self.assertEqual(passed["distinct_events"], 100)

            path.write_text("settlement_status,event_id,pnl,clv_pct\nsettled,1,-1,-2\n", encoding="utf-8")
            blocked = FIT.sellability_metrics(path)
            self.assertEqual(blocked["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
