from __future__ import annotations

import runpy
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PIPELINE = runpy.run_path(str(ROOT / "scripts" / "run-goalscorer-pipeline.py"), run_name="goalscorer_pipeline_test")
SCRAPER = runpy.run_path(str(ROOT / "scripts" / "odds-api-scrape-goalscorer.py"), run_name="goalscorer_scraper_test")


class GoalscorerSeasonAndBudgetTests(unittest.TestCase):
    def test_current_season_rolls_in_july(self) -> None:
        self.assertEqual(PIPELINE["_current_season_label"](date(2026, 6, 30)), "2025-2026")
        self.assertEqual(PIPELINE["_current_season_label"](date(2026, 7, 1)), "2026-2027")

    def test_header_only_csv_is_not_usable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.csv"
            path.write_text("a,b\n", encoding="utf-8")
            self.assertFalse(PIPELINE["_csv_has_data_rows"](path))
            path.write_text("a,b\n1,2\n", encoding="utf-8")
            self.assertTrue(PIPELINE["_csv_has_data_rows"](path))

    def test_http_budget_fails_closed_before_extra_request(self) -> None:
        budget = SCRAPER["HttpRequestBudget"](1)
        budget.used = 1
        with self.assertRaises(SCRAPER["RequestBudgetExhausted"]):
            budget.fetch_json("events", {})


if __name__ == "__main__":
    unittest.main()
