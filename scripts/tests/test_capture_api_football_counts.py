from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import UTC, date, datetime
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "capture_api_football_counts",
    SCRIPTS / "capture-api-football-counts.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def stat(name: str, value: object) -> dict:
    return {"type": name, "value": value}


def fixture() -> dict:
    return {
        "fixture": {
            "id": 123,
            "date": "2026-08-15T14:00:00+00:00",
            "status": {"short": "FT"},
            "referee": "Referee Name",
        },
        "teams": {
            "home": {"id": 10, "name": "Arsenal FC"},
            "away": {"id": 20, "name": "Chelsea FC"},
        },
    }


class CaptureApiFootballCountsTests(unittest.TestCase):
    def test_archives_uncaptured_fixture_and_deduplicates_rerun(self) -> None:
        calls: list[tuple[str, dict]] = []

        def request(path: str, params: dict) -> dict:
            calls.append((path, params))
            if path == "fixtures":
                return {"response": [fixture()] if params["league"] == 39 else []}
            return {
                "response": [
                    {"team": {"id": 20}, "statistics": [stat("Total Shots", 8), stat("Fouls", 12)]},
                    {"team": {"id": 10}, "statistics": [stat("Total Shots", 15), stat("Fouls", 9)]},
                ]
            }

        captured_at = datetime(2026, 8, 16, 1, tzinfo=UTC)
        rows, health = MODULE.collect_counts(
            [date(2026, 8, 15)],
            [],
            max_requests=90,
            request_fn=request,
            captured_at=captured_at,
        )
        self.assertEqual(health["new_rows"], 1)
        self.assertEqual(health["requests_used"], 6)
        self.assertEqual(rows[0]["home_shots"], 15)
        self.assertEqual(rows[0]["away_shots"], 8)
        self.assertEqual(rows[0]["home_fouls"], 9)
        self.assertEqual(rows[0]["home_team_source_name"], "Arsenal FC")

        calls.clear()
        rerun, rerun_health = MODULE.collect_counts(
            [date(2026, 8, 15)],
            rows,
            max_requests=90,
            request_fn=request,
            captured_at=captured_at,
        )
        self.assertEqual(len(rerun), 1)
        self.assertEqual(rerun_health["new_rows"], 0)
        self.assertEqual(rerun_health["requests_used"], 5)
        self.assertFalse(any(path == "fixtures/statistics" for path, _ in calls))

    def test_hard_request_limit_stops_before_statistics_call(self) -> None:
        def request(path: str, params: dict) -> dict:
            self.assertEqual(path, "fixtures")
            return {"response": [fixture()]}

        rows, health = MODULE.collect_counts(
            [date(2026, 8, 15)],
            [],
            max_requests=1,
            request_fn=request,
            captured_at=datetime(2026, 8, 16, 1, tzinfo=UTC),
        )
        self.assertEqual(rows, [])
        self.assertEqual(health["requests_used"], 1)
        self.assertTrue(health["truncated_by_request_budget"])

    def test_missing_provider_fields_remain_empty_not_zero(self) -> None:
        def request(path: str, params: dict) -> dict:
            if path == "fixtures":
                return {"response": [fixture()] if params["league"] == 39 else []}
            return {
                "response": [
                    {"team": {"id": 10}, "statistics": [stat("Corner Kicks", 4)]},
                    {"team": {"id": 20}, "statistics": [stat("Corner Kicks", 3)]},
                ]
            }

        rows, _ = MODULE.collect_counts(
            [date(2026, 8, 15)],
            [],
            max_requests=90,
            request_fn=request,
            captured_at=datetime(2026, 8, 16, 1, tzinfo=UTC),
        )
        self.assertIsNone(rows[0]["home_shots"])
        self.assertEqual(rows[0]["total_corners"], 7)


if __name__ == "__main__":
    unittest.main()
