from __future__ import annotations

import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SCRIPTS_DIR / "tennis-props-scrape-betsbk.py"
SPEC = importlib.util.spec_from_file_location("tennis_props_scrape_betsbk", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BetsBkParserTests(unittest.TestCase):
    def test_parses_public_price_buttons(self) -> None:
        self.assertEqual(
            MODULE.parse_price_buttons(["OVER 3.5\n2.12", "UNDER 3.5\n1.61"]),
            ("3.5", "2.12", "1.61"),
        )

    def test_rejects_one_sided_or_mismatched_line(self) -> None:
        self.assertIsNone(MODULE.parse_price_buttons(["OVER 3.5\n2.12"]))
        self.assertIsNone(
            MODULE.parse_price_buttons(["OVER 3.5\n2.12", "UNDER 4.5\n1.61"])
        )

    def test_classifies_player_and_match_service_break_markets(self) -> None:
        self.assertEqual(
            MODULE.market_heading("Player One Service Breaks", "Player One", "Player Two"),
            ("player_breaks", "Player One", "Player Two"),
        )
        self.assertEqual(
            MODULE.market_heading("Total Breaks of Serve in Match", "Player One", "Player Two"),
            ("match_breaks", "Player One", "Player Two"),
        )

    def test_does_not_confuse_tiebreaks_or_break_points_with_service_breaks(self) -> None:
        self.assertIsNone(MODULE.market_heading("Tie Break in Match", "Player One", "Player Two"))
        self.assertIsNone(MODULE.market_heading("Player One Break Points Won", "Player One", "Player Two"))
        self.assertIsNone(MODULE.market_heading("Player One Aces in Set 1", "Player One", "Player Two"))

    def test_merge_replaces_refreshed_event_and_preserves_other_event(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "lines.csv"
            existing = [
                self.row(event_id="sbk-1", bookmaker="BetsBK", over_odds="1.80"),
                self.row(event_id="sbk-2", bookmaker="BetsBK", over_odds="1.75"),
            ]
            MODULE.write_rows(path, existing, MODULE.OUTPUT_FIELDS)
            fresh = [self.row(event_id="sbk-1", bookmaker="BetsBK", over_odds="2.05")]
            MODULE.merge_snapshot(path, fresh)
            with path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual(next(row for row in rows if row["event_id"] == "sbk-1")["over_odds"], "2.05")
            self.assertTrue(any(row["event_id"] == "sbk-2" for row in rows))

    @staticmethod
    def row(*, event_id: str, bookmaker: str, over_odds: str) -> dict[str, str]:
        row = {field: "" for field in MODULE.OUTPUT_FIELDS}
        row.update(
            {
                "event_id": event_id,
                "date": "2026-08-26",
                "tour": "ATP",
                "tournament": "US Open",
                "bookmaker": bookmaker,
                "player": "Player One",
                "opponent": "Player Two",
                "market": "aces",
                "line": "3.5",
                "over_odds": over_odds,
                "under_odds": "1.80",
                "capture_ts": "2026-08-26T12:00:00Z",
                "match_start_utc": "2026-08-26T15:00:00Z",
            }
        )
        return row


if __name__ == "__main__":
    unittest.main()
