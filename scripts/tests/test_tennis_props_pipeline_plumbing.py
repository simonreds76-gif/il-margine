from __future__ import annotations

import argparse
import csv
import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_script(name: str, module_name: str):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


COMPARE = load_script("tennis-props-compare-bet365.py", "props_compare_plumbing")
TRACKER = load_script("tennis-props-shadow-tracker.py", "props_tracker_plumbing")
DAILY = load_script("run-tennis-props-daily.py", "props_daily_plumbing")
SYNC = load_script("sync-tennis-props-hosted-captures.py", "props_sync_plumbing")
HEALTH = load_script("tennis-props-pipeline-health.py", "props_health_plumbing")
MODEL_REPORT = load_script("tennis-props-model-report.py", "props_model_report_plumbing")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["date"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class OneSidedComparisonTests(unittest.TestCase):
    def row(self, odds: str, line: str, value: str = "12.0") -> dict[str, str]:
        now = datetime.now(timezone.utc)
        return {
            "date": now.date().isoformat(),
            "tour": "ATP",
            "tournament": "Washington",
            "player": "Player One",
            "opponent": "Player Two",
            "market": "aces",
            "scope": "player",
            "line": line,
            "over_odds": odds,
            "under_odds": "",
            "price_pair_status": "over_only",
            "matched_board": "yes",
            "line_quality": "one_sided",
            "projection_mean": "6.1",
            "confidence": "MED",
            "combined_surface_svpt_sample": "1200",
            "capture_ts": now.isoformat(),
            "match_start_utc": (now + timedelta(hours=8)).isoformat(),
            "value_over_pct": value,
            "value_under_pct": "",
            "edge_over_novig_pct": "",
            "edge_under_novig_pct": "",
            "notes": "",
        }

    def test_selects_one_representative_over_only_ladder_row(self) -> None:
        rows = [self.row("1.55", "4.5"), self.row("2.00", "6.5"), self.row("3.00", "8.5")]
        args = argparse.Namespace(min_value=0.10, min_novig_edge=0.05, max_model_market_gap=0.12)
        COMPARE.apply_decision_gates(rows, args, datetime.now(timezone.utc))

        selected = [row for row in rows if row["best_available_line"] == "true"]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["over_odds"], "2.00")
        self.assertEqual(selected[0]["decision_mode"], "one_sided_over_shadow")
        self.assertEqual(selected[0]["trackable_shadow"], "true")
        self.assertEqual(selected[0]["bettable"], "false")

    def test_one_sided_shadow_rejects_low_edge(self) -> None:
        rows = [self.row("2.00", "6.5", value="4.0")]
        args = argparse.Namespace(min_value=0.10, min_novig_edge=0.05, max_model_market_gap=0.12)
        COMPARE.apply_decision_gates(rows, args, datetime.now(timezone.utc))
        self.assertEqual(rows[0]["trackable_shadow"], "false")
        self.assertIn("EDGE_BELOW_GATE", rows[0]["shadow_block_reasons"])

    def test_each_player_gets_an_independent_ladder_selection(self) -> None:
        player_one = self.row("2.00", "6.5")
        player_two = self.row("2.10", "5.5")
        player_two["player"] = "Player Two"
        player_two["opponent"] = "Player One"
        rows = [player_one, player_two]
        COMPARE.select_main_lines(rows)
        self.assertEqual(
            sum(row["best_available_line"] == "true" for row in rows),
            2,
        )

    def test_legacy_away_team_total_is_reoriented_as_player_prop(self) -> None:
        row = {
            "market": "match_aces",
            "raw_market_name": "Aces Team Total Away",
            "player": "Home Player",
            "opponent": "Away Player",
        }
        normalized = COMPARE.normalize_legacy_team_total_row(row)
        self.assertEqual(normalized["market"], "aces")
        self.assertEqual(normalized["player"], "Away Player")
        self.assertEqual(normalized["opponent"], "Home Player")

    def test_player_only_fallback_requires_one_missing_name(self) -> None:
        self.assertFalse(COMPARE.can_fallback_player_only("Player One", "Player Two"))
        self.assertTrue(COMPARE.can_fallback_player_only("Player One", ""))
        self.assertTrue(COMPARE.can_fallback_player_only("", "Player Two"))


class ShadowTrackerTests(unittest.TestCase):
    @staticmethod
    def args() -> argparse.Namespace:
        return argparse.Namespace(
            min_value=8.0,
            allow_watch=False,
            allow_medium=True,
            allow_notes=False,
            bookmaker="Bet365",
        )

    def test_player_signal_requires_explicit_trackable_shadow_state(self) -> None:
        row = {
            "date": "2026-07-29",
            "tour": "ATP",
            "tournament": "Washington",
            "scope": "player",
            "player": "Player One",
            "opponent": "Player Two",
            "market": "aces",
            "line": "6.5",
            "confidence": "MED",
            "matched_board": "yes",
            "trackable_shadow": "true",
            "decision_mode": "one_sided_over_shadow",
            "shadow_side": "OVER",
            "value_over_pct": "12.0",
            "over_odds": "2.0",
            "price_pair_status": "over_only",
        }
        args = argparse.Namespace(
            min_value=8.0,
            allow_watch=False,
            allow_medium=True,
            allow_notes=False,
            bookmaker="Bet365",
        )
        signal = TRACKER.build_signal(row, Path("comparison.csv"), args)
        self.assertIsNotNone(signal)
        self.assertEqual(signal["side"], "OVER")
        self.assertEqual(signal["decision_mode"], "one_sided_over_shadow")

        row["trackable_shadow"] = "false"
        self.assertIsNone(TRACKER.build_signal(row, Path("comparison.csv"), args))

    def test_two_way_player_shadow_tracks_registered_under_side(self) -> None:
        row = {
            "date": "2026-08-26",
            "tour": "WTA",
            "tournament": "US Open",
            "scope": "player",
            "player": "Player One",
            "opponent": "Player Two",
            "market": "aces",
            "line": "3.5",
            "confidence": "MED",
            "matched_board": "yes",
            "trackable_shadow": "true",
            "decision_mode": "two_way_player_shadow",
            "shadow_side": "UNDER",
            "value_over_pct": "-10.0",
            "value_under_pct": "14.0",
            "over_odds": "1.70",
            "under_odds": "2.02",
            "price_pair_status": "two_way",
            "bookmaker": "BetsBK",
        }
        args = argparse.Namespace(
            min_value=8.0,
            allow_watch=False,
            allow_medium=True,
            allow_notes=False,
            bookmaker="Bet365",
        )
        signal = TRACKER.build_signal(row, Path("comparison.csv"), args)
        self.assertIsNotNone(signal)
        self.assertEqual(signal["side"], "UNDER")
        self.assertEqual(signal["bookmaker"], "BetsBK")
        self.assertEqual(signal["decision_mode"], "two_way_player_shadow")

    def test_match_total_ids_include_line_and_side(self) -> None:
        row = {
            "date": "2026-09-02",
            "tour": "ATP",
            "tournament": "US Open",
            "scope": "match_total",
            "player": "Player One",
            "opponent": "Player Two",
            "market": "match_breaks",
            "line": "6.5",
        }
        first = TRACKER.signal_id(row, "OVER")
        row["line"] = "7.5"
        second = TRACKER.signal_id(row, "OVER")
        third = TRACKER.signal_id(row, "UNDER")
        self.assertNotEqual(first, second)
        self.assertNotEqual(second, third)
        self.assertTrue(first.endswith("|6.5|OVER"))

    def test_break_decision_key_ignores_later_line_and_side(self) -> None:
        row = {
            "date": "2026-09-03",
            "tour": "WTA",
            "player": "Madison Keys",
            "opponent": "Anna Bondar",
            "market": "player_breaks",
            "line": "3.5",
            "side": "UNDER",
        }
        first = TRACKER.prospective_decision_key(row)
        row.update({"line": "4.5", "side": "OVER"})
        self.assertEqual(first, TRACKER.prospective_decision_key(row))

    def test_later_opposite_break_decision_is_voided_as_reprice(self) -> None:
        base = {
            "date": "2026-09-03",
            "tour": "WTA",
            "player": "Madison Keys",
            "opponent": "Anna Bondar",
            "market": "player_breaks",
            "line": "3.5",
            "decision_mode": "breaks_single_source_shadow",
            "settlement_status": "pending",
            "over_odds": "1.5333",
            "under_odds": "2.3750",
        }
        original = {
            **base,
            "signal_id": "under-entry",
            "side": "UNDER",
            "capture_ts": "2026-09-02T14:20:05Z",
        }
        duplicate = {
            **base,
            "signal_id": "over-reprice",
            "side": "OVER",
            "over_odds": "1.9091",
            "under_odds": "1.8000",
            "capture_ts": "2026-09-03T09:45:54Z",
        }

        self.assertEqual(TRACKER.reconcile_duplicate_break_decisions([original, duplicate]), 1)
        self.assertEqual(original["latest_over_odds"], "1.9091")
        self.assertIn("market_favourite_flip", original["market_move_status"])
        self.assertEqual(duplicate["settlement_status"], "void")
        self.assertEqual(duplicate["pnl"], "0.000")
        self.assertEqual(duplicate["settlement_note"], "duplicate_reprice_of:under-entry")

    def test_history_refresh_records_line_move_without_new_signal(self) -> None:
        original = {
            "date": "2026-09-03",
            "tour": "ATP",
            "player": "Botic Van De Zandschulp",
            "opponent": "Alex De Minaur",
            "market": "player_breaks",
            "line": "2.5",
            "side": "OVER",
            "decision_mode": "breaks_single_source_shadow",
            "settlement_status": "pending",
            "capture_ts": "2026-09-03T09:45:54Z",
            "over_odds": "1.8000",
            "under_odds": "1.9091",
        }
        history = [{
            **original,
            "line": "3.5",
            "capture_ts": "2026-09-03T10:32:22Z",
            "over_odds": "2.1000",
            "under_odds": "1.6667",
        }]

        self.assertEqual(TRACKER.refresh_break_market_movements([original], history), 1)
        self.assertEqual(original["latest_line"], "3.5")
        self.assertEqual(original["line_move"], "1.000")
        self.assertIn("line_up", original["market_move_status"])
        self.assertIn("market_favourite_flip", original["market_move_status"])

    def test_break_calibration_row_is_recorded_without_a_betting_side(self) -> None:
        row = {
            "date": "2026-09-02",
            "tour": "ATP",
            "tournament": "US Open",
            "scope": "match_total",
            "player": "Player One",
            "opponent": "Player Two",
            "market": "match_breaks",
            "line": "6.5",
            "confidence": "LOW",
            "matched_board": "no",
            "calibration_eligible": "true",
            "decision_mode": "breaks_calibration_unfiltered",
            "value_over_pct": "14.0",
            "value_under_pct": "-12.0",
            "over_odds": "1.90",
            "under_odds": "1.90",
            "price_pair_status": "two_way",
            "gate_version": "breaks_v1_p0",
        }
        signal = TRACKER.build_signal(row, Path("comparison.csv"), self.args())
        self.assertIsNotNone(signal)
        self.assertEqual(signal["side"], "")
        self.assertEqual(signal["selected_odds"], "")
        self.assertEqual(signal["observed_side"], "OVER")
        self.assertEqual(signal["observed_odds"], "1.900")
        self.assertTrue(signal["signal_id"].endswith("|6.5|CALIBRATION"))

    def test_bet365_single_source_break_row_is_recorded_for_prospective_roi(self) -> None:
        row = {
            "date": "2026-09-02",
            "tour": "ATP",
            "tournament": "US Open",
            "scope": "match_total",
            "player": "Player One",
            "opponent": "Player Two",
            "market": "match_breaks",
            "line": "6.5",
            "confidence": "HIGH",
            "matched_board": "yes",
            "calibration_eligible": "true",
            "trackable_shadow": "true",
            "shadow_side": "OVER",
            "decision_mode": "breaks_single_source_shadow",
            "value_over_pct": "4.0",
            "value_under_pct": "-7.0",
            "over_odds": "1.90",
            "under_odds": "1.90",
            "bookmaker": "Bet365",
        }
        signal = TRACKER.build_signal(row, Path("comparison.csv"), self.args())
        self.assertIsNotNone(signal)
        self.assertEqual(signal["side"], "OVER")
        self.assertEqual(signal["decision_mode"], "breaks_single_source_shadow")
        self.assertEqual(signal["selected_odds"], "1.900")

    def test_legacy_break_signal_is_reclassified_without_losing_observed_price(self) -> None:
        row = {
            "signal_id": "legacy",
            "date": "2026-09-02",
            "tour": "ATP",
            "tournament": "US Open",
            "scope": "match_total",
            "player": "Player One",
            "opponent": "Player Two",
            "market": "match_breaks",
            "line": "6.5",
            "side": "OVER",
            "selected_odds": "1.833",
            "value_pct": "11.09",
            "decision_mode": "breaks_shadow",
            "closing_snapshot_count": "1",
            "clv_pct": "0.000",
        }
        migrated = TRACKER.normalize_existing_row(row)
        self.assertEqual(migrated["decision_mode"], "breaks_calibration_unfiltered")
        self.assertEqual(migrated["side"], "")
        self.assertEqual(migrated["observed_side"], "OVER")
        self.assertEqual(migrated["observed_odds"], "1.833")
        self.assertEqual(migrated["clv_pct"], "")

    def test_missing_exact_comparison_never_falls_back_to_stale_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            old_props = TRACKER.PROPS_DIR
            old_argv = sys.argv
            TRACKER.PROPS_DIR = base
            stale = base / "comparison-2026-07-28.csv"
            write_csv(stale, [{"date": "2026-07-28", "trackable_shadow": "true"}])
            signals = base / "signals.csv"
            performance = base / "performance.txt"
            sys.argv = [
                "tennis-props-shadow-tracker.py",
                "--date",
                "2026-07-29",
                "--signals",
                str(signals),
                "--performance",
                str(performance),
            ]
            try:
                self.assertEqual(TRACKER.main(), 0)
                self.assertFalse(signals.exists())
                self.assertFalse(performance.exists())
            finally:
                TRACKER.PROPS_DIR = old_props
                sys.argv = old_argv


class DailyMarketSelectionTests(unittest.TestCase):
    def test_uses_recent_capture_when_it_contains_target_date_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_props = DAILY.PROPS_DIR
            DAILY.PROPS_DIR = Path(tmp)
            try:
                prior = DAILY.lines_file("2026-07-28")
                write_csv(prior, [{"date": "2026-07-29", "capture_ts": "2026-07-28T15:30:00Z"}])
                selected = DAILY.select_market_file("2026-07-29")
                self.assertEqual(selected, DAILY.combined_lines_file("2026-07-28"))
                self.assertTrue(selected.exists())
            finally:
                DAILY.PROPS_DIR = old_props

    def test_combines_bet365_and_betsbk_snapshots_without_source_collision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_props = DAILY.PROPS_DIR
            DAILY.PROPS_DIR = Path(tmp)
            try:
                write_csv(
                    DAILY.lines_file("2026-08-26"),
                    [{"date": "2026-08-26", "event_id": "odds-1", "bookmaker": "Bet365"}],
                )
                write_csv(
                    DAILY.betsbk_lines_file("2026-08-26"),
                    [{"date": "2026-08-26", "event_id": "sbk-1", "bookmaker": "BetsBK"}],
                )
                selected = DAILY.select_market_file("2026-08-26")
                self.assertEqual(selected, DAILY.combined_lines_file("2026-08-26"))
                with selected.open("r", encoding="utf-8", newline="") as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual({row["bookmaker"] for row in rows}, {"Bet365", "BetsBK"})
            finally:
                DAILY.PROPS_DIR = old_props

    def test_does_not_reuse_capture_without_target_date_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_props = DAILY.PROPS_DIR
            DAILY.PROPS_DIR = Path(tmp)
            try:
                prior = DAILY.lines_file("2026-07-28")
                write_csv(prior, [{"date": "2026-07-28", "capture_ts": "2026-07-28T15:30:00Z"}])
                self.assertIsNone(DAILY.select_market_file("2026-07-29"))
            finally:
                DAILY.PROPS_DIR = old_props

    def test_fast_comparison_skips_derived_ace_boards(self) -> None:
        old_select = DAILY.select_market_file
        old_refresh = DAILY.refresh_derived_ace_boards
        old_compare = DAILY.run_comparison
        old_tracking = DAILY.run_shadow_tracking
        old_health = DAILY.write_pipeline_health
        marker = Path("market.csv")
        DAILY.select_market_file = lambda _as_of: marker
        DAILY.refresh_derived_ace_boards = lambda _as_of: self.fail("derived boards should be skipped")
        DAILY.run_comparison = lambda _as_of, market: market == marker
        DAILY.run_shadow_tracking = lambda _as_of: None
        DAILY.write_pipeline_health = lambda *_args, **_kwargs: 0
        try:
            result = DAILY.run_comparison_only(
                "2026-07-29",
                skip_sync=True,
                lookback_days=3,
                skip_derived_boards=True,
            )
            self.assertEqual(result, 0)
        finally:
            DAILY.select_market_file = old_select
            DAILY.refresh_derived_ace_boards = old_refresh
            DAILY.run_comparison = old_compare
            DAILY.run_shadow_tracking = old_tracking
            DAILY.write_pipeline_health = old_health

    def test_failed_comparison_removes_same_date_stale_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_props = DAILY.PROPS_DIR
            old_run = DAILY.run
            DAILY.PROPS_DIR = Path(tmp)
            comparison = DAILY.PROPS_DIR / "comparison-2026-07-29.csv"
            write_csv(comparison, [{"date": "2026-07-29", "matched_board": "yes"}])
            DAILY.run = lambda *args, **kwargs: 1
            try:
                self.assertFalse(
                    DAILY.run_comparison(
                        "2026-07-29",
                        DAILY.PROPS_DIR / "lines.csv",
                    )
                )
                self.assertFalse(comparison.exists())
            finally:
                DAILY.PROPS_DIR = old_props
                DAILY.run = old_run

    def test_am_task_runs_lightweight_hosted_comparison(self) -> None:
        am_script = (SCRIPTS / "oncourt-am-refresh.ps1").read_text(encoding="utf-8")
        self.assertIn("run-tennis-props-daily.py", am_script)
        self.assertIn("--capture-only", am_script)
        self.assertIn("--comparison-only", am_script)
        self.assertIn("--skip-derived-boards", am_script)
        self.assertLess(am_script.index("--capture-only"), am_script.index("build-tennis-props-board.py"))
        self.assertIn("--skip-hosted-sync", am_script)
        self.assertIn('"--require-ready", "--new-only"', am_script)
        self.assertIn('"scripts\\tennis-evidence-snapshot.py", "--supabase"', am_script)
        self.assertIn('"--days-ahead", "3"', am_script)
        self.assertIn('"tennis props hosted-price comparison" -TimeoutSeconds 420', am_script)

    def test_close_task_recaptures_only_open_break_watch_fixtures(self) -> None:
        close_script = (SCRIPTS / "pinnacle-close-capture.ps1").read_text(encoding="utf-8")
        self.assertIn("tennis-props-scrape-bet365-direct.py", close_script)
        self.assertIn("--tracked-only --max-events 20", close_script)
        self.assertIn("tennis-props-shadow-tracker.py --movement-history", close_script)
        self.assertNotIn("--comparison-only", close_script)

    def test_full_pipeline_passes_schedule_horizon_to_projection_board(self) -> None:
        daily_script = (SCRIPTS / "run-tennis-props-daily.py").read_text(encoding="utf-8")
        board_call = daily_script[daily_script.index('str(ROOT / "scripts" / "build-tennis-props-board.py")') :]
        board_call = board_call[: board_call.index('"Build tennis props projection board"')]
        self.assertIn('"--days-ahead"', board_call)
        self.assertIn("str(args.days_ahead)", board_call)

    def test_core_props_tracking_precedes_slow_ace_v4_research(self) -> None:
        daily_script = (SCRIPTS / "run-tennis-props-daily.py").read_text(encoding="utf-8")
        self.assertLess(
            daily_script.index("Append tennis props shadow signals"),
            daily_script.index("Register and score ATP ace-over v4 challenger"),
        )

    def test_am_timeout_kills_complete_process_tree(self) -> None:
        am_script = (SCRIPTS / "oncourt-am-refresh.ps1").read_text(encoding="utf-8")
        self.assertIn('Start-Process -FilePath "taskkill.exe"', am_script)
        self.assertIn('"/T"', am_script)

    def test_nightly_task_publishes_compact_tennis_evidence_after_settlement(self) -> None:
        nightly = (SCRIPTS / "oncourt-daily.ps1").read_text(encoding="utf-8")
        self.assertLess(
            nightly.index("oncourt-settle-nightly.ps1"),
            nightly.index("tennis-evidence-snapshot.py"),
        )
        self.assertIn('"scripts\\tennis-evidence-snapshot.py", "--supabase"', nightly)


class ComparisonInputFilterTests(unittest.TestCase):
    def test_excludes_only_event_rows_before_as_of(self) -> None:
        rows = [
            {"date": "2026-07-30", "market": "aces"},
            {"date": "2026-07-31", "market": "aces"},
            {"date": "2026-08-01", "market": "double_faults"},
            {"date": "", "market": "aces"},
        ]
        kept, excluded = COMPARE.filter_line_rows_for_as_of(rows, "2026-07-31")
        self.assertEqual(excluded, 1)
        self.assertEqual([row["date"] for row in kept], ["2026-07-31", "2026-08-01", ""])

    def test_market_filter_supports_v3_aces_comparison(self) -> None:
        rows = [
            {"market": "aces"},
            {"market": "match_aces"},
            {"market": "double_faults"},
        ]
        kept = COMPARE.filter_line_rows_by_market(rows, "aces,match_aces")
        self.assertEqual([row["market"] for row in kept], ["aces", "match_aces"])


class HostedSyncTests(unittest.TestCase):
    def test_history_merge_is_append_only_and_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "history.csv"
            write_csv(target, [{"event_id": "1", "capture_ts": "a"}])
            remote = b"event_id,capture_ts\r\n1,a\r\n2,b\r\n"
            self.assertEqual(SYNC.merge_history(target, remote), 1)
            self.assertEqual(len(HEALTH.read_csv(target)), 2)
            self.assertEqual(SYNC.merge_history(target, remote), 0)
            self.assertEqual(len(HEALTH.read_csv(target)), 2)


class PipelineHealthTests(unittest.TestCase):
    def test_capture_without_comparison_is_structural_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            lines = base / "lines.csv"
            comparison = base / "comparison.csv"
            signals = base / "signals.csv"
            write_csv(lines, [{"date": "2026-07-29", "capture_ts": "2026-07-29T08:00:00Z"}])
            payload = HEALTH.build_health(
                "2026-07-29",
                lines,
                comparison,
                signals,
                now=datetime(2026, 7, 29, 9, tzinfo=timezone.utc),
            )
            self.assertEqual(payload["state"], "COMPARISON_MISSING")
            self.assertTrue(payload["structural_error"])

    def test_one_sided_only_comparison_is_structural_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            lines = base / "lines.csv"
            comparison = base / "comparison.csv"
            signals = base / "signals.csv"
            write_csv(
                lines,
                [
                    {"date": "2026-07-28", "capture_ts": "2026-07-29T08:00:00Z"},
                    {"date": "2026-07-29", "capture_ts": "2026-07-29T08:00:00Z"},
                ],
            )
            write_csv(
                comparison,
                [
                    {
                        "date": "2026-07-29",
                        "matched_board": "yes",
                        "price_pair_status": "over_only",
                        "trackable_shadow": "true",
                        "bettable": "false",
                    }
                ],
            )
            payload = HEALTH.build_health(
                "2026-07-29",
                lines,
                comparison,
                signals,
                now=datetime(2026, 7, 29, 9, tzinfo=timezone.utc),
            )
            self.assertEqual(payload["state"], "TWO_WAY_PRICES_MISSING")
            self.assertTrue(payload["structural_error"])
            self.assertEqual(payload["past_event_line_rows"], 1)
            self.assertEqual(payload["eligible_line_rows"], 1)

    def test_service_break_health_distinguishes_feed_from_edge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            lines = base / "lines.csv"
            comparison = base / "comparison.csv"
            signals = base / "signals.csv"
            write_csv(lines, [{"date": "2026-09-02", "market": "match_breaks", "capture_ts": "2026-09-02T08:00:00Z"}])
            write_csv(comparison, [{
                "date": "2026-09-02",
                "market": "match_breaks",
                "matched_board": "yes",
                "price_pair_status": "two_way",
                "trackable_shadow": "true",
                "bettable": "false",
                "decision_mode": "breaks_prospective_shadow",
            }])
            payload = HEALTH.build_health(
                "2026-09-02",
                lines,
                comparison,
                signals,
                now=datetime(2026, 9, 2, 9, tzinfo=timezone.utc),
            )
            self.assertEqual(payload["break_state"], "STRICT_PROSPECTIVE_READY")
            self.assertEqual(payload["break_line_rows"], 1)
            self.assertEqual(payload["break_matched_rows"], 1)
            self.assertEqual(payload["break_trackable_rows"], 1)
            self.assertEqual(payload["break_strict_rows"], 1)

    def test_service_break_health_identifies_bet365_only_prospective_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            lines = base / "lines.csv"
            comparison = base / "comparison.csv"
            signals = base / "signals.csv"
            write_csv(lines, [{"date": "2026-09-02", "market": "match_breaks", "capture_ts": "2026-09-02T08:00:00Z"}])
            write_csv(comparison, [{
                "date": "2026-09-02",
                "market": "match_breaks",
                "matched_board": "yes",
                "price_pair_status": "two_way",
                "trackable_shadow": "true",
                "bettable": "false",
                "decision_mode": "breaks_single_source_shadow",
            }])
            payload = HEALTH.build_health(
                "2026-09-02",
                lines,
                comparison,
                signals,
                now=datetime(2026, 9, 2, 9, tzinfo=timezone.utc),
            )
            self.assertEqual(payload["break_state"], "BET365_PROSPECTIVE_READY")
            self.assertEqual(payload["break_single_source_rows"], 1)
            self.assertEqual(payload["break_strict_rows"], 0)

    def test_service_break_health_reports_calibration_only_separately(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            lines = base / "lines.csv"
            comparison = base / "comparison.csv"
            signals = base / "signals.csv"
            write_csv(lines, [{"date": "2026-09-02", "market": "match_breaks", "capture_ts": "2026-09-02T08:00:00Z"}])
            write_csv(comparison, [{
                "date": "2026-09-02",
                "market": "match_breaks",
                "matched_board": "yes",
                "price_pair_status": "two_way",
                "trackable_shadow": "false",
                "calibration_eligible": "true",
                "decision_mode": "breaks_calibration_unfiltered",
                "shadow_block_reasons": "PRICE_SOURCE_UNVERIFIED",
            }])
            payload = HEALTH.build_health(
                "2026-09-02",
                lines,
                comparison,
                signals,
                now=datetime(2026, 9, 2, 9, tzinfo=timezone.utc),
            )
            self.assertEqual(payload["break_state"], "CALIBRATION_ONLY")
            self.assertEqual(payload["break_calibration_rows"], 1)
            self.assertEqual(payload["break_trackable_rows"], 0)

    def test_windows_watchdog_evaluates_pipeline_health_artifact(self) -> None:
        watchdog = (SCRIPTS / "tennis-health-check.ps1").read_text(encoding="utf-8")
        self.assertIn("function Get-ArtifactHealth", watchdog)
        self.assertIn("pipeline-health.json", watchdog)
        self.assertIn("$artifactConfigs | ForEach-Object { Get-ArtifactHealth", watchdog)


class ModelReportTests(unittest.TestCase):
    def test_break_calibration_is_excluded_from_shadow_roi(self) -> None:
        rows = [
            {
                "decision_mode": "breaks_calibration_unfiltered",
                "settlement_status": "settled",
                "pnl": "8.0",
            },
            {
                "decision_mode": "two_way_player_shadow",
                "settlement_status": "settled",
                "pnl": "1.0",
            },
        ]
        stats = MODEL_REPORT.shadow_stats(rows)
        self.assertEqual(stats["shadow_signals"], "1")
        self.assertEqual(stats["shadow_settled"], "1")
        self.assertEqual(stats["shadow_pnl_units"], "1.00")
        self.assertEqual(stats["break_calibration_rows"], "1")
        self.assertEqual(stats["break_calibration_settled"], "1")


if __name__ == "__main__":
    unittest.main()
