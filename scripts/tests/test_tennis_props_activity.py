from __future__ import annotations

import csv
import importlib.util
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
PATH = SCRIPTS / "tennis-props-activity.py"
SPEC = importlib.util.spec_from_file_location("tennis_props_activity_test", PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


FIELDS = [
    "tourney_id", "tourney_date", "match_num",
    "winner_id", "winner_name", "loser_id", "loser_name",
    "w_svpt", "l_svpt",
]


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


class TennisPropsActivityTests(unittest.TestCase):
    def test_counts_main_and_lower_activity_without_duplicate_match(self) -> None:
        main = {
            "tourney_id": "main-1", "tourney_date": "20260701", "match_num": "1",
            "winner_id": "1", "winner_name": "Player One",
            "loser_id": "2", "loser_name": "Player Two",
            "w_svpt": "70", "l_svpt": "65",
        }
        lower = {
            "tourney_id": "chall-1", "tourney_date": "20260601", "match_num": "2",
            "winner_id": "1", "winner_name": "Player One",
            "loser_id": "3", "loser_name": "Player Three",
            "w_svpt": "80", "l_svpt": "60",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_rows(root / "atp_matches_2026.csv", [main])
            write_rows(root / "atp_matches_qual_chall_2026.csv", [main, lower])
            rows = MODULE.build_rows(
                root,
                as_of=date(2026, 7, 30),
                start_year=2026,
                end_year=2026,
            )
        player = next(
            row for row in rows
            if row["player_name"] == "Player One" and row["window"] == "L12M"
        )
        self.assertEqual(player["matches"], "2")
        self.assertEqual(player["svpt"], "150")
        self.assertEqual(player["main_matches"], "1")
        self.assertEqual(player["qual_chall_matches"], "1")


if __name__ == "__main__":
    unittest.main()
