from __future__ import annotations

import importlib.util
import json
import tempfile
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
    def test_broad_exact_uk_catalogue_is_targeted(self) -> None:
        expected = {
            "10BET", "888sport", "Bet365", "Betano", "Betfair Sportsbook",
            "BetMGM", "BetUK", "BetVictor", "Betway", "Coral", "Ladbrokes",
            "LeoVegas", "Mr Green", "Paddy Power", "Parimatch", "QuinnBet",
            "Unibet", "William Hill",
        }
        self.assertTrue(expected.issubset(MODULE.TARGET_BOOKMAKERS))
        self.assertGreaterEqual(len(MODULE.TARGET_BOOKMAKERS), 20)

    def test_oddschecker_catalogue_has_23_fixed_odds_bookmakers_only(self) -> None:
        self.assertEqual(len(MODULE.ODDSCHECKER_TARGET_BOOKMAKERS), 23)
        self.assertNotIn("Betfair", MODULE.ODDSCHECKER_TARGET_BOOKMAKERS)
        self.assertNotIn("Matchbook", MODULE.ODDSCHECKER_TARGET_BOOKMAKERS)
        self.assertNotIn("Sporting Index", MODULE.ODDSCHECKER_TARGET_BOOKMAKERS)

    def test_fractional_prices_are_converted_to_decimal(self) -> None:
        self.assertEqual(MODULE.fractional_to_decimal("evens"), 2.0)
        self.assertEqual(MODULE.fractional_to_decimal("4/5"), 1.8)
        self.assertIsNone(MODULE.fractional_to_decimal("-"))

    def test_oddschecker_capture_excludes_non_fixed_odds_operators(self) -> None:
        prices = [
            {"code": "B3", "bookmaker": "bet365", "fractional": "1/1"},
            {"code": "WH", "bookmaker": "William Hill", "fractional": "21/20"},
            {"code": "BF", "bookmaker": "Betfair", "fractional": "11/10"},
            {"code": "MA", "bookmaker": "Matchbook", "fractional": "11/10"},
            {"code": "SI", "bookmaker": "Sporting Index", "fractional": "11/10"},
        ]
        capture = {
            "captured_at": "2026-08-31T12:00:00Z",
            "capture_mode": "manual_browser_one_off",
            "pages": [{
                "sport": "football",
                "event": "Home FC vs Away FC",
                "home": "Home FC",
                "away": "Away FC",
                "grids": [{
                    "market": "Win Market",
                    "selections": [
                        {"label": "Home FC", "prices": prices},
                        {"label": "Draw", "prices": prices},
                        {"label": "Away FC", "prices": prices},
                    ],
                }],
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.json"
            path.write_text(json.dumps(capture), encoding="utf-8")
            payload, bookmakers, metadata = MODULE.load_oddschecker_capture(path)

        self.assertEqual(bookmakers, ["Bet365", "William Hill"])
        self.assertEqual(set(payload[0]["bookmakers"]), {"Bet365", "William Hill"})
        self.assertEqual(metadata["source"], "oddschecker_public_browser_grid")

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

    def test_complete_total_without_a_verified_line_is_rejected(self) -> None:
        market = {
            "name": "Over/Under",
            "over": 1.91,
            "under": 1.91,
        }
        self.assertEqual(MODULE.quote_sets(market, "Over/Under", "Home", "Away"), [])

    def test_prices_from_different_total_lines_are_not_paired(self) -> None:
        market = {
            "name": "Over/Under",
            "odds": [
                {"label": "Over 2.5", "odds": 1.91},
                {"label": "Under 3.5", "odds": 1.91},
            ],
        }
        self.assertEqual(MODULE.quote_sets(market, "Over/Under", "Home", "Away"), [])

    def test_bookmaker_aliases_do_not_absorb_regional_variants(self) -> None:
        self.assertEqual(MODULE.display_bookmaker("Unibet UK"), "Unibet")
        self.assertEqual(MODULE.display_bookmaker("Unibet"), "Unibet")
        self.assertEqual(MODULE.display_bookmaker("Bet365 (no latency)"), "Bet365")
        self.assertEqual(MODULE.display_bookmaker("Bwin DE"), "Bwin DE")

    def test_target_selection_uses_one_bounded_account_request(self) -> None:
        response = type("Response", (), {"raise_for_status": lambda self: None})()
        with patch.object(MODULE.requests, "put", return_value=response) as put:
            MODULE.select_target_bookmakers("secret", ["Bet365", "William Hill"])

        self.assertEqual(put.call_count, 1)
        self.assertEqual(put.call_args.kwargs["params"]["bookmakers"], "Bet365,William Hill")

    def test_selected_bookmaker_response_variants_are_normalized(self) -> None:
        self.assertEqual(
            MODULE.selected_bookmaker_names({"selectedBookmakers": ["Bet365", "BetMGM"]}),
            ["Bet365", "BetMGM"],
        )
        self.assertEqual(
            MODULE.selected_bookmaker_names({"bookmakers": [{"name": "Bet365"}]}),
            ["Bet365"],
        )

    def test_reset_restores_original_selection_when_broad_selection_fails(self) -> None:
        class Response:
            def raise_for_status(self) -> None:
                return None

        selection_error = MODULE.requests.HTTPError("blocked")
        with (
            patch.object(MODULE, "get_selected_bookmakers", return_value=["Bet365", "BetMGM"]),
            patch.object(MODULE.requests, "put", return_value=Response()) as put,
            patch.object(
                MODULE,
                "select_target_bookmakers",
                side_effect=[selection_error, None],
            ) as select,
        ):
            with self.assertRaisesRegex(RuntimeError, "original bookmaker selection was restored"):
                MODULE.reset_target_bookmakers("secret", ["Bet365", "BetMGM", "William Hill"])

        self.assertEqual(put.call_count, 1)
        self.assertEqual(select.call_args_list[1].args[1], ["Bet365", "BetMGM"])

    def test_player_props_require_matching_player_stat_and_line(self) -> None:
        market = {
            "name": "Player Props",
            "odds": [
                {"label": "Player A (Shots) Over 1.5", "odds": 1.91},
                {"label": "Player B (Shots) Under 1.5", "odds": 1.91},
            ],
        }
        self.assertEqual(MODULE.quote_sets(market, "Player Props", "Home", "Away"), [])

        market["odds"].append({"label": "Player A (Shots) Under 1.5", "odds": 1.91})
        quotes = MODULE.quote_sets(market, "Player Props", "Home", "Away")
        self.assertEqual(len(quotes), 1)

    def test_new_complete_count_market_families_are_recognized(self) -> None:
        self.assertEqual(MODULE.market_family("Corners Totals"), "Corners")
        self.assertEqual(MODULE.market_family("Bookings Totals"), "Cards")
        self.assertEqual(MODULE.market_family("Total Shots Home"), "Team Shots")
        self.assertEqual(MODULE.market_family("Goalkeeper Saves Away"), "Goalkeeper Saves")
        self.assertEqual(MODULE.market_family("Team Total (Aces) Home", "tennis"), "Player Aces")

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

    def test_market_segments_can_publish_without_blended_operator_ranking(self) -> None:
        definitions = (
            ("football", "ML", {"home": 2.4, "draw": 3.2, "away": 2.8}),
            ("football", "Over/Under", {"hdp": 2.5, "over": 1.91, "under": 1.91}),
            ("tennis", "ML", {"home": 1.8, "away": 2.1}),
            ("tennis", "Totals (Games)", {"hdp": 22.5, "over": 1.91, "under": 1.91}),
        )
        payload = []
        event_id = 0
        for segment_index, (sport, market_name, prices) in enumerate(definitions):
            for _ in range(2):
                event_id += 1
                payload.append({
                    "id": str(event_id),
                    "status": "pending",
                    "home": f"Home {event_id}",
                    "away": f"Away {event_id}",
                    "_snapshot_sport": sport,
                    "bookmakers": {
                        f"Segment {segment_index} Book {book_index}": [
                            {"name": market_name, **prices},
                        ]
                        for book_index in range(3)
                    },
                })

        result = MODULE.build_index(payload, "2026-08-28T12:00:00Z")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["operators"], [])
        self.assertEqual(len([row for row in result["segments"] if row["status"] == "PASS"]), 4)

    def test_two_book_cross_sport_snapshot_is_explicitly_limited(self) -> None:
        definitions = (
            ("football", "ML", {"home": 2.4, "draw": 3.2, "away": 2.8}),
            ("football", "Over/Under", {"hdp": 2.5, "over": 1.91, "under": 1.91}),
            ("tennis", "ML", {"home": 1.8, "away": 2.1}),
            ("tennis", "Totals (Games)", {"hdp": 22.5, "over": 1.91, "under": 1.91}),
        )
        payload = []
        event_id = 0
        for sport, market_name, prices in definitions:
            for _ in range(3):
                event_id += 1
                payload.append({
                    "id": str(event_id),
                    "status": "pending",
                    "home": f"Home {event_id}",
                    "away": f"Away {event_id}",
                    "_snapshot_sport": sport,
                    "bookmakers": {
                        bookmaker: [{"name": market_name, **prices}]
                        for bookmaker in ("Bet365", "BetMGM")
                    },
                })

        result = MODULE.build_index(payload, "2026-08-28T12:00:00Z")
        self.assertEqual(result["status"], "PASS_LIMITED")
        limited = [row for row in result["segments"] if row["status"] == "PASS_LIMITED"]
        self.assertEqual(len(limited), 4)
        self.assertTrue(all(len(row["operators"]) == 2 for row in limited))

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
        william_hill = [event(1, {"William Hill": (2.5, 3.3, 2.9)})]
        responses = [
            Response(200, [{"name": "Bet365"}, {"name": "William Hill"}]),
            Response(200, scheduled),
            Response(403, {"message": "blocked combined request"}),
            Response(200, bet365),
            Response(200, william_hill),
        ]
        with patch.object(MODULE.requests, "get", side_effect=responses) as get:
            payload, bookmakers, capture = MODULE.fetch_payload("secret", 4, 10, 1, ("football",))

        self.assertEqual(bookmakers, ["Bet365", "William Hill"])
        self.assertEqual(len(payload), 2)
        self.assertTrue(all(row["_snapshot_sport"] == "football" for row in payload))
        self.assertEqual(capture["sports"][0]["operators"][0]["status"], "returned")
        self.assertEqual(get.call_count, 5)

    def test_successful_multi_request_probes_silently_missing_books(self) -> None:
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
        combined = [event(1, {"Bet365": (2.4, 3.2, 2.8)})]
        william_hill = [event(1, {"William Hill": (2.5, 3.3, 2.9)})]
        responses = [
            Response(200, [{"name": "Bet365"}, {"name": "William Hill"}]),
            Response(200, scheduled),
            Response(200, combined),
            Response(200, william_hill),
        ]
        with patch.object(MODULE.requests, "get", side_effect=responses) as get:
            payload, bookmakers, capture = MODULE.fetch_payload("secret", 4, 10, 1, ("football",))

        self.assertEqual(bookmakers, ["Bet365", "William Hill"])
        self.assertEqual(len(payload), 2)
        operators = {row["provider_name"]: row for row in capture["sports"][0]["operators"]}
        self.assertEqual(operators["Bet365"]["request_mode"], "combined")
        self.assertEqual(operators["William Hill"]["request_mode"], "fallback")
        self.assertEqual(operators["William Hill"]["status"], "returned")
        self.assertEqual(get.call_count, 4)


if __name__ == "__main__":
    unittest.main()
