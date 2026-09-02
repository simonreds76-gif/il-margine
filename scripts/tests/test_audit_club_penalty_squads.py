import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "audit-club-penalty-squads.py"
SPEC = importlib.util.spec_from_file_location("audit_club_penalty_squads", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ClubPenaltySquadAuditTests(unittest.TestCase):
    def test_normalizes_accents_and_special_letters(self) -> None:
        self.assertEqual(MODULE.normalize_name("Martin Ødegaard"), "martin odegaard")
        self.assertEqual(MODULE.normalize_name("Pascal Groß"), "pascal gross")
        self.assertEqual(MODULE.normalize_name("Kenan Yıldız"), "kenan yildiz")

    def test_matches_short_name_inside_full_squad_name(self) -> None:
        status, match = MODULE.match_player("Chris Wood", ["Christopher Wood", "Morgan Gibbs-White"])
        self.assertEqual(status, "present")
        self.assertEqual(match, "Christopher Wood")

    def test_reports_close_squad_names_for_review(self) -> None:
        matches = MODULE.closest_squad_names("Kenan Yildiz", ["Kenan Yıldız", "Jonathan Tah"])
        self.assertEqual(matches, "Kenan Yıldız")

    def test_extracts_only_players_from_next_payload(self) -> None:
        payload = {
            "props": {
                "pageProps": {
                    "fallback": {
                        "team-42": {
                            "squad": {
                                "squad": [
                                    {"title": "coach", "members": [{"name": "Coach Name"}]},
                                    {"title": "keepers", "members": [{"name": "Keeper Name"}]},
                                    {"title": "attackers", "members": [{"name": "Taker Name"}]},
                                ]
                            }
                        }
                    }
                }
            }
        }
        html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script>'
        names = MODULE.squad_names(MODULE.extract_team_payload(html, 42))
        self.assertEqual(names, ["Keeper Name", "Taker Name"])


if __name__ == "__main__":
    unittest.main()
