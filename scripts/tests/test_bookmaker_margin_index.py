from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "bookmaker_margin_index",
    ROOT / "scripts" / "bookmaker-margin-index.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def event(event_id: int, book_prices: dict[str, tuple[float, float, float]]) -> dict:
    bookmakers = {}
    for bookmaker, (home, draw, away) in book_prices.items():
        bookmakers[bookmaker] = [
            {
                "name": "ML",
                "home": home,
                "draw": draw,
                "away": away,
            },
            {
                "name": "Over/Under",
                "odds": [{"hdp": 2.5, "over": 1.91, "under": 1.91}],
            },
            {
                "name": "Asian Handicap",
                "odds": [{"hdp": -0.5, "home": 1.91, "away": 1.91}],
            },
        ]
    return {
        "id": str(event_id),
        "status": "pending",
        "home": f"Home {event_id}",
        "away": f"Away {event_id}",
        "bookmakers": bookmakers,
    }


class BookmakerMarginIndexTests(unittest.TestCase):
    def test_active_admin_recreational_books_are_targeted(self) -> None:
        expected = {"10bet", "Bally Bet", "Bet365", "Betfred", "SBK", "Spreadex"}
        self.assertTrue(expected.issubset(MODULE.TARGET_BOOKMAKERS))

    def test_ml_selection_labels_share_the_main_market(self) -> None:
        market = {
            "name": "Full Time Result",
            "odds": [
                {"label": "1", "odds": 2.4},
                {"label": "X", "odds": 3.2},
                {"label": "2", "odds": 3.1},
            ],
        }
        quotes = MODULE.quote_sets(market, "Match Winner", "Home FC", "Away FC")
        self.assertEqual(len(quotes), 1)
        self.assertEqual(quotes[0]["line"], "main")

    def test_incomplete_outcome_set_is_rejected(self) -> None:
        market = {
            "name": "Over/Under",
            "odds": [{"hdp": 2.5, "over": 1.9}],
        }
        self.assertEqual(MODULE.quote_sets(market, "Over/Under", "Home", "Away"), [])

    def test_tennis_moneyline_is_two_way_and_segmented(self) -> None:
        payload = []
        for event_id in (1, 2):
            bookmakers = {}
            for bookmaker in ("Book A", "Book B", "Book C", "Book D"):
                bookmakers[bookmaker] = [
                    {"name": "ML", "home": 1.8, "away": 2.1},
                    {"name": "Spread (Games)", "odds": [{"hdp": -2.5, "home": 1.91, "away": 1.91}]},
                    {"name": "Totals (Games)", "odds": [{"hdp": 22.5, "over": 1.91, "under": 1.91}]},
                ]
            payload.append({
                "id": str(event_id),
                "status": "pending",
                "home": f"Player A {event_id}",
                "away": f"Player B {event_id}",
                "_snapshot_sport": "tennis",
                "bookmakers": bookmakers,
            })

        result = MODULE.build_index(payload, "2026-08-28T12:00:00Z")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["summary"]["sports"], ["Tennis"])
        segments = {(row["sport"], row["market_family"]): row for row in result["segments"]}
        self.assertEqual(segments[("Tennis", "Match Winner")]["status"], "PASS")
        self.assertEqual(len(segments[("Tennis", "Match Winner")]["operators"]), 4)

    def test_index_passes_only_with_qualified_operator_coverage(self) -> None:
        prices = {
            "Tight Book": (2.55, 3.35, 2.95),
            "Book B": (2.45, 3.25, 2.85),
            "Book C": (2.42, 3.2, 2.8),
            "Book D": (2.4, 3.15, 2.75),
        }
        payload = [event(1, prices), event(2, prices)]
        result = MODULE.build_index(payload, "2026-08-28T12:00:00Z")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["summary"]["operators"], 4)
        self.assertEqual(result["operators"][0]["name"], "Tight Book")
        self.assertEqual(result["summary"]["observations"], 24)

    def test_index_fails_closed_with_thin_operator_rows(self) -> None:
        payload = [
            event(
                1,
                {
                    "Book A": (2.4, 3.2, 2.8),
                    "Book B": (2.4, 3.2, 2.8),
                    "Book C": (2.4, 3.2, 2.8),
                    "Book D": (2.4, 3.2, 2.8),
                },
            )
        ]
        result = MODULE.build_index(payload, "2026-08-28T12:00:00Z")
        self.assertEqual(result["status"], "INSUFFICIENT_COVERAGE")
        self.assertEqual(result["operators"], [])
        self.assertEqual(len(result["diagnostic_operators"]), 4)

    def test_error_summary_never_serializes_request_url(self) -> None:
        response = type("Response", (), {"status_code": 403})()
        error = MODULE.requests.HTTPError(
            "403 for https://api.odds-api.io/v3/odds/multi?apiKey=secret",
            response=response,
        )
        self.assertEqual(MODULE.safe_error_summary(error), "HTTPError: HTTP 403")

    def test_multi_book_403_falls_back_to_accessible_books(self) -> None:
        class Response:
            def __init__(self, status_code: int, payload: object) -> None:
                self.status_code = status_code
                self._payload = payload
                self.ok = 200 <= status_code < 300

            def json(self) -> object:
                return self._payload

            def raise_for_status(self) -> None:
                if not self.ok:
                    raise MODULE.requests.HTTPError(response=self)

        scheduled = [{
            "id": "1",
            "date": "2026-08-29T15:00:00Z",
            "home": "Home 1",
            "away": "Away 1",
            "league": {"name": "Premier League"},
        }]
        bet365 = [event(1, {"Bet365": (2.4, 3.2, 2.8)})]
        betfred = [event(1, {"Betfred": (2.5, 3.3, 2.9)})]
        responses = [
            Response(200, [{"name": "Bet365"}, {"name": "Betfred"}]),
            Response(200, scheduled),
            Response(403, {"message": "blocked combined request"}),
            Response(200, bet365),
            Response(200, betfred),
        ]
        with patch.object(MODULE.requests, "get", side_effect=responses) as get:
            payload, bookmakers = MODULE.fetch_payload("secret", 4, 10, 1, ("football",))

        self.assertEqual(bookmakers, ["Bet365", "Betfred"])
        self.assertEqual(len(payload), 2)
        self.assertTrue(all(row["_snapshot_sport"] == "football" for row in payload))
        self.assertEqual(get.call_count, 5)


if __name__ == "__main__":
    unittest.main()
