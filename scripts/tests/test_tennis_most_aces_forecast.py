from __future__ import annotations

from datetime import UTC, datetime
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_forecast():
    path = SCRIPTS / "tennis-most-aces-forecast.py"
    spec = importlib.util.spec_from_file_location("tennis_most_aces_forecast_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


FORECAST = load_forecast()


class MostAcesForecastTests(unittest.TestCase):
    def board(self) -> dict[str, str]:
        return {
            "date": "2026-07-29",
            "tour": "ATP",
            "tournament": "Washington",
            "round": "R16",
            "surface": "Hard",
            "player1": "Player One",
            "player2": "Player Two",
            "player1_mean": "8.0",
            "player2_mean": "5.0",
            "rho": "0.22",
            "p_player1": "0.65",
            "p_draw": "0.10",
            "p_player2": "0.25",
            "fair_player1": "1.538",
            "fair_draw": "10.0",
            "fair_player2": "4.0",
            "model": "test",
        }

    def test_registration_is_append_only_and_deduplicated(self) -> None:
        ledger: list[dict[str, str]] = []
        self.assertEqual(FORECAST.register([self.board()], ledger), 1)
        self.assertEqual(FORECAST.register([self.board()], ledger), 0)
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0]["predicted_outcome"], "P1")
        self.assertIn("NO_ROI", ledger[0]["notes"])

    def test_settlement_scores_actual_ace_outcome_without_prices(self) -> None:
        ledger: list[dict[str, str]] = []
        FORECAST.register([self.board()], ledger)
        result = {
            "winner_name": "Player One",
            "loser_name": "Player Two",
            "tourney_name": "Washington",
            "tourney_date": "20260729",
            "score": "6-4 6-4",
            "w_ace": "10",
            "l_ace": "4",
            "_settlement_source": "oncourt",
        }
        key = ("ATP", 2026, FORECAST.pair_key("Player One", "Player Two"))
        with (
            patch.object(FORECAST.SETTLE, "load_sackmann_index", return_value={}),
            patch.object(FORECAST.SETTLE, "load_oncourt_index", return_value={key: [result]}),
            patch.object(FORECAST, "datetime") as mocked_datetime,
        ):
            mocked_datetime.now.return_value = datetime(2026, 7, 30, tzinfo=UTC)
            mocked_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            self.assertEqual(FORECAST.settle(ledger, Path("."), Path(".")), 1)
        self.assertEqual(ledger[0]["settlement_status"], "settled")
        self.assertEqual(ledger[0]["actual_outcome"], "P1")
        self.assertEqual(ledger[0]["prediction_correct"], "yes")
        self.assertGreater(float(ledger[0]["model_brier"]), 0.0)

    def test_report_never_claims_profitability(self) -> None:
        ledger: list[dict[str, str]] = []
        FORECAST.register([self.board()], ledger)
        report = FORECAST.report_payload(ledger)
        self.assertFalse(report["can_claim_profitability"])
        self.assertEqual(report["status"], "EVIDENCE_BUILDING")


if __name__ == "__main__":
    unittest.main()
