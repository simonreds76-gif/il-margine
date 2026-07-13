from __future__ import annotations

import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT = SCRIPTS / "reconcile-team-shots-sources.py"
SPEC = importlib.util.spec_from_file_location("team_shots_source_reconciliation", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class TeamShotsSourceReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.candidate = root / "candidate.csv"
        self.reference = root / "reference.csv"
        self.candidate_row = {
            "date": "2025-08-16",
            "league": "epl",
            "season": "2025-2026",
            "home_team": "Manchester United",
            "away_team": "Arsenal",
            "home_shots": 13,
            "away_shots": 11,
            "home_sot": 5,
            "away_sot": 4,
            "home_corners": 6,
            "away_corners": 5,
            "source": "football-data+understat-xg",
        }
        self.reference_row = {
            "Date": "16/08/2025",
            "league": "epl",
            "season": "2025-2026",
            "HomeTeam": "Man United",
            "AwayTeam": "Arsenal",
            "HS": 13,
            "AS": 11,
            "HST": 5,
            "AST": 4,
            "HC": 6,
            "AC": 5,
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_rows(self) -> None:
        write_csv(self.candidate, list(self.candidate_row), [self.candidate_row])
        write_csv(self.reference, list(self.reference_row), [self.reference_row])

    def test_equivalent_sources_pass(self) -> None:
        self.write_rows()
        report = MODULE.reconcile(self.candidate, self.reference)
        self.assertTrue(report["passes"])
        self.assertEqual(report["matched_rows"], 1)
        self.assertEqual(report["field_checks"]["home_shots"]["mismatches"], 0)

    def test_count_delta_fails_and_is_recorded(self) -> None:
        self.candidate_row["home_shots"] = 15
        self.write_rows()
        report = MODULE.reconcile(self.candidate, self.reference)
        self.assertFalse(report["passes"])
        self.assertEqual(report["field_checks"]["home_shots"]["mismatches"], 1)
        self.assertEqual(report["field_checks"]["home_shots"]["mean_absolute_delta"], 2.0)


if __name__ == "__main__":
    unittest.main()
