from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT / "db" / "migrations" / "20260717_0001_run_status_active_cadence.sql"
).read_text(encoding="utf-8")


class RunStatusActiveCadenceTests(unittest.TestCase):
    def test_retired_automatic_pipelines_are_not_expected(self) -> None:
        for pipeline in ("goalscorer-settle", "team-props", "fetch-results-snapshot"):
            with self.subTest(pipeline=pipeline):
                self.assertNotIn(f"('{pipeline}'::text", MIGRATION)

    def test_active_heartbeat_pipelines_remain_expected(self) -> None:
        for pipeline in (
            "pinnacle-capture-history",
            "oncourt-daily",
            "oncourt-am-refresh",
            "oncourt-weekly",
        ):
            with self.subTest(pipeline=pipeline):
                self.assertIn(f"('{pipeline}'::text", MIGRATION)


if __name__ == "__main__":
    unittest.main()
