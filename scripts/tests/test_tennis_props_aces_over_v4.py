from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from tennis_props_ladder import canonical_quote, fit_market_ladder


def load_v4():
    path = SCRIPTS / "tennis-props-aces-over-v4.py"
    spec = importlib.util.spec_from_file_location("tennis_props_aces_over_v4_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


V4 = load_v4()


class LadderTests(unittest.TestCase):
    def test_vukic_ladder_is_accepted_and_canonical_quote_is_near_even(self) -> None:
        points = [(2.5, 1.10), (4.5, 1.36), (9.5, 3.40), (14.5, 11.0), (19.5, 26.0)]
        fitted = fit_market_ladder(points, alpha=V4.LADDER_REFERENCE_ALPHA)
        self.assertTrue(fitted.accepted, fitted)
        self.assertGreater(fitted.mu_mkt or 0.0, 0.0)
        self.assertLess(fitted.shape_rmse or 1.0, 0.25)
        self.assertEqual(fitted.dropped_ceiling, 1)
        self.assertEqual(canonical_quote(points), (4.5, 1.36))

    def test_ladder_rejects_insufficient_points(self) -> None:
        fitted = fit_market_ladder([(4.5, 1.30), (9.5, 3.0)], alpha=0.18)
        self.assertFalse(fitted.accepted)
        self.assertEqual(fitted.reject_reason, "INSUFFICIENT_POINTS")

    def test_ladder_rejects_non_monotone_prices(self) -> None:
        fitted = fit_market_ladder([(4.5, 1.50), (9.5, 1.40), (14.5, 4.0)], alpha=0.18)
        self.assertFalse(fitted.accepted)
        self.assertEqual(fitted.reject_reason, "NON_MONOTONE_LADDER")


class RegistrationTests(unittest.TestCase):
    def test_prefit_registration_keeps_v4_equal_to_v3(self) -> None:
        candidate = {
            "row": {
                "date": "2026-07-30",
                "tour": "ATP",
                "tournament": "Washington",
                "surface": "Hard",
                "player": "Player One",
                "opponent": "Player Two",
                "market": "aces",
                "event_id": "123",
                "match_start_utc": "2026-07-30T18:00:00Z",
                "bookmaker": "Bet365",
                "projection_mean": "8.25",
            },
            "source": Path("comparison.csv"),
            "fit": fit_market_ladder(
                [(2.5, 1.06), (4.5, 1.24), (9.5, 2.60), (14.5, 8.0)],
                alpha=0.1763648838,
            ),
            "line": 9.5,
            "odds": 2.60,
            "capture": "2026-07-30T10:00:00Z",
        }
        gate = {
            "deployment_safe_aces": {
                "ATP": {"candidate_alpha": 0.1763648838},
            }
        }
        from datetime import UTC, datetime

        row = V4.build_registration(
            candidate,
            ledger=[],
            gate=gate,
            sha256="model-hash",
            now=datetime(2026, 7, 30, 10, tzinfo=UTC),
        )
        self.assertEqual(row["phase"], "PRE_FIT")
        self.assertEqual(row["w_applied"], "0.000000")
        self.assertEqual(row["mu_v4"], row["mu_v3"])
        self.assertEqual(row["frozen_sha256"], V4.frozen_digest(row))

    def test_integrity_detects_frozen_mutation(self) -> None:
        row = {field: "" for field in V4.FIELDNAMES}
        row["observation_id"] = "one"
        row["mu_v3"] = "5.0"
        row["frozen_sha256"] = V4.frozen_digest(row)
        V4.assert_integrity([row])
        row["mu_v3"] = "6.0"
        with self.assertRaises(RuntimeError):
            V4.assert_integrity([row])

    def test_future_row_cannot_settle_from_old_same_pair_result(self) -> None:
        from datetime import UTC, datetime
        from unittest.mock import patch

        row = {field: "" for field in V4.FIELDNAMES}
        row.update(
            {
                "observation_id": "future",
                "date": "2026-07-30",
                "tour": "ATP",
                "player": "Player One",
                "opponent": "Player Two",
                "market": "aces",
                "match_start_utc": "2026-07-30T18:00:00Z",
                "settlement_status": "pending",
            }
        )
        with (
            patch.object(V4.SETTLE, "load_oncourt_index", return_value={}),
            patch.object(V4.SETTLE, "load_sackmann_index", return_value={}),
        ):
            settled = V4.settle_rows(
                [row],
                sackmann_dir=Path("."),
                oncourt_dir=Path("."),
                now_dt=datetime(2026, 7, 30, 10, tzinfo=UTC),
            )
        self.assertEqual(settled, 0)
        self.assertEqual(row["settlement_status"], "pending")
        self.assertEqual(row["settlement_note"], "match_not_started")


if __name__ == "__main__":
    unittest.main()
