from __future__ import annotations

import json
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
FETCH = runpy.run_path(str(ROOT / "scripts/fotmob-fetch-lineups.py"))
VALIDATE = runpy.run_path(str(ROOT / "scripts/validate-goalscorer-live-outputs.py"))


class LineupContractTests(unittest.TestCase):
    def validate(self, fixtures):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lineups.json"
            path.write_text(json.dumps({"fixtures": fixtures}), encoding="utf-8")
            return VALIDATE["validate_lineups"](str(path), "lineups")

    def fixture(self, kind="predicted"):
        return dict(match_date="2026-09-12", home_team="Arsenal", away_team="Chelsea",
                    lineup_type=kind, home_status="FotMob Expected XI", away_status="FotMob Expected XI",
                    home_players=[f"Home {i}" for i in range(11)], away_players=[f"Away {i}" for i in range(11)])

    def test_fetcher_pending_fixture_passes_real_validator(self):
        fetch = FETCH["fetch_confirmed_lineups"]
        match = dict(id=123, home={"name": "Arsenal"}, away={"name": "Chelsea"},
                     status={"utcTime": "2026-09-12T14:00:00Z"})
        for lineup in (None, {"lineupType": "pending"}):
            with self.subTest(lineup=lineup), patch.dict(fetch.__globals__, {
                "_fetch_json": lambda url, params: {"leagues": [{"id": 47, "matches": [match]}]} if "date" in params else {"pageUrl": "/match/123"},
                "_fetch_text": lambda url: "unused",
                "_extract_next_payload": lambda text: {"props": {"pageProps": {"content": {"lineup": lineup}}}},
            }):
                fixtures, _ = fetch("20260912", 47, {}, str.lower)
                self.assertEqual(len(fixtures), 1)
                self.assertEqual(fixtures[0]["lineup_type"], "pending")
                self.assertEqual(fixtures[0]["home_players"], [])
                self.assertIn("pending=1", self.validate(fixtures)[0])

    def test_available_predicted_and_confirmed_lineups_pass(self):
        self.validate([self.fixture(), self.fixture("standard")])

    def test_incomplete_second_fixture_is_rejected(self):
        broken = self.fixture("standard")
        broken["away_players"] = []
        with self.assertRaisesRegex(ValueError, r"fixtures\[1\].away.*11"):
            self.validate([self.fixture(), broken])

    def test_missing_status_is_not_silently_accepted(self):
        broken = self.fixture()
        del broken["home_status"]
        with self.assertRaisesRegex(ValueError, "home_status"):
            self.validate([broken])

    def test_pending_cannot_claim_confirmed_or_contain_players(self):
        pending = self.fixture("pending")
        pending.update(home_players=[], away_players=[], home_starters=[], away_starters=[],
                       home_status="Lineup Pending", away_status="Lineup Pending")
        self.validate([pending])
        for change in ({"home_status": "Confirmed Lineup"}, {"home_players": ["Invented starter"]}, {"home_players": None}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.validate([{**pending, **change}])

    def test_empty_fixture_list_is_valid(self):
        self.assertIn("fixtures=0", self.validate([])[0])


if __name__ == "__main__":
    unittest.main()
