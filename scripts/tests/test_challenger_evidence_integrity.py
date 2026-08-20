from __future__ import annotations

import csv
import importlib.util
import sys
import tempfile
import unittest
from datetime import UTC, date, datetime
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


promote = load_script("promote_challenger_nearmiss_shadow_test", "promote-challenger-nearmiss-shadow.py")
clv = load_script("audit_strict_clv_test", "audit-strict-clv.py")
scorer = load_script("score_tennis_spread_history_test", "score-tennis-spread-history.py")
policy = load_script("strict_policy_report_test", "strict-policy-report.py")


class ChallengerStakePolicyTests(unittest.TestCase):
    def test_challenger_profile_is_always_zero_stake(self) -> None:
        self.assertEqual(
            policy.apply_profile_stake_policy("challenger_ml_shadow", 1.0, 100.0, "flat_match"),
            (0.0, 0.0, "prospective_evidence_no_stake"),
        )
        self.assertEqual(
            policy.apply_profile_stake_policy("strict", 1.0, 100.0, "flat_match"),
            (1.0, 100.0, "flat_match"),
        )


class ChallengerEntryOddsTests(unittest.TestCase):
    def test_snapshot_lookup_is_date_aware_and_oriented(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fields = [
                "player1_name",
                "player2_name",
                "odds1",
                "odds2",
                "pinnacle_margin",
                "league_name",
            ]
            for day, odds1 in (("2026-08-01", "1.50"), ("2026-08-08", "1.80")):
                with (root / f"pinnacle-odds-{day}.csv").open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields)
                    writer.writeheader()
                    writer.writerow(
                        {
                            "player1_name": "Player A",
                            "player2_name": "Player B",
                            "odds1": odds1,
                            "odds2": "2.50",
                            "pinnacle_margin": "3.0",
                            "league_name": "ATP Challenger Test",
                        }
                    )
            index = promote.load_pinnacle_odds(root)
            row = {
                "date": "2026-08-08",
                "player1": "Player B",
                "player2": "Player A",
                "side": "P1",
            }
            promoted = promote.promote_row(row, index)
            self.assertEqual(promoted["pin_odds1"], "2.50")
            self.assertEqual(promoted["pin_odds2"], "1.80")

    def test_existing_publication_price_is_immutable(self) -> None:
        existing = [{field: "" for field in promote.FIELDNAMES}]
        existing[0].update(
            {
                "date": "2026-08-08",
                "player1": "A",
                "player2": "B",
                "side": "P1",
                "signal_profile": "challenger_ml_nearmiss",
                "pin_odds1": "2.10",
                "pin_odds2": "1.80",
                "odds_capture_status": "matched_local_pinnacle",
            }
        )
        refreshed = [dict(existing[0], pin_odds1="2.50", pin_odds2="1.60")]
        merged = promote.merge_existing(existing, refreshed)
        self.assertEqual(merged[0]["pin_odds1"], "2.10")
        self.assertEqual(merged[0]["pin_odds2"], "1.80")


class ChallengerCloseIntegrityTests(unittest.TestCase):
    @staticmethod
    def history(captured: str, kickoff: str = "2026-08-08T15:00:00Z"):
        return clv.HistoryRow(
            capture_date="2026-08-08",
            captured_at=captured,
            captured_ts=clv.parse_timestamp(captured),
            kickoff_iso=kickoff,
            kickoff_ts=clv.parse_timestamp(kickoff),
            capture_mode="close",
            source="local_csv",
            league="Challenger",
            player1_name="Alice Smith",
            player2_name="Bob Jones",
            odds1=1.9,
            odds2=2.0,
            spread_line=-1.5,
            spread_odds1=1.9,
            spread_odds2=1.9,
        )

    def test_verified_close_rejects_post_start_and_stale_rows(self) -> None:
        valid = self.history("2026-08-08T14:30:00Z")
        post = self.history("2026-08-08T15:01:00Z")
        stale = self.history("2026-08-08T01:00:00Z")
        lookup = clv.build_history_lookup([valid, post, stale])
        signal = {
            "date": "2026-08-08",
            "time_utc": "12:00:00",
            "match_date": "2026-08-08",
            "player1": "Alice Smith",
            "player2": "Bob Jones",
        }
        matched, _, reason = clv.match_signal_to_history(
            signal,
            lookup,
            require_verified_kickoff=True,
            max_close_lag_minutes=720,
        )
        self.assertIs(matched, valid)
        self.assertEqual(reason, "history")

    def test_verified_close_rejects_missing_kickoff(self) -> None:
        row = self.history("2026-08-08T14:30:00Z", "")
        lookup = clv.build_history_lookup([row])
        signal = {
            "date": "2026-08-08",
            "time_utc": "12:00:00",
            "match_date": "2026-08-08",
            "player1": "Alice Smith",
            "player2": "Bob Jones",
        }
        matched, _, reason = clv.match_signal_to_history(
            signal,
            lookup,
            require_verified_kickoff=True,
        )
        self.assertIsNone(matched)
        self.assertEqual(reason, "history_kickoff_unverified")


class ChallengerMlScorerTests(unittest.TestCase):
    def test_ml_scoring_is_outcome_independent_and_uses_true_close(self) -> None:
        kickoff = datetime(2026, 8, 8, 15, 0, tzinfo=UTC)
        game = scorer.Game(2, 1, 99, 4, "6-4 6-4", date(2026, 8, 8))
        tour = scorer.Tour(99, "Test Challenger", 4, 1)

        def snapshot(captured: datetime, mode: str, odds1: float, odds2: float):
            return scorer.Snapshot(
                lane="Challenger",
                league_name="ATP Challenger Test",
                player1_name="Player A",
                player2_name="Player B",
                player1_id=1,
                player2_id=2,
                captured_at=captured,
                capture_date=date(2026, 8, 8),
                capture_mode=mode,
                match_date=date(2026, 8, 8),
                kickoff=kickoff,
                ml_odds1=odds1,
                ml_odds2=odds2,
                spread_line=1.5,
                spread_odds1=1.9,
                spread_odds2=1.9,
                source_file="capture.csv",
                resolve_method1="exact",
                resolve_method2="exact",
            )

        publication = snapshot(datetime(2026, 8, 8, 12, 0, tzinfo=UTC), "daily", 2.20, 1.70)
        close = snapshot(datetime(2026, 8, 8, 14, 45, tzinfo=UTC), "close", 2.00, 1.80)
        row, reason = scorer.score_ml_match(
            "Challenger",
            game,
            [(publication, "exact"), (close, "exact")],
            {99: tour},
        )
        self.assertEqual(reason, "")
        assert row is not None
        self.assertEqual(row["p1_win_binary"], 0)
        self.assertEqual(row["p1_flat_pnl"], -1.0)
        self.assertEqual(row["close_ml_odds1"], 2.0)
        self.assertEqual(row["clv_eligible"], "1")


if __name__ == "__main__":
    unittest.main()
