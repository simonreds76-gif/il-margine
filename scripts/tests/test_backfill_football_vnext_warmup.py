from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "backfill_football_vnext_warmup_test",
    SCRIPTS / "backfill-football-vnext-warmup.py",
)
assert SPEC is not None and SPEC.loader is not None
BACKFILL = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BACKFILL
SPEC.loader.exec_module(BACKFILL)


class PublisherStub:
    @staticmethod
    def warmup_tracking_signals(rows):
        by_fixture = {}
        for row in rows:
            current = by_fixture.get(row["match_id"])
            if current is None or float(row["edge"]) > float(current["edge"]):
                by_fixture[row["match_id"]] = row
        return list(by_fixture.values())


class BackfillFootballVnextWarmupTests(unittest.TestCase):
    def test_first_qualifying_scan_is_frozen_without_hindsight(self) -> None:
        rows = [
            {"published_at_utc": "2026-08-20T10:00:00Z", "model": "corners_v3", "match_id": "fx-1", "pick_id": "first", "edge": "0.04"},
            {"published_at_utc": "2026-08-20T10:00:00Z", "model": "corners_v3", "match_id": "fx-1", "pick_id": "same-scan-strongest", "edge": "0.06"},
            {"published_at_utc": "2026-08-21T10:00:00Z", "model": "corners_v3", "match_id": "fx-1", "pick_id": "later-hindsight", "edge": "0.20"},
        ]

        recovered = BACKFILL.first_qualifying_rows(PublisherStub, rows)

        self.assertEqual([row["pick_id"] for row in recovered], ["same-scan-strongest"])


if __name__ == "__main__":
    unittest.main()
