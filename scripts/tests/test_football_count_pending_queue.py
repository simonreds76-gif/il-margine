import csv
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("count_pending_fetch", ROOT / "scripts/fetch-results-snapshot.py")
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)


class CountPendingQueueTests(unittest.TestCase):
    def write(self, root, name, rows):
        path = root / "data/football-form" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        fields = ["pick_id", "result", "league", "home_team", "away_team", "kickoff_utc"]
        with path.open("w", newline="", encoding="utf8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_hourly_and_opponent_only_picks_enter_daily_queue(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(F, "ROOT", Path(tmp)):
            root = Path(tmp)
            self.write(root, F.COUNT_LEDGER_NAMES[0], [dict(pick_id="old", result="lost")])
            self.write(root, F.COUNT_SIGNAL_NAMES[0], [dict(pick_id="old", result=""), dict(pick_id="hourly", result="")])
            self.write(root, F.COUNT_LEDGER_NAMES[2], [dict(pick_id="opponent", result="pending")])
            rows = F.load_pending_rows(["data/football-form/" + F.COUNT_LEDGER_NAMES[0]])
            self.assertEqual({r["pick_id"] for r in rows}, {"hourly", "opponent"})

    def test_duplicate_ledger_paths_and_same_fixture_do_not_duplicate_requests(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(F, "ROOT", Path(tmp)):
            root = Path(tmp)
            fixture = dict(result="pending", league="epl", home_team="Arsenal", away_team="Chelsea", kickoff_utc="2026-09-12T14:00:00Z")
            self.write(root, F.COUNT_LEDGER_NAMES[0], [dict(fixture, pick_id="v4")])
            self.write(root, F.COUNT_LEDGER_NAMES[2], [dict(fixture, pick_id="opponent")])
            path = "data/football-form/" + F.COUNT_LEDGER_NAMES[0]
            rows = F.load_pending_rows([path, path])
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(F.collect_target_fixtures(rows)["epl"]), 1)
            self.assertEqual(F.DEFAULT_API_FOOTBALL_MAX_REQUESTS, 10)

    def test_candidate_blank_rows_and_settled_picks_stay_out(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(F, "ROOT", Path(tmp)):
            root = Path(tmp)
            self.write(root, "football-counts-vnext-candidates.csv", [dict(pick_id="candidate", result="")])
            self.assertEqual(F.load_pending_rows(["data/football-form/football-counts-vnext-candidates.csv"]), [])
            self.write(root, F.COUNT_LEDGER_NAMES[1], [dict(pick_id="voided", result="void")])
            self.write(root, F.COUNT_SIGNAL_NAMES[1], [dict(pick_id="voided", result="")])
            self.assertEqual(F.load_pending_rows(["data/football-form/" + F.COUNT_LEDGER_NAMES[1]]), [])


if __name__ == "__main__":
    unittest.main()
