from __future__ import annotations

import csv
import importlib.util
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "oncourt-compute-recent-activity.py"
SPEC = importlib.util.spec_from_file_location("oncourt_compute_recent_activity", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class RecentActivityTests(unittest.TestCase):
    def test_fixture_filter_keeps_supported_unplayed_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            tours = tmp_path / "tours.csv"
            today = tmp_path / "today.csv"
            write_csv(
                tours,
                ["id", "name", "rank"],
                [
                    {"id": 1, "name": "ATP Gstaad", "rank": 2},
                    {"id": 2, "name": "M15 London", "rank": 0},
                    {"id": 3, "name": "Wimbledon", "rank": 4},
                ],
            )
            write_csv(
                today,
                ["tour_id", "player1_id", "player2_id", "result"],
                [
                    {"tour_id": 1, "player1_id": 10, "player2_id": 20, "result": ""},
                    {"tour_id": 1, "player1_id": 30, "player2_id": 40, "result": "6-4 6-4"},
                    {"tour_id": 2, "player1_id": 50, "player2_id": 60, "result": ""},
                    {"tour_id": 3, "player1_id": 70, "player2_id": 80, "result": ""},
                    {"tour_id": 3, "player1_id": 3700, "player2_id": 3700, "result": ""},
                ],
            )
            self.assertEqual(MODULE.load_fixture_player_ids(today, tours), {10, 20, 70, 80})

    def test_activity_windows_fatigue_and_opponent_quality(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            games = Path(tmp) / "games.csv"
            write_csv(
                games,
                ["winner_id", "loser_id", "tour_id", "round_id", "result", "date"],
                [
                    {"winner_id": 10, "loser_id": 20, "tour_id": 1, "round_id": 4, "result": "6-4 6-4", "date": "2026-07-16"},
                    {"winner_id": 30, "loser_id": 10, "tour_id": 2, "round_id": 5, "result": "7-6 6-3", "date": "2026-07-14"},
                    {"winner_id": 10, "loser_id": 40, "tour_id": 3, "round_id": 6, "result": "6-2 6-2", "date": "2026-06-27"},
                    {"winner_id": 10, "loser_id": 50, "tour_id": 4, "round_id": 7, "result": "W/O", "date": "2026-07-17"},
                    {"winner_id": 10, "loser_id": 60, "tour_id": 5, "round_id": 8, "result": "6-0 6-0", "date": "2026-07-18"},
                ],
            )
            activity, max_date = MODULE.aggregate_activity((games,), {10, 20}, date(2026, 7, 17))
            rows = {row["player_id"]: row for row in MODULE.build_rows(activity, {20: 1600.0, 30: 1700.0})}

            self.assertEqual(max_date, date(2026, 7, 16))
            self.assertEqual(rows[10]["matches_last_21d"], 3)
            self.assertEqual(rows[10]["wins_last_21d"], 2)
            self.assertEqual(rows[10]["matches_last_5d"], 2)
            self.assertTrue(rows[10]["played_yesterday"])
            self.assertEqual(rows[10]["last_match_date"], "2026-07-16")
            self.assertEqual(rows[10]["avg_opponent_elo"], 1600.0)
            self.assertEqual(rows[20]["matches_last_21d"], 1)
            self.assertEqual(rows[20]["wins_last_21d"], 0)

    def test_fixture_player_parent_rows_are_targeted_and_typed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            players = Path(tmp) / "players.csv"
            write_csv(
                players,
                ["id", "name", "birthdate", "country", "atp_rank", "hard_points", "clay_points", "grass_points"],
                [
                    {
                        "id": 10,
                        "name": "Existing Player",
                        "birthdate": "1995-01-01",
                        "country": "GBR",
                        "atp_rank": 50,
                        "hard_points": 120,
                        "clay_points": "",
                        "grass_points": 40.5,
                    },
                    {
                        "id": 131263,
                        "name": "New Player",
                        "birthdate": "",
                        "country": "USA",
                        "atp_rank": "",
                        "hard_points": 12.5,
                        "clay_points": 3,
                        "grass_points": "",
                    },
                ],
            )

            rows = MODULE.load_fixture_player_rows(players, {131263})

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["id"], 131263)
            self.assertEqual(rows[0]["name"], "New Player")
            self.assertIsNone(rows[0]["birthdate"])
            self.assertIsNone(rows[0]["atp_rank"])
            self.assertEqual(rows[0]["hard_points"], 12.5)
            self.assertIsNone(rows[0]["grass_points"])


if __name__ == "__main__":
    unittest.main()
