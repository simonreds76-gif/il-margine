from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import UTC, date, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import goalkeeper_saves_live as live  # noqa: E402


def load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


capture = load_script("goalkeeper_saves_capture", "goalkeeper-saves-capture.py")
shadow = load_script("goalkeeper_saves_shadow", "goalkeeper-saves-shadow.py")
settle = load_script("goalkeeper_saves_settle", "goalkeeper-saves-settle.py")


class GoalkeeperSavesLiveTests(unittest.TestCase):
    @staticmethod
    def history(team: str, venue: str) -> list[dict[str, str]]:
        rows = []
        for index in range(8):
            rows.append(
                {
                    "date": f"2026-07-{index + 1:02d}",
                    "team": team,
                    "venue": venue if index % 2 == 0 else ("away" if venue == "home" else "home"),
                    "sot_for": "5",
                    "sot_against": "4",
                    "shots_for": "13",
                    "shots_against": "11",
                    "xg_for": "1.5",
                    "xg_against": "1.2",
                    "goals_against": "1",
                }
            )
        return rows

    def test_registered_features_are_causal_and_complete(self) -> None:
        features, blockers = live.build_features(
            histories={"home": self.history("Home", "home"), "away": self.history("Away", "away")},
            team="Home",
            opponent="Away",
            venue="home",
            kickoff_day=date(2026, 8, 1),
            home_price=2.0,
            draw_price=3.5,
            away_price=4.0,
        )
        self.assertEqual(blockers, [])
        self.assertIsNotNone(features)
        self.assertEqual(len(features or ()), 9)

    def test_missing_market_is_not_mislabeled_as_missing_registered_feature(self) -> None:
        features, blockers = live.build_features(
            histories={"home": self.history("Home", "home"), "away": self.history("Away", "away")},
            team="Home",
            opponent="Away",
            venue="home",
            kickoff_day=date(2026, 8, 1),
            home_price=0.0,
            draw_price=0.0,
            away_price=0.0,
        )
        self.assertIsNone(features)
        self.assertEqual(blockers, ["missing_three_way_market"])

    def test_confirmed_goalkeeper_gate(self) -> None:
        fixture = {
            "lineup_type": "standard",
            "home_starters": [{"name": "David Raya", "role_group": "GK"}],
            "away_starters": [{"name": "Nick Pope", "role_group": "GK"}],
        }
        self.assertEqual(live.resolve_goalkeeper(fixture, "D. Raya")[:2], ("home", "confirmed_starter"))
        fixture["lineup_type"] = "predicted"
        self.assertEqual(live.resolve_goalkeeper(fixture, "David Raya")[:2], ("home", "predicted_starter"))

    def test_capture_extracts_over_lines_and_match_prices(self) -> None:
        event = {
            "id": "1",
            "date": "2026-08-22T15:00:00Z",
            "home": "Home",
            "away": "Away",
            "bookmakers": {
                "Bet365": [
                    {
                        "name": "Fulltime Result",
                        "odds": [
                            {"label": "Home", "odds": "2.00"},
                            {"label": "Draw", "odds": "3.50"},
                            {"label": "Away", "odds": "4.00"},
                        ],
                    },
                    {
                        "name": "Goalkeeper Saves",
                        "odds": [{"label": "Keeper One", "hdp": 3.5, "over": "1.90", "under": "1.90"}],
                    },
                ]
            },
        }
        rows = capture.extract_rows(
            [event],
            {"1": {**event, "league": {"name": "England Premier League"}}},
            bookmaker_name="Bet365",
            captured_at="2026-08-20T10:00:00Z",
            capture_mode="publication",
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["league"], "epl")
        self.assertEqual(rows[0]["home_price"], "2.0000")
        self.assertEqual([row["side"] for row in rows], ["over", "under"])

    def test_capture_accepts_alternate_three_way_shape_and_event_fallback(self) -> None:
        event = {
            "id": "1",
            "date": "2026-08-22T15:00:00Z",
            "home": "Home",
            "away": "Away",
            "bookmakers": {
                "Bet365": [
                    {
                        "name": "Goalkeeper Saves",
                        "odds": [{"label": "Keeper One", "hdp": 3.5, "over": "1.90"}],
                    }
                ]
            },
        }
        meta = {
            **event,
            "league": {"name": "England Premier League"},
            "bookmakers": {
                "Bet365": [{"name": "ML", "home": 2.0, "draw": 3.5, "away": 4.0}]
            },
        }
        rows = capture.extract_rows(
            [event],
            {"1": meta},
            bookmaker_name="Bet365",
            captured_at="2026-08-20T10:00:00Z",
            capture_mode="publication",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["home_price"], "2.0000")
        self.assertEqual(rows[0]["source"], "odds_api_io:event_metadata")

    def test_capture_does_not_treat_half_time_ml_as_full_time_result(self) -> None:
        event = {
            "home": "Home",
            "away": "Away",
            "bookmakers": {
                "Bet365": [{"name": "ML HT", "home": 2.0, "draw": 3.5, "away": 4.0}]
            },
        }
        self.assertEqual(capture.three_way_prices(event, "Bet365"), (None, None, None))

    def test_integer_line_prices_include_push_return(self) -> None:
        priced = live.price_side("over", 3.0, 2.20, 3.2, 0.25)
        expected_fair = (1.0 - priced["push_probability"]) / priced["model_probability"]
        self.assertAlmostEqual(priced["fair_odds"], expected_fair)

    def test_signal_ledger_is_append_only_and_deduplicated(self) -> None:
        candidate = {field: "" for field in shadow.CANDIDATE_FIELDS}
        candidate.update(
            {
                "event_id": "fixture",
                "goalkeeper": "Keeper",
                "line": "3.5",
                "side": "over",
                "candidate_status": "eligible_shadow",
                "strongest_for_fixture": "yes",
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "signals.csv"
            added, rows = shadow.append_signals(path, [candidate], "2026-08-20T10:00:00Z")
            added_again, rows_again = shadow.append_signals(path, [candidate], "2026-08-20T11:00:00Z")
        self.assertEqual((added, added_again), (1, 0))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows_again), 1)

    def test_predicted_starting_goalkeeper_enters_shadow_ledger(self) -> None:
        candidate = {field: "" for field in shadow.CANDIDATE_FIELDS}
        candidate.update(
            {
                "event_id": "fixture",
                "goalkeeper": "Keeper",
                "line": "3.5",
                "side": "over",
                "edge": "0.12",
                "lineup_status": "predicted_starter",
                "candidate_status": "eligible_shadow",
                "blockers": "",
                "strongest_for_fixture": "yes",
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            added, rows = shadow.append_signals(
                Path(directory) / "signals.csv", [candidate], "2026-08-20T10:00:00Z"
            )
        self.assertEqual(added, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["lineup_status"], "predicted_starter")

    def test_infrastructure_failure_preserves_existing_candidate_board(self) -> None:
        existing = [{
            "kickoff_at": "2026-08-20T19:00:00Z",
            "model_mean": "3.2",
            "candidate_status": "blocked",
            "blockers": "predicted_starter",
        }]
        scanned = [{"model_mean": "", "candidate_status": "blocked", "blockers": "history_lt_6"}]
        now = datetime(2026, 8, 20, 18, 0, tzinfo=UTC)
        self.assertTrue(shadow.should_preserve_candidate_board(existing, scanned, now))

    def test_empty_local_scan_preserves_current_hosted_board(self) -> None:
        existing = [{"kickoff_at": "2026-08-20T19:00:00Z", "model_mean": "3.2"}]
        now = datetime(2026, 8, 20, 18, 0, tzinfo=UTC)
        self.assertTrue(shadow.should_preserve_candidate_board(existing, [], now))

    def test_synced_predicted_starter_is_reclassified_for_tracking(self) -> None:
        rows = shadow.apply_starter_tracking_policy([{
            "lineup_status": "predicted_starter",
            "odds_decimal": "2.20",
            "edge": "0.22",
            "candidate_status": "blocked",
            "blockers": "predicted_starter",
        }])
        self.assertEqual(rows[0]["candidate_status"], "eligible_shadow")
        self.assertEqual(rows[0]["blockers"], "")

    def test_primary_selection_prefers_near_even_value_over_tail_edge(self) -> None:
        rows = [
            {
                "event_id": "fixture",
                "candidate_status": "eligible_shadow",
                "odds_decimal": "2.20",
                "model_probability": "0.486445",
                "edge": "0.070178",
                "strongest_for_fixture": "no",
            },
            {
                "event_id": "fixture",
                "candidate_status": "tail_diagnostic",
                "odds_decimal": "11.00",
                "model_probability": "0.130475",
                "edge": "0.435224",
                "strongest_for_fixture": "no",
            },
        ]
        shadow.mark_primary_selections(rows)
        self.assertEqual(rows[0]["strongest_for_fixture"], "yes")
        self.assertEqual(rows[1]["strongest_for_fixture"], "no")

    def test_named_goalkeeper_saves_are_extracted(self) -> None:
        payload = {
            "response": [
                {
                    "players": [
                        {
                            "player": {"id": 1, "name": "David Raya"},
                            "statistics": [
                                {
                                    "games": {"minutes": 90, "position": "G", "substitute": False},
                                    "goals": {"saves": 4},
                                }
                            ],
                        }
                    ]
                }
            ]
        }
        actual, metadata = settle.player_saves(payload, "D. Raya")
        self.assertEqual(actual, 4)
        self.assertEqual(metadata["position"], "G")

    def test_settlement_waits_until_match_has_had_time_to_finish(self) -> None:
        now = settle.datetime(2026, 8, 26, 18, 0, tzinfo=settle.UTC)
        self.assertFalse(settle.signal_is_due({"kickoff_at": "2026-08-26T16:00:00Z"}, now))
        self.assertTrue(settle.signal_is_due({"kickoff_at": "2026-08-26T14:00:00Z"}, now))

    def test_api_errors_are_exposed_for_settlement_diagnostics(self) -> None:
        payload = {"errors": {"plan": "Free plans do not have access to this date."}}
        self.assertEqual(
            settle.api_error_messages(payload),
            ["plan: Free plans do not have access to this date."],
        )

    def test_settlement_uses_player_total_and_close_clv(self) -> None:
        signal = {"line": "3.5", "side": "over", "odds_decimal": "2.00", "stake_units": "0.5"}
        settle.settle_row(signal, 4, 1.80, "2026-08-20T12:00:00Z")
        self.assertEqual(signal["status"], "won")
        self.assertEqual(signal["pnl_units"], "0.5000")
        self.assertAlmostEqual(float(signal["clv"]), (2.0 / 1.8) - 1.0, places=6)

        under_signal = {"line": "3.5", "side": "under", "odds_decimal": "1.90", "stake_units": "0.5"}
        settle.settle_row(under_signal, 3, None, "2026-08-20T12:00:00Z")
        self.assertEqual(under_signal["status"], "won")

    def test_close_requires_post_signal_close_capture_near_kickoff(self) -> None:
        signal = {
            "event_id": "fixture",
            "goalkeeper": "Keeper One",
            "line": "3.5",
            "side": "over",
            "created_at": "2026-08-20T12:00:00Z",
            "kickoff_at": "2026-08-20T15:00:00Z",
        }
        base = {
            "event_id": "fixture",
            "player": "Keeper One",
            "line": "3.5",
            "side": "over",
            "odds_decimal": "1.80",
        }
        rows = [
            {**base, "capture_mode": "publication", "captured_at": "2026-08-20T14:30:00Z"},
            {**base, "capture_mode": "close", "captured_at": "2026-08-20T11:00:00Z"},
        ]
        self.assertIsNone(settle.latest_close(rows, signal))
        rows.append({**base, "capture_mode": "close", "captured_at": "2026-08-20T14:00:00Z"})
        self.assertEqual(settle.latest_close(rows, signal), 1.8)

    def test_shadow_report_calculates_true_close_evidence(self) -> None:
        signals = [
            {"status": "won", "stake_units": "0.5", "pnl_units": "0.5", "clv": "0.10"},
            {"status": "lost", "stake_units": "0.5", "pnl_units": "-0.5", "clv": ""},
        ]
        report = shadow.report_payload([], signals, "2026-08-20T12:00:00Z", 0)
        self.assertEqual(report["evidence"]["clv_matched"], 1)
        self.assertEqual(report["evidence"]["true_close_coverage"], 0.5)
        self.assertEqual(report["evidence"]["clv"], 0.1)


if __name__ == "__main__":
    unittest.main()
