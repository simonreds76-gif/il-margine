from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "tennis_most_aces_capture", ROOT / "scripts" / "tennis-most-aces-capture.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MostAcesCaptureTests(unittest.TestCase):
    def test_three_separate_outcomes(self) -> None:
        market = {
            "name": "Player To Serve Most Aces",
            "odds": [
                {"label": "Alex de Minaur", "odds": 3.2},
                {"label": "Draw", "odds": 8.0},
                {"label": "Stefanos Tsitsipas", "odds": 1.55},
            ],
        }
        self.assertTrue(MODULE.is_most_aces_market(market["name"]))
        self.assertEqual(
            MODULE.extract_market_prices(market, "Alex de Minaur", "Stefanos Tsitsipas"),
            (3.2, 8.0, 1.55),
        )

    def test_combined_home_draw_away_shape(self) -> None:
        market = {
            "name": "Most Aces",
            "outcomes": [{"home": 1.8, "draw": 7.5, "away": 2.4}],
        }
        self.assertEqual(
            MODULE.extract_market_prices(market, "Player One", "Player Two"),
            (1.8, 7.5, 2.4),
        )

    def test_incomplete_market_is_rejected(self) -> None:
        market = {
            "name": "Most Aces",
            "odds": [
                {"label": "Player One", "odds": 1.8},
                {"label": "Player Two", "odds": 2.4},
            ],
        }
        self.assertIsNone(MODULE.extract_market_prices(market, "Player One", "Player Two"))

    def test_market_audit_keeps_unrecognized_names(self) -> None:
        class Common:
            @staticmethod
            def clean_player(value):
                return str(value)

            @staticmethod
            def tour_from_event(_event):
                return "ATP"

            @staticmethod
            def tournament_from_event(_event):
                return "Washington"

        rows = MODULE.extract_audit_rows(
            [{
                "id": "event-1",
                "date": "2026-07-29T18:00:00Z",
                "home": "Player One",
                "away": "Player Two",
                "bookmakers": {
                    "BetMGM": [{
                        "name": "Ace Match Winner",
                        "odds": [{"label": "Player One", "odds": 1.8}],
                    }],
                },
            }],
            "2026-07-29T10:00:00Z",
            Common(),
            source_endpoint="odds/multi",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_endpoint"], "odds/multi")
        self.assertEqual(rows[0]["market_name"], "Ace Match Winner")
        self.assertEqual(rows[0]["recognized_most_aces"], "no")

    def test_single_event_fetch_wraps_dict_and_list_payloads(self) -> None:
        class Common:
            calls = 0

            @classmethod
            def fetch_json(cls, _path, _params):
                cls.calls += 1
                if cls.calls == 1:
                    return {"id": "one"}
                return [{"id": "two"}]

        rows = MODULE.fetch_single_event_odds(
            Common(),
            "key",
            [{"id": "one"}, {"id": "two"}],
            "BetMGM",
        )
        self.assertEqual([row["id"] for row in rows], ["one", "two"])


if __name__ == "__main__":
    unittest.main()
