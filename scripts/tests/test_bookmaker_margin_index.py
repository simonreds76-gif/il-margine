from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


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
    def test_ml_selection_labels_share_the_main_market(self) -> None:
        market = {
            "name": "Full Time Result",
            "odds": [
                {"label": "1", "odds": 2.4},
                {"label": "X", "odds": 3.2},
                {"label": "2", "odds": 3.1},
            ],
        }
        quotes = MODULE.quote_sets(market, "Moneyline", "Home FC", "Away FC")
        self.assertEqual(len(quotes), 1)
        self.assertEqual(quotes[0]["line"], "main")

    def test_incomplete_outcome_set_is_rejected(self) -> None:
        market = {
            "name": "Over/Under",
            "odds": [{"hdp": 2.5, "over": 1.9}],
        }
        self.assertEqual(MODULE.quote_sets(market, "Over/Under", "Home", "Away"), [])

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


if __name__ == "__main__":
    unittest.main()
