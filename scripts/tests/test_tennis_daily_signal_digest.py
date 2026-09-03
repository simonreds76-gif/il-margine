from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "tennis-daily-signal-digest.py"
SPEC = importlib.util.spec_from_file_location("tennis_daily_signal_digest", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TennisDailySignalDigestTests(unittest.TestCase):
    def test_ml_signal_formats_price_fair_edge_and_stake(self) -> None:
        lane = MODULE.Lane("VOL200", Path("unused.csv"), "TRACKED EXPANSION", 10)
        signal = MODULE.row_to_signal(
            {
                "date": "2026-07-16",
                "player1": "Player One",
                "player2": "Player Two",
                "side": "P2",
                "bet_type": "match",
                "pin_odds2": "3.18",
                "our_odds2": "2.8058",
                "value_pct": "13.34",
                "stake_units": "1.0",
                "settlement_status": "pending",
            },
            lane,
            "2026-07-16",
        )
        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertEqual(signal.match, "Player One vs Player Two")
        self.assertIn("Player Two ML @ 3.18", signal.selection)
        self.assertIn("fair 2.806", signal.selection)
        self.assertIn("edge +13.3%", signal.selection)
        self.assertTrue(signal.selection.endswith("1u"))

    def test_spread_signal_uses_selected_player_and_handicap(self) -> None:
        lane = MODULE.Lane("CLAY BO3", Path("unused.csv"), "SHADOW / RESEARCH", 30)
        signal = MODULE.row_to_signal(
            {
                "date": "2026-07-16",
                "player1": "Player One",
                "player2": "Player Two",
                "side": "P2-",
                "bet_type": "spread",
                "spread_line": "-4",
                "spread_odds": "1.855",
                "value_pct": "9.67",
                "stake_units": "2",
                "settlement_status": "pending",
            },
            lane,
            "2026-07-16",
        )
        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertIn("Player Two -4 games @ 1.855", signal.selection)

    def test_registered_gap_candidate_is_provisional_half_unit(self) -> None:
        signal = MODULE.gap_replacement_signal(
            {
                "date": "2026-07-16",
                "player1": "Player One",
                "player2": "Player Two",
                "selected_player": "Player One",
                "selected_side": "P1",
                "bet_type": "match",
                "selected_odds": "2.75",
                "fair_odds1": "2.10",
                "value_pct": "30.95",
                "model_market_gap_pp": "12.4",
                "diagnostic_quality": "LOW",
                "replacement_cohorts": "volume200_gap_10_15_same_side",
                "replacement_forward_eligible": "1",
                "settlement_status": "pending",
            },
            "2026-07-16",
        )
        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertEqual(signal.section, "PROVISIONAL ML EXPANSION")
        self.assertEqual(signal.labels, ["VOL200 GAP"])
        self.assertIn("gap 12.4pp", signal.selection)
        self.assertIn("quality LOW", signal.selection)
        self.assertTrue(signal.selection.endswith("0.5u"))

    def test_hard_side_flip_candidate_is_private_half_unit_shadow(self) -> None:
        signal = MODULE.gap_replacement_signal(
            {
                "date": "2026-08-01",
                "surface": "Hard",
                "player1": "Player One",
                "player2": "Player Two",
                "selected_player": "Player Two",
                "selected_side": "P2",
                "bet_type": "match",
                "selected_odds": "2.28",
                "fair_odds2": "1.85",
                "value_pct": "23.25",
                "model_market_gap_pp": "3.31",
                "diagnostic_quality": "HIGH",
                "data_coverage_tag": "HIGH",
                "side_flip": "1",
                "short_favorite_guard": "0",
                "policy_profiles": "volume_200",
                "settlement_status": "pending",
            },
            "2026-08-01",
        )
        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertEqual(signal.section, "PROVISIONAL HARD ML")
        self.assertEqual(signal.labels, ["HARD FLIP"])
        self.assertIn("model/market side flip", signal.selection)
        self.assertTrue(signal.selection.endswith("0.5u"))

    def test_hard_side_flip_candidate_keeps_safety_exclusions(self) -> None:
        base = {
            "date": "2026-08-01",
            "surface": "Hard",
            "player1": "Player One",
            "player2": "Player Two",
            "selected_player": "Player Two",
            "selected_side": "P2",
            "bet_type": "match",
            "selected_odds": "2.28",
            "model_market_gap_pp": "3.31",
            "diagnostic_quality": "HIGH",
            "data_coverage_tag": "HIGH",
            "side_flip": "1",
            "short_favorite_guard": "0",
            "policy_profiles": "volume_200",
            "settlement_status": "pending",
        }
        for override in (
            {"surface": "Clay"},
            {"model_market_gap_pp": "10.01"},
            {"policy_profiles": ""},
            {"data_coverage_tag": "PARTIAL"},
            {"short_favorite_guard": "1"},
        ):
            with self.subTest(override=override):
                self.assertIsNone(
                    MODULE.gap_replacement_signal({**base, **override}, "2026-08-01")
                )

    def test_over_only_trackable_prop_is_rendered_as_shadow_watchlist(self) -> None:
        original_read_csv = MODULE.read_csv
        MODULE.read_csv = lambda _path: [
            {
                "date": "2026-07-29",
                "player": "Aleksandar Vukic",
                "opponent": "Lorenzo Musetti",
                "market": "aces",
                "line": "9.5",
                "over_odds": "3.40",
                "fair_over_odds": "2.515",
                "value_over_pct": "35.17",
                "trackable_shadow": "true",
                "shadow_side": "OVER",
                "bettable": "false",
                "recommended_side": "",
                "match_start_utc": "2026-07-29T17:00:00Z",
            }
        ]
        try:
            signals = MODULE.props_signals("2026-07-29")
        finally:
            MODULE.read_csv = original_read_csv

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].section, "BET365 PROPS WATCHLIST")
        self.assertEqual(signals[0].labels, ["ACES/DF WATCH"])
        self.assertIn("Vukic aces Over 9.5 @ 3.4", signals[0].selection)
        self.assertIn("fair 2.515", signals[0].selection)
        self.assertTrue(signals[0].selection.endswith("shadow evidence only"))

    def test_service_break_market_has_its_own_research_label(self) -> None:
        original_read_csv = MODULE.read_csv
        MODULE.read_csv = lambda _path: [
            {
                "date": "2026-08-11",
                "player": "Nishesh Basavareddy",
                "opponent": "Learner Tien",
                "market": "match_breaks",
                "line": "6.5",
                "over_odds": "1.90",
                "fair_over_odds": "2.43",
                "value_over_pct": "-21.95",
                "trackable_shadow": "true",
                "shadow_side": "OVER",
                "bettable": "false",
                "recommended_side": "",
                "match_start_utc": "2026-08-11T17:00:00Z",
            }
        ]
        try:
            signals = MODULE.props_signals("2026-08-11")
        finally:
            MODULE.read_csv = original_read_csv

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].section, "BET365 BREAKS WATCHLIST")
        self.assertEqual(signals[0].labels, ["BREAKS WATCH"])
        self.assertIn("Match service breaks Over 6.5 @ 1.9", signals[0].selection)
        self.assertTrue(signals[0].selection.endswith("shadow evidence only"))

    def test_props_watchlist_excludes_other_event_dates(self) -> None:
        original_read_csv = MODULE.read_csv
        MODULE.read_csv = lambda _path: [
            {
                "date": "2026-07-30",
                "player": "Alejandro Tabilo",
                "opponent": "Terence Atmane",
                "market": "aces",
                "line": "9.5",
                "over_odds": "3.50",
                "trackable_shadow": "true",
                "shadow_side": "OVER",
            }
        ]
        try:
            signals = MODULE.props_signals("2026-07-29")
        finally:
            MODULE.read_csv = original_read_csv

        self.assertEqual(signals, [])

    def test_break_watchlist_identity_survives_line_and_side_repricing(self) -> None:
        original_read_csv = MODULE.read_csv
        base = {
            "date": "2026-09-03",
            "player": "Madison Keys",
            "opponent": "Anna Bondar",
            "market": "player_breaks",
            "fair_over_odds": "1.8",
            "fair_under_odds": "2.2",
            "trackable_shadow": "true",
            "bettable": "false",
        }
        MODULE.read_csv = lambda _path: [
            {**base, "line": "3.5", "over_odds": "1.9", "shadow_side": "OVER"},
            {**base, "line": "4.5", "under_odds": "2.0", "shadow_side": "UNDER"},
        ]
        try:
            signals = MODULE.props_signals("2026-09-03")
        finally:
            MODULE.read_csv = original_read_csv

        self.assertEqual(len(signals), 2)
        self.assertEqual(signals[0].key, signals[1].key)

    def test_render_stays_within_telegram_limit(self) -> None:
        signals = [
            MODULE.Signal(
                section="SHADOW / RESEARCH",
                priority=20,
                labels=["TEST"],
                match=f"Player {index} vs Opponent {index}",
                selection="Player selection @ 2.0 | edge +10.0% | 1u " + ("x" * 200),
                edge_pct=10.0,
            )
            for index in range(50)
        ]
        messages = MODULE.render_messages("2026-07-16", signals, [])
        self.assertGreater(len(messages), 1)
        self.assertTrue(all(len(message) <= MODULE.TELEGRAM_LIMIT for message in messages))

    def test_new_only_state_returns_only_unseen_selections(self) -> None:
        old = MODULE.Signal("CORE", 0, ["STRICT"], "A vs B", "A ML", 10.0, key=("old",))
        new = MODULE.Signal("BET365 PROPS", 40, ["ACES/DF"], "C vs D", "C aces Over", 9.0, key=("new",))
        state = {"date": "2026-08-04", "signal_ids": [MODULE.signal_id(old)]}
        self.assertEqual(
            MODULE.new_signals_since_state([old, new], state, "2026-08-04"),
            [new],
        )

    def test_update_message_explains_that_only_new_props_are_included(self) -> None:
        signal = MODULE.Signal(
            "BET365 PROPS", 40, ["ACES/DF"], "A vs B", "A aces Over 7.5 @ 2", 9.0, key=("new",)
        )
        message = MODULE.render_messages("2026-08-04", [signal], [], update_only=True)[0]
        self.assertIn("TENNIS SIGNAL UPDATE", message)
        self.assertIn("Only selections not included in the earlier alert", message)
        self.assertIn("evidence only, not bets", message)

    def test_github_auth_prefers_gh_cli_before_credential_manager(self) -> None:
        completed = MODULE.subprocess.CompletedProcess(["gh", "auth", "token"], 0, "token-from-gh\n", "")
        with patch.dict(MODULE.os.environ, {"GH_TOKEN": "", "GITHUB_TOKEN": ""}, clear=False), patch.object(
            MODULE.subprocess, "run", return_value=completed
        ) as run:
            self.assertEqual(MODULE.github_token(), "token-from-gh")
        self.assertEqual(run.call_args.args[0], ["gh", "auth", "token"])

    def test_same_digest_state_can_be_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"
            path.write_text('{"date":"2026-07-16","digest_hash":"abc"}', encoding="utf-8")
            self.assertEqual(MODULE.load_state(path)["digest_hash"], "abc")

    def test_new_only_noop_preserves_same_day_dispatch_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "state.json"
            report_path = Path(temp_dir) / "report.txt"
            ready_path = Path(temp_dir) / "ready.json"
            ready_path.write_text('{"date":"2026-08-04","status":"ok"}', encoding="utf-8")
            state_path.write_text(
                '{"date":"2026-08-04","digest_hash":"old","signal_ids":[],"dispatched_at":"2026-08-04T08:00:00Z"}',
                encoding="utf-8",
            )
            with (
                patch.object(MODULE, "collect_signals", return_value=([], [])),
                patch.object(
                    MODULE.sys,
                    "argv",
                    [
                        str(SCRIPT),
                        "--date",
                        "2026-08-04",
                        "--report",
                        str(report_path),
                        "--state",
                        str(state_path),
                        "--ready-state",
                        str(ready_path),
                        "--new-only",
                    ],
                ),
            ):
                self.assertEqual(MODULE.main(), 0)

            updated = MODULE.load_state(state_path)
            self.assertEqual(updated["dispatched_at"], "2026-08-04T08:00:00Z")

    def test_ready_state_requires_matching_date_and_ok_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ready.json"
            path.write_text('{"date":"2026-07-16","status":"ok"}', encoding="utf-8")
            self.assertTrue(MODULE.signal_generation_is_ready(path, "2026-07-16"))
            self.assertFalse(MODULE.signal_generation_is_ready(path, "2026-07-17"))
            path.write_text('{"date":"2026-07-16","status":"failed"}', encoding="utf-8")
            self.assertFalse(MODULE.signal_generation_is_ready(path, "2026-07-16"))

    def test_digest_dispatch_defaults_to_golden(self) -> None:
        self.assertEqual(MODULE.DEFAULT_REF, "golden-with-speed-insights")

    def test_dispatch_prefers_bounded_gh_cli(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"gh",\n                "workflow",\n                "run"', source)
        self.assertIn("timeout=20", source)


if __name__ == "__main__":
    unittest.main()
