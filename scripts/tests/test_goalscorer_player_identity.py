from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from goalscorer_penalty_utils import best_name_match, player_match_score


COMPARE_PATH = SCRIPTS / "goalscorer-live-compare.py"
SPEC = importlib.util.spec_from_file_location("goalscorer_live_compare_identity_test", COMPARE_PATH)
assert SPEC and SPEC.loader
COMPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPARE)


def player(name: str, team_key: str) -> dict[str, object]:
    key = COMPARE._norm_text(name)
    return {
        "player_id": "1",
        "player_name": name,
        "player_key": key,
        "team": team_key,
        "team_key": team_key,
        "team_keys": [team_key],
        "position": "FW",
        "match_date": "2026-08-01",
        "games": 1.0,
        "minutes": 90.0,
        "source": "history",
    }


class GoalscorerPlayerIdentityTests(unittest.TestCase):
    def test_same_surname_different_full_given_names_do_not_match(self) -> None:
        self.assertEqual(player_match_score("Marcos Fernandez", "Roberto Fernández"), 0)
        self.assertIsNone(best_name_match("Marcos Fernandez", ["Roberto Fernández"]))

    def test_initial_and_reordered_aliases_remain_supported(self) -> None:
        self.assertGreaterEqual(player_match_score("R. Fernandez", "Roberto Fernández"), 90)
        self.assertGreaterEqual(player_match_score("Kike Garcia", "Garcia Kike"), 90)

    def test_transliteration_and_compound_given_names_match(self) -> None:
        self.assertGreaterEqual(player_match_score("Kenan Yıldız", "Kenan Yildiz"), 90)
        self.assertGreaterEqual(player_match_score("Luca Waldschmidt", "Gian-Luca Waldschmidt"), 88)
        self.assertGreaterEqual(player_match_score("Ben Lhassine Kone", "Benjamin Lhassine Kone"), 88)
        self.assertGreaterEqual(player_match_score("Tasos Douvikas", "Anastasios Douvikas"), 88)

    def test_live_resolver_rejects_surname_collision_inside_fixture(self) -> None:
        roberto = player("Roberto Fernández", "espanyol")
        resolved = COMPARE._resolve_player_meta(
            "Marcos Fernandez",
            "espanyol",
            "levante",
            {roberto["player_key"]: roberto},
            {"espanyol": [roberto]},
            {},
            {},
        )
        self.assertIsNone(resolved)

    def test_live_resolver_rejects_exact_name_from_unrelated_team(self) -> None:
        marcos = player("Marcos Fernandez", "betis")
        resolved = COMPARE._resolve_player_meta(
            "Marcos Fernandez",
            "espanyol",
            "levante",
            {marcos["player_key"]: marcos},
            {},
            {},
            {},
        )
        self.assertIsNone(resolved)

    def test_live_resolver_keeps_exact_player_on_fixture_team(self) -> None:
        roberto = player("Roberto Fernández", "espanyol")
        resolved = COMPARE._resolve_player_meta(
            "Roberto Fernandez",
            "espanyol",
            "levante",
            {roberto["player_key"]: roberto},
            {"espanyol": [roberto]},
            {},
            {},
        )
        self.assertIs(resolved, roberto)


if __name__ == "__main__":
    unittest.main()
