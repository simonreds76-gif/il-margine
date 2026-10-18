"""Regression coverage for verified provider aliases; selection rules stay frozen."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from football_team_names import football_form_team_key
from goalkeeper_saves_live import load_lineup_index, person_match_score, resolve_goalkeeper

class GoalkeeperAliasesTest(unittest.TestCase):
    def test_club_provider_aliases(self):
        for market, lineup in [("Angers SCO", "Angers"), ("AJ Auxerre", "Auxerre"), ("Stade Rennais FC", "Rennes"), ("Olympique Lyon", "Lyon")]:
            with self.subTest(market=market):
                self.assertEqual(football_form_team_key(market), football_form_team_key(lineup))
        self.assertNotEqual(football_form_team_key("Paris FC"), football_form_team_key("Paris Saint-Germain"))

    def test_verified_keeper_aliases(self):
        for market, lineup in [("Landry Mvogo", "Yvon Mvogo"), ("Alejandro Remiro", "Alex Remiro"), ("Odisseas Vlachodimos", "Odysseas Vlachodimos"), ("Andrei Radu", "Ionut Radu")]:
            with self.subTest(market=market):
                self.assertEqual(person_match_score(market, lineup), 100)
                fixture = {"home_starters": [{"name": lineup, "role_group": "GK"}], "lineup_type": "predicted"}
                self.assertEqual(resolve_goalkeeper(fixture, market), ("home", "predicted_starter", lineup))

    def test_other_people_and_nonstarters_stay_blocked(self):
        for left, right in [("Mihai Radu", "Ionut Radu"), ("Alberto Remiro", "Alex Remiro"), ("Aitor Fernandez", "Sergio Herrera"), ("Dean Henderson", "Walter Benitez")]:
            self.assertEqual(person_match_score(left, right), 0)
        fixture = {"home_starters": [{"name": "Yvon Mvogo", "role_group": "DEF"}]}
        self.assertEqual(resolve_goalkeeper(fixture, "Landry Mvogo")[1], "goalkeeper_not_matched_to_lineup")

    def test_date_opponent_and_ambiguity_guards(self):
        fixture = {"match_date": "2026-10-18", "home_team": "Angers", "away_team": "Marseille", "home_starters": [{"name": "Yvon Mvogo", "role_group": "GK"}]}
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "lineups.json"
            p.write_text(json.dumps({"fixtures": [fixture]}), encoding="utf-8")
            index = load_lineup_index([p])
        key = ("2026-10-18", football_form_team_key("Angers SCO"), football_form_team_key("Olympique Marseille"))
        self.assertIn(key, index)
        self.assertNotIn(("2026-10-19", key[1], key[2]), index)
        self.assertNotIn((key[0], key[1], "lyon"), index)
        fixture["away_starters"] = fixture["home_starters"]
        self.assertEqual(resolve_goalkeeper(fixture, "Landry Mvogo")[1], "ambiguous_goalkeeper_identity")

if __name__ == "__main__":
    unittest.main()
