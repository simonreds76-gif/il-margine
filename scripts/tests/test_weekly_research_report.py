from __future__ import annotations

import csv
import json
import os
import runpy
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = runpy.run_path(str(ROOT / "scripts" / "weekly-research-report.py"), run_name="weekly_research_report_test")


class WeeklyResearchReportTests(unittest.TestCase):
    @staticmethod
    def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fields = sorted({key for row in rows for key in row})
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_settled_ledger_summary_uses_real_stakes(self) -> None:
        rows = [
            {"settled": "1", "bet_outcome": "won", "stake": "0.5", "pnl_units": "1.0"},
            {"settled": "1", "bet_outcome": "lost", "stake": "1.0", "pnl_units": "-1.0"},
            {"settled": "", "bet_outcome": "", "stake": "1.0", "pnl_units": ""},
        ]
        summary = REPORT["settled_ledger_summary"](rows, stake_field="stake")
        self.assertEqual(summary["registered"], 3)
        self.assertEqual(summary["settled"], 2)
        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary["staked_units"], 1.5)
        self.assertEqual(summary["pnl_units"], 0.0)
        self.assertEqual(summary["roi_pct"], 0.0)

    def test_assist_summary_is_fail_closed(self) -> None:
        summary = REPORT["assist_value_research_summary"]()
        self.assertIn(summary["lane_status"], {"FROZEN_RESEARCH", "NOT_RUN"})
        self.assertIn("backtest_status", summary)
        self.assertIn("settlement_status", summary)
        self.assertIn("market_status", summary)
        self.assertIn("prospective", summary)

    def test_assist_workflow_has_a_fixed_weekly_api_ceiling(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "assist-value-shadow.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "10 7 * * 0,5,6"', workflow)
        self.assertIn("--max-events-per-league 10", workflow)
        self.assertIn("--max-odds-requests-per-league 1", workflow)
        self.assertIn("--disable-global-fallback", workflow)
        self.assertNotIn("SUPABASE_SERVICE_ROLE_KEY", workflow)
        self.assertNotIn("DATABASE_URL", workflow)

    def test_weekly_workflow_publishes_canonical_monitor_bundle(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "weekly-research-report.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "30 11 * * 2"', workflow)
        self.assertIn("contents: write", workflow)
        self.assertIn("group: golden-with-speed-insights-branch-writes", workflow)
        self.assertIn("Publish canonical weekly monitor bundle", workflow)
        self.assertIn("data/football-form/weekly-research-report.md", workflow)
        self.assertIn("data/team-shots/team-shots-live-snapshot.json", workflow)
        self.assertIn("data/corners-ou/corners-live-snapshot.json", workflow)
        self.assertIn("python scripts/corners-v4-g0-diagnostic.py", workflow)
        self.assertIn("data/corners-ou/corners-v4-g0-diagnostic.json", workflow)

    def test_corners_v4_g0_summary_reports_line_failures(self) -> None:
        summary = REPORT["corners_v4_g0_summary"](
            {
                "status": "RESEARCH_ONLY_NO_ROUTING_CHANGE",
                "samples": {"v3": 1000, "enriched": 800},
                "folds": [
                    {"season": "2025-2026", "variant": "v3_control", "mae": 2.72},
                    {"season": "2025-2026", "variant": "v4_lean_no_wide_block", "mae": 2.70},
                ],
                "market_g0": {
                    "variants": {
                        "v4_lean_no_wide_block": {
                            "g0_status": "FAIL",
                            "market_rows": 200,
                            "brier_delta": 0.004,
                            "per_line": {
                                "8.5": {"gate": "PASS"},
                                "9.5": {"gate": "FAIL"},
                                "12.5": {"status": "MISSING"},
                            },
                        }
                    }
                },
            }
        )
        self.assertEqual(summary["decision"], "FAIL")
        self.assertAlmostEqual(summary["mae_delta"], -0.02)
        self.assertEqual(summary["passed_lines"], 1)
        self.assertEqual(summary["available_lines"], 2)
        self.assertEqual(summary["failed_lines"], ["9.5", "12.5"])

    def test_weekly_payload_includes_automation_budget(self) -> None:
        payload = REPORT["build_payload"]()
        self.assertIn("automation_budget", payload)
        self.assertIn("corners_v4_g0", payload)
        self.assertIn("goalkeeper_saves_v1", payload)
        self.assertEqual(payload["goalkeeper_saves_v1"]["count_gate"], "PASS")
        self.assertEqual(
            payload["goalkeeper_saves_v1"]["market_status"],
            "OVER_ONLY_GOALKEEPER_SAVE_PRICES_RETURNED",
        )
        self.assertIn("capture_status", payload["goalkeeper_saves_v1"])
        self.assertFalse(payload["goalkeeper_saves_v1"]["sellable"])
        self.assertIn("tennis_venue_ace_factor_v1", payload)
        self.assertFalse(payload["tennis_venue_ace_factor_v1"]["automatic_promotion"])

    def test_goalscorer_weekly_evidence_is_decision_ready(self) -> None:
        goalscorer = REPORT["build_payload"]()["goalscorer_v2"]
        calibration = goalscorer["calibration"]
        self.assertGreater(calibration["n"], 0)
        self.assertIsNotNone(calibration["raw_brier"])
        self.assertIsNotNone(calibration["beta_brier"])
        self.assertIsNotNone(calibration["brier_delta"])
        self.assertIsNotNone(calibration["raw_ece"])
        self.assertIsNotNone(calibration["beta_ece"])
        self.assertEqual(len(goalscorer["extreme_gap_quarantine"]["by_league"]), 5)
        self.assertTrue(goalscorer["blockers"])

    def test_weekly_payload_includes_every_tennis_lane(self) -> None:
        payload = REPORT["build_payload"]()
        tennis = payload["tennis_model_evidence"]
        self.assertEqual(
            set(tennis["lanes"]),
            {"strict", "volume_200", "spread_v1", "grass_bo3", "clay_bo3", "cpi_speed", "challenger"},
        )
        self.assertIn("strict_gap_10_20_same_side", tennis["gap_replacements"])
        self.assertIn("volume200_gap_10_15_same_side", tennis["gap_replacements"])

    def test_telegram_report_contains_core_provisional_and_inactive_tennis(self) -> None:
        message = REPORT["telegram_text"](REPORT["build_payload"]())
        self.assertIn("Tennis prospective evidence source:", message)
        self.assertIn("Tennis lane summaries:", message)
        self.assertIn("Tennis Strict [CORE]", message)
        self.assertIn("ACTION BOARD", message)
        self.assertIn("EVIDENCE DETAIL", message)
        self.assertIn("Tennis Volume 200 [SHADOW / DO NOT BET]", message)
        self.assertIn("Strict gap 10-20pp [0.5u provisional]", message)
        self.assertIn("Volume gap 10-15pp [0.5u provisional]", message)
        self.assertIn("Inactive tennis research (not tips)", message)
        self.assertIn("Hard side-flip evidence [BROAD DIAGNOSTIC]", message)
        self.assertIn("GK Saves v1: count PASS", message)
        self.assertIn("Team Shots scan:", message)
        self.assertIn("Corners scan:", message)
        self.assertIn("Goalscorer beta vs raw", message)
        self.assertIn("Goalscorer gaps [ZERO-STAKE]", message)
        self.assertIn("weekly verdict", message)
        self.assertIn("| capture ", message)
        self.assertLessEqual(len(message), 4096)

    def test_tennis_only_telegram_report_is_complete_and_compact(self) -> None:
        message = REPORT["tennis_telegram_text"](REPORT["build_payload"]())
        self.assertIn("Il Margine weekly tennis evidence", message)
        self.assertIn("Prospective evidence source:", message)
        self.assertIn("Lane summaries:", message)
        self.assertIn("Strict [CORE]", message)
        self.assertIn("Volume 200 [SHADOW / DO NOT BET]", message)
        self.assertIn("Strict gap 10-20pp [0.5u provisional]", message)
        self.assertIn("Inactive research (not tips)", message)
        self.assertIn("Aces/DF vs Bet365", message)
        self.assertIn("Aces Over v4 [PRE_FIT]", message)
        self.assertIn("Venue ace v1 [SHADOW]", message)
        self.assertIn("NOT SELLABLE", message)
        self.assertIn("Most Aces A0 [outcome only]", message)
        self.assertIn("Most Aces Direct [prospective shadow]", message)
        self.assertIn("Direct vs A0 paired", message)
        self.assertIn("price evidence is separate below", message)
        self.assertIn("Most Aces Direct vs BetMGM", message)
        self.assertIn("Aces/DF promotion gate", message)
        self.assertIn("Hard side-flip evidence [BROAD DIAGNOSTIC]", message)
        self.assertLessEqual(len(message), 4096)

    def test_action_board_keeps_small_positive_cohorts_in_research(self) -> None:
        payload = REPORT["build_payload"]()
        evidence = payload["tennis_model_evidence"]
        evidence["gap_source_status"] = "OK"
        evidence["gap_replacements"]["strict_gap_10_20_same_side"]["performance"] = {
            "settled": 38,
            "roi_pct": 13.1,
            "avg_clv_pct": 0.86,
        }
        payload["tennis_props_shadow_decision"].update({"settled": 14, "roi_pct": 30.5})
        message = REPORT["telegram_text"](payload)
        self.assertIn("KEEP COLLECTING: Strict gap is positive but provisional", message)
        self.assertIn("WATCH ONLY: Aces/DF is promising but far too small", message)

    def test_missing_local_gap_evidence_is_not_rendered_as_zero_results(self) -> None:
        payload = REPORT["build_payload"]()
        payload["tennis_model_evidence"] = {
            "lanes": payload["tennis_model_evidence"]["lanes"],
            "gap_source_status": "SOURCE_MISSING",
            "gap_replacements": {},
            "side_flip_by_surface": {},
        }
        message = REPORT["tennis_telegram_text"](payload)
        self.assertIn("SOURCE_MISSING - local prospective evidence unavailable", message)
        self.assertNotIn("0/150 settled", message)

    def test_fresh_local_snapshot_replaces_stale_hosted_tennis_lanes(self) -> None:
        build_payload = REPORT["build_payload"]
        globals_map = build_payload.__globals__
        original_loader = globals_map["load_tennis_evidence_snapshot"]
        generated_at = REPORT["datetime"].now(REPORT["UTC"]).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        globals_map["load_tennis_evidence_snapshot"] = lambda: {
            "generated_at": generated_at,
            "_source": "test",
            "sections": {
                "tennis_model_evidence": {
                    "lanes": {"strict": {"settled": 1}},
                    "lane_source": {"status": "FRESH", "oldest_generated_at": "2026-08-04T09:00:00Z"},
                    "gap_source_status": "OK",
                    "side_flip_by_surface": {"Hard": {"settled": 52}},
                }
            },
        }
        try:
            payload = build_payload()
        finally:
            globals_map["load_tennis_evidence_snapshot"] = original_loader
        self.assertEqual(payload["tennis_model_evidence"]["lanes"]["strict"].get("settled"), 1)
        self.assertEqual(payload["tennis_model_evidence"]["lane_source"]["status"], "FRESH")
        self.assertEqual(payload["tennis_model_evidence"]["side_flip_by_surface"]["Hard"]["settled"], 52)

    def test_lane_source_detects_stale_core_lane(self) -> None:
        summary = REPORT["tennis_lane_source_summary"](
            {
                "strict": {"generated_at": "2026-04-25T00:00:00Z"},
                "volume_200": {"generated_at": "2026-08-04T00:00:00Z"},
                "spread_v1": {"generated_at": "2026-08-04T00:00:00Z"},
            }
        )
        self.assertEqual(summary["status"], "STALE")

    def test_most_aces_stale_json_falls_back_to_next_checkpoint(self) -> None:
        payload = REPORT["build_payload"]()
        payload["tennis_most_aces_forecast"] = {
            "models": {},
            "paired_comparison": {"paired_events": 0},
        }
        message = REPORT["tennis_telegram_text"](payload)
        self.assertIn("Direct vs A0 paired: n=0/200", message)
        self.assertIn("BUILDING (next 50)", message)
        self.assertNotIn("BUILDING (review due)", message)

    def test_most_aces_price_summary_is_model_specific(self) -> None:
        rows = [
            {
                "model": "most_aces_direct_1x2_v1",
                "settlement_status": "settled",
                "bet_eligible": "yes",
                "pnl": "1.5",
                "clv_pct": "2.0",
            },
            {
                "model": "v3_aces_gaussian_copula_nb2",
                "settlement_status": "settled",
                "bet_eligible": "yes",
                "pnl": "-1.0",
                "clv_pct": "-0.5",
            },
        ]
        summary = REPORT["most_aces_price_summary"](rows)
        direct = summary["most_aces_direct_1x2_v1"]
        self.assertEqual(direct["eligible_settled"], 1)
        self.assertEqual(direct["pnl_units"], 1.5)
        self.assertEqual(direct["mean_clv_pct"], 2.0)

    def test_tennis_props_decision_fails_closed_on_thin_sample(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            signals = root / "signals.csv"
            health = root / "health.json"
            self.write_csv(
                signals,
                [
                    {
                        "settlement_status": "settled",
                        "result": "win",
                        "pnl": "1.5",
                        "fair_odds": "2.0",
                        "clv_pct": "2.0",
                        "market": "aces",
                        "tournament": "Wimbledon",
                    },
                    {
                        "settlement_status": "pending",
                        "result": "",
                        "pnl": "",
                        "fair_odds": "2.2",
                        "clv_pct": "-1.0",
                        "market": "double_faults",
                        "tournament": "Washington",
                    },
                ],
            )
            health.write_text(
                json.dumps(
                    {
                        "state": "SHADOW_EVIDENCE_READY",
                        "structural_error": False,
                        "line_rows": 20,
                        "matched_rows": 10,
                        "two_way_rows": 0,
                        "over_only_rows": 20,
                    }
                ),
                encoding="utf-8",
            )
            summary = REPORT["tennis_props_shadow_decision"](signals, health)

        self.assertEqual(summary["status"], "COLLECTING_EVIDENCE")
        self.assertFalse(summary["automatic_promotion"])
        self.assertEqual(summary["settled"], 1)
        self.assertEqual(summary["pending_unknown"], 1)
        self.assertEqual(summary["pnl_units"], 1.5)
        self.assertEqual(summary["calibration"]["rows"], 1)

    def test_tennis_props_pending_rows_distinguish_due_from_future(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            signals = root / "signals.csv"
            health = root / "health.json"
            now = datetime.now(UTC)
            self.write_csv(
                signals,
                [
                    {
                        "settlement_status": "pending",
                        "match_start_utc": (now - timedelta(days=1)).isoformat(),
                        "market": "aces",
                    },
                    {
                        "settlement_status": "pending",
                        "match_start_utc": (now + timedelta(days=1)).isoformat(),
                        "market": "double_faults",
                    },
                    {
                        "settlement_status": "pending",
                        "match_start_utc": "",
                        "market": "aces",
                    },
                ],
            )
            health.write_text(json.dumps({"structural_error": False}), encoding="utf-8")
            summary = REPORT["tennis_props_shadow_decision"](signals, health)
            rendered = REPORT["tennis_props_shadow_decision_report"](summary)

        self.assertEqual(summary["pending"], 3)
        self.assertEqual(summary["pending_due"], 1)
        self.assertEqual(summary["pending_future"], 1)
        self.assertEqual(summary["pending_unknown"], 1)
        self.assertIn("3 pending (1 due, 1 future, 1 unknown)", rendered)
        self.assertIn("settled_sample", summary["failed_gates"])
        self.assertIn("price_integrity", summary["failed_gates"])

    def test_tennis_props_decision_only_requests_review_after_every_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            signals = root / "signals.csv"
            health = root / "health.json"
            rows: list[dict[str, str]] = []
            for index in range(300):
                won = index % 2 == 0
                rows.append(
                    {
                        "settlement_status": "settled",
                        "result": "win" if won else "loss",
                        "pnl": "1.10" if won else "-1.0",
                        "fair_odds": "2.0",
                        "clv_pct": "2.0" if index < 180 else "0.0",
                        "market": "aces" if index % 3 else "double_faults",
                        "tournament": "Wimbledon" if index < 150 else "US Open",
                    }
                )
            self.write_csv(signals, rows)
            health.write_text(
                json.dumps(
                    {
                        "state": "BETTABLE_READY",
                        "structural_error": False,
                        "line_rows": 500,
                        "matched_rows": 450,
                        "two_way_rows": 200,
                        "over_only_rows": 300,
                    }
                ),
                encoding="utf-8",
            )
            summary = REPORT["tennis_props_shadow_decision"](signals, health)

        self.assertEqual(summary["status"], "REVIEW_FOR_PROMOTION")
        self.assertFalse(summary["automatic_promotion"])
        self.assertEqual(summary["failed_gates"], [])
        self.assertEqual(summary["settled_slams"], ["US Open", "Wimbledon"])

    def test_local_weekly_task_sends_one_consolidated_tennis_message(self) -> None:
        script = (ROOT / "scripts" / "oncourt-weekly.ps1").read_text(encoding="utf-8")
        self.assertIn('"scripts\\tennis-props-v3-weekly-report.py", "--no-telegram"', script)
        self.assertEqual(script.count("--tennis-only-telegram"), 1)

    def test_telegram_uses_github_relay_when_local_secrets_are_absent(self) -> None:
        post = REPORT["post_telegram"]
        globals_map = post.__globals__
        original_relay = globals_map["dispatch_telegram_relay"]
        original_token = os.environ.pop("OPS_ALERT_TELEGRAM_BOT_TOKEN", None)
        original_chat = os.environ.pop("OPS_ALERT_TELEGRAM_CHAT_ID", None)
        relayed: list[str] = []
        globals_map["dispatch_telegram_relay"] = relayed.append
        try:
            self.assertTrue(post("weekly evidence"))
        finally:
            globals_map["dispatch_telegram_relay"] = original_relay
            if original_token is not None:
                os.environ["OPS_ALERT_TELEGRAM_BOT_TOKEN"] = original_token
            if original_chat is not None:
                os.environ["OPS_ALERT_TELEGRAM_CHAT_ID"] = original_chat
        self.assertEqual(relayed, ["weekly evidence"])


if __name__ == "__main__":
    unittest.main()
