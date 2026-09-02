from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "club-penalty-squad-alert.py"
SPEC = importlib.util.spec_from_file_location("club_penalty_squad_alert", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ClubPenaltySquadAlertTests(unittest.TestCase):
    def test_clean_audit_has_no_issues(self) -> None:
        payload = {"rows": [{"status": "present"}]}
        self.assertEqual(MODULE.issue_rows(payload), [])

    def test_message_names_missing_player_and_deduplicates_fetch_errors(self) -> None:
        payload = {
            "clubs_checked": 96,
            "slots_checked": 288,
            "status_counts": {"present": 283, "missing": 2, "fetch_error": 3},
            "rows": [
                {"status": "missing", "league": "epl", "club": "Everton", "rank": "primary", "player": "Old Player"},
                {"status": "fetch_error", "league": "serie-a", "club": "Milan", "rank": "primary", "player": "A"},
                {"status": "fetch_error", "league": "serie-a", "club": "Milan", "rank": "secondary", "player": "B"},
            ],
        }
        message = MODULE.build_message(payload, "https://example.test/run")
        self.assertIn("Everton | primary Old Player", message)
        self.assertEqual(message.count("SERIE-A | Milan | squad unavailable"), 1)
        self.assertIn("were not changed automatically", message)
        self.assertIn("https://example.test/run", message)


if __name__ == "__main__":
    unittest.main()
