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


if __name__ == "__main__":
    unittest.main()
