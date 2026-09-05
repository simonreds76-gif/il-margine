from __future__ import annotations

import csv
import json
import runpy
import sys
import tempfile
import unittest
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
EXP = runpy.run_path(str(ROOT / "scripts/tennis-props-fresh-data-challenger.py"))
CONFIG = json.loads((ROOT / "config/tennis-props-fresh-data-challenger-v1.json").read_text())


class FreshDataChallengerTests(unittest.TestCase):
    def row(self, **kwargs):
        return dict({"signal_id": "old-id", "event_id": "123", "bookmaker": "Bet365", "tour": "ATP",
                     "tournament": "US Open", "date": "2026-09-04", "player": "Alice Player", "opponent": "Bob Player",
                     "scope": "player", "market": "aces", "line": "4.5", "side": "OVER", "selected_odds": "2.1",
                     "projection_mean": "5", "fair_odds": "2.4", "distribution": "negative_binomial",
                     "settlement_status": "settled", "result": "win", "actual": "6",
                     "capture_ts": "2026-09-02T18:00:00Z", "logged_at_utc": "2026-09-03T09:00:00Z",
                     "match_start_utc": "2026-09-04T16:00:00Z"}, **kwargs)

    def history(self):
        return [{"player_id": "1", "played": date(2026, 8, 1) + timedelta(days=i), "surface": "Hard",
                 "aces_valid": True, "double_faults_valid": True, "sp": 100, "rp": 100,
                 "ace": 10, "allowed": 8, "df": 4, "second": 40} for i in range(6)]

    def test_cutoff_is_earliest_capture_entry_and_fixture_day(self):
        cutoff, reason = EXP["temporal_cutoff"](self.row(), date(2026, 9, 4))
        self.assertEqual((cutoff, reason), (date(2026, 9, 2), "ok"))
        self.assertEqual(EXP["temporal_cutoff"](self.row(), date(2026, 9, 1))[1], "registration_after_source_fixture_day")
        self.assertEqual(EXP["temporal_cutoff"](self.row(logged_at_utc="2026-09-04T16:00:00Z"))[1], "poststart_capture_or_registration")
        self.assertEqual(EXP["temporal_cutoff"](self.row(capture_ts=""))[1], "missing_or_invalid_timestamp")
        self.assertEqual(EXP["temporal_cutoff"](self.row(capture_ts="2026-09-03T11:00:00Z"))[1], "capture_after_registration")

    def test_future_same_day_and_other_surface_cannot_change_past_features(self):
        cutoff = date(2026, 9, 2)
        history = self.history()
        before = EXP["rate_trend"](history, history, "Hard", cutoff, "aces", CONFIG)
        poison = dict(history[0], ace=100, allowed=100)
        extended = history + [dict(poison, played=cutoff), dict(poison, played=cutoff + timedelta(days=1)),
                              dict(poison, played=cutoff - timedelta(days=1), surface="Clay")]
        after = EXP["rate_trend"](extended, extended, "Hard", cutoff, "aces", CONFIG)
        self.assertEqual(before, after)
        self.assertLess(before[1]["player_recent"]["latest"], cutoff.isoformat())

    def test_constant_rates_produce_no_change_and_same_primary_filter(self):
        for market in CONFIG["markets"]:
            multiplier, _, reason = EXP["rate_trend"](self.history(), self.history(), "Hard", date(2026, 9, 2), market, CONFIG)
            self.assertEqual(reason, "ok")
            self.assertAlmostEqual(multiplier, 1)
            row = self.row(market=market)
            baseline = EXP["prediction"](5, row, CONFIG)
            challenger = EXP["prediction"](5 * multiplier, row, CONFIG)
            self.assertEqual(baseline, challenger)
            self.assertEqual(EXP["score_probability"](baseline["p_conditional"], 1), EXP["score_probability"](challenger["p_conditional"], 1))
            self.assertEqual(baseline["ev"] >= .03, challenger["ev"] >= .03)

    def test_df_second_serve_prior_and_fixed_blend(self):
        history = self.history()
        history += [dict(r, played=r["played"] - timedelta(days=150), df=1, second=20) for r in self.history()]
        multiplier, support, reason = EXP["rate_trend"](history, [], "Hard", date(2026, 9, 2), "double_faults", CONFIG)
        self.assertEqual(reason, "ok")
        baseline_df = 30 / 360
        recent_df = (24 + 200 * baseline_df) / (240 + 200)
        baseline_share = 360 / 1200
        recent_share = (240 + 500 * baseline_share) / (600 + 500)
        expected = min(1.2, max(.8, .5 + .5 * (recent_df / baseline_df) * (recent_share / baseline_share)))
        self.assertAlmostEqual(multiplier, expected)
        self.assertEqual(support["player_baseline"]["matches"], 12)

    def test_insufficient_support_is_excluded(self):
        multiplier, _, reason = EXP["rate_trend"](self.history()[:1], [], "Hard", date(2026, 9, 2), "double_faults", CONFIG)
        self.assertIsNone(multiplier)
        self.assertEqual(reason, "insufficient_player_baseline_support")

    def test_whole_fixtures_and_dates_are_disjoint_between_periods(self):
        records = [{"fixture_id": str(i), "fixture_date": f"2026-09-0{1 + i // 2}"} for i in range(6)]
        phases, boundary = EXP["assign_phases"](records + records[:2] * 10, 2 / 3)
        self.assertEqual(boundary, "2026-09-03")
        self.assertEqual(phases, {"0": "development", "1": "development", "2": "development", "3": "development", "4": "evaluation", "5": "evaluation"})

    def test_push_has_no_binary_score_and_zero_profit(self):
        self.assertEqual(EXP["outcomes"](4, 4, "OVER", 2.5), (0, None))
        self.assertEqual(EXP["score_probability"](.6, None), {"brier": None, "log_loss": None})
        self.assertEqual(EXP["outcomes"](5, 4.5, "OVER", 2.5), (1.5, 1))
        self.assertEqual(EXP["outcomes"](5, 4.5, "UNDER", 2.5), (-1, 0))

    def test_paired_strategy_delta_keeps_skipped_common_fixtures(self):
        values = [{"fixture_id": "a", "delta": 2}, {"fixture_id": "a", "delta": 0}, {"fixture_id": "b", "delta": 0}]
        result = EXP["paired_interval"](values, lambda r: r["delta"], dict(CONFIG, bootstrap_replicates=100))
        self.assertEqual(result["fixtures"], 2)
        self.assertEqual(result["equal_fixture_mean_delta"], .5)

    def test_source_fixture_requires_exact_round_or_unique_candidate(self):
        def game(round_id, actual):
            return {"key": ("1", "2", "99", round_id), "played": date(2026, 9, 4), "tournament": "US Open",
                    "stat": {"w_ace": actual}}
        games = [game("4", "6"), game("5", "10")]
        self.assertEqual(EXP["match_fixture"](self.row(), games, "1", "2")[1], "ambiguous_source_fixture")
        self.assertEqual(EXP["match_fixture"](self.row(round_id="4"), games, "1", "2")[1], "ok")
        self.assertEqual(EXP["match_fixture"](self.row(round_id="5"), games, "1", "2")[1], "source_actual_disagrees_with_ledger")

    def test_source_loader_does_not_cross_rounds_and_quarantines_conflicts(self):
        def write(path, records):
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(records[0]))
                writer.writeheader()
                writer.writerows(records)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            write(source / "courts.csv", [{"id": "1", "name": "Hard"}])
            write(source / "players_atp.csv", [{"id": "1", "name": "Player, Alice"}, {"id": "2", "name": "Bob Player"}])
            write(source / "tours_atp.csv", [{"id": "99", "name": "US Open", "rank": "4", "court_id": "1"}])
            games = [{"winner_id": "1", "loser_id": "2", "tour_id": "99", "round_id": str(i),
                      "result": "6-4 6-4", "date": "2026-09-04"} for i in (4, 5)]
            write(source / "games_atp.csv", games)
            stats = []
            for game in games:
                stat = {k: game[k] for k in ("winner_id", "loser_id", "tour_id", "round_id")}
                for prefix in ("w", "l"):
                    stat.update({f"{prefix}_svpt": "100", f"{prefix}_fs": "60", f"{prefix}_w2sof": "40",
                                 f"{prefix}_ace": "6" if game["round_id"] == "4" else "10", f"{prefix}_df": "2"})
                stats.append(stat)
            write(source / "stat_atp.csv", stats)
            history, fixtures, _, _ = EXP["load_source"](source, [self.row()], CONFIG)
            self.assertEqual([r["ace"] for r in history["ATP"]["1"]], [6, 10])
            self.assertEqual(len(fixtures["ATP"][("1", "2")]), 2)
            write(source / "stat_atp.csv", stats + [dict(stats[0], w_ace="99")])
            history, fixtures, _, quality = EXP["load_source"](source, [self.row()], CONFIG)
            self.assertEqual([r["ace"] for r in history["ATP"]["1"]], [10])
            self.assertEqual(quality["conflicting_source_key"], 1)
            self.assertEqual(fixtures["ATP"][("1", "2")][0]["key"][3], "5")

    def test_physical_contract_aliases_are_one_research_opportunity(self):
        original = self.row()
        alias = self.row(event_id="provider-alias", model_version="different-label", line="4.50")
        key = EXP["physical_contract_key"]
        self.assertEqual(key(original, "ATP|1|2|99|4", "1"), key(alias, "ATP|1|2|99|4", "1"))
        for changed in (self.row(line="5.5"), self.row(side="UNDER"), self.row(bookmaker="BetsBK")):
            self.assertNotEqual(key(original, "ATP|1|2|99|4", "1"), key(changed, "ATP|1|2|99|4", "1"))

    def test_evaluate_no_trend_changes_no_primary_scores_despite_rounded_entry_probability(self):
        row = self.row()
        baseline = EXP["prediction"](5, row, CONFIG)
        row["fair_odds"] = str(1 / (baseline["p_conditional"] + .005))
        alias = dict(row, signal_id="later-id", event_id="provider-alias", model_version="v2",
                     logged_at_utc="2026-09-03T10:00:00Z")
        game = {"key": ("1", "2", "99", "4"), "fixture_id": "ATP|1|2|99|4", "played": date(2026, 9, 4),
                "surface": "Hard", "tournament": "US Open", "stat": {"w_ace": "6"}}
        source = ({"ATP": {"1": self.history(), "2": self.history()}},
                  {"ATP": {("1", "2"): [game]}}, {"ATP": {"alice player": "1", "bob player": "2"}}, {})
        with patch.dict(EXP["evaluate"].__globals__, load_source=lambda *_: source):
            evaluated, excluded, report = EXP["evaluate"]([alias, row], Path("unused"), dict(CONFIG, bootstrap_replicates=100))
        self.assertEqual(len(evaluated), 1)
        self.assertEqual(excluded[0]["reason"], "duplicate_physical_contract_after_source_join")
        record = evaluated[0]
        self.assertEqual(record["signal_id"], "old-id")
        self.assertEqual(record["incumbent"], record["challenger"])
        self.assertNotEqual(record["incumbent"]["p_conditional"], record["recorded_incumbent"]["p_conditional"])
        self.assertAlmostEqual(report["reconstruction_probability_audit"]["max_absolute_delta"], .005)

    def test_changed_input_fails_before_publishing_experiment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            signal = root / "signals.csv"
            signal.write_text("signal_id\noriginal\n")
            config = root / "config.json"
            config.write_text(json.dumps(CONFIG))
            for name in ("courts.csv", *(f"{kind}_{tour}.csv" for tour in ("atp", "wta") for kind in ("players", "tours", "games", "stat"))):
                (root / name).write_text("id\n")
            out = root / "experiment"
            def mutate(*_):
                signal.write_text("signal_id\nchanged\n")
                return [], [], {}
            with patch.object(sys, "argv", ["experiment", "--signals", str(signal), "--config", str(config),
                                            "--oncourt-dir", str(root), "--output-prefix", str(out)]):
                with patch.dict(EXP["main"].__globals__, evaluate=mutate):
                    with self.assertRaisesRegex(RuntimeError, "input changed"):
                        EXP["main"]()
            self.assertFalse(out.with_suffix(".json").exists())


if __name__ == "__main__":
    unittest.main()
