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
SETTLE = load_script("tennis-props-settle-shadow.py", "props_settle_plumbing")


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


class ShadowSettlementPriceTests(unittest.TestCase):
    def test_player_prop_closing_price_cannot_cross_players(self) -> None:
        signal = {
            "event_id": "73087108",
            "date": "2026-07-29",
            "tour": "ATP",
            "bookmaker": "Bet365",
            "player": "Aleksandar Vukic",
            "opponent": "Lorenzo Musetti",
            "market": "aces",
            "line": "9.5",
            "side": "OVER",
            "selected_odds": "3.40",
            "logged_at_utc": "2026-07-29T08:10:00Z",
            "match_start_utc": "2026-07-29T17:00:00Z",
        }
        history = [
            {
                **signal,
                "capture_ts": "2026-07-29T08:00:00Z",
                "over_odds": "3.40",
            },
            {
                **signal,
                "capture_ts": "2026-07-29T08:30:00Z",
                "over_odds": "3.30",
            },
            {
                **signal,
                "player": "Lorenzo Musetti",
                "opponent": "Aleksandar Vukic",
                "capture_ts": "2026-07-29T09:00:00Z",
                "over_odds": "6.00",
            },
        ]

        by_event: dict[tuple[object, ...], list[dict[str, str]]] = {}
        by_pair: dict[tuple[object, ...], list[dict[str, str]]] = {}
        for row in history:
            by_event.setdefault(SETTLE.history_key(row), []).append(row)
            by_pair.setdefault(SETTLE.history_key(row, fallback=True), []).append(row)

        self.assertTrue(SETTLE.enrich_closing_price(signal, by_event, by_pair))
        self.assertEqual(signal["closing_odds"], "3.300")
        self.assertGreater(float(signal["clv_pct"]), 0.0)
        self.assertEqual(signal["closing_snapshot_count"], "1")

    def test_registration_capture_is_not_a_close(self) -> None:
        signal = {
            "event_id": "1", "date": "2026-07-29", "tour": "ATP",
            "bookmaker": "Bet365", "player": "Player One", "opponent": "Player Two",
            "market": "aces", "line": "9.5", "side": "OVER",
            "selected_odds": "3.40", "logged_at_utc": "2026-07-29T08:10:00Z",
            "match_start_utc": "2026-07-29T17:00:00Z",
        }
        capture = {**signal, "capture_ts": "2026-07-29T08:00:00Z", "over_odds": "3.40"}
        by_event = {SETTLE.history_key(capture): [capture]}
        by_pair = {SETTLE.history_key(capture, fallback=True): [capture]}
        self.assertFalse(SETTLE.enrich_closing_price(signal, by_event, by_pair))
        self.assertEqual(signal["closing_odds"], "")
        self.assertEqual(signal["clv_pct"], "")


class DailyMarketSelectionTests(unittest.TestCase):
    def test_uses_recent_capture_when_it_contains_target_date_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_props = DAILY.PROPS_DIR
            DAILY.PROPS_DIR = Path(tmp)
            try:
                prior = DAILY.lines_file("2026-07-28")
                write_csv(prior, [{"date": "2026-07-29", "capture_ts": "2026-07-28T15:30:00Z"}])
                selected = DAILY.select_market_file("2026-07-29")
                self.assertEqual(selected, prior)
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

    def test_windows_watchdog_evaluates_pipeline_health_artifact(self) -> None:
        watchdog = (SCRIPTS / "tennis-health-check.ps1").read_text(encoding="utf-8")
        self.assertIn("function Get-ArtifactHealth", watchdog)
        self.assertIn("pipeline-health.json", watchdog)
        self.assertIn("$artifactConfigs | ForEach-Object { Get-ArtifactHealth", watchdog)


if __name__ == "__main__":
    unittest.main()
