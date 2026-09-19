import importlib.util
import json
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "audit-club-penalty-squads.py"
SPEC = importlib.util.spec_from_file_location("audit_club_penalty_squads", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ClubPenaltySquadAuditTests(unittest.TestCase):
    def test_role_review_age_does_not_reset_with_roster_check(self) -> None:
        jobs = [{'league': 'epl', 'club': 'Test', 'entry': {
            'last_reviewed': {'date': '2026-08-28'},
            'last_verified': {'date': '2026-09-19', 'method': 'current_squad_membership_audit'},
        }}]
        season = {'league_start_dates': {'epl': '2026-08-21'}}
        self.assertEqual(MODULE.hierarchy_quality(jobs, season, date(2026, 9, 18)), [])
        self.assertEqual(MODULE.hierarchy_quality(jobs, season, date(2026, 9, 19))[0]['status'], 'hierarchy_review_due')
        self.assertEqual(MODULE.hierarchy_quality(jobs, season, date(2027, 7, 1)), [])

    def test_recent_approved_penalty_review_counts_but_future_review_does_not(self) -> None:
        job = {'league': 'epl', 'club': 'Test', 'entry': {
            'last_reviewed': {'date': '2026-08-01'},
            'evidence_log': [{'type': 'competitive_penalty_event', 'date': '2026-09-18',
                              'review': {'status': 'approved', 'reviewed_at': '2026-09-19T12:00:00Z'}}],
        }}
        season = {'league_start_dates': {'epl': '2026-08-21'}}
        self.assertEqual(MODULE.hierarchy_quality([job], season, date(2026, 9, 19)), [])
        self.assertEqual(len(MODULE.hierarchy_quality([job], season, date(2026, 9, 17))), 1)

    def test_duplicate_full_names_fold_accents_but_mononyms_are_not_identity(self) -> None:
        jobs = [
            {'league': 'epl', 'club': 'A', 'entry': {'primary': 'Martin Ødegaard', 'secondary': 'Vitinha'}},
            {'league': 'ligue-1', 'club': 'B', 'entry': {'primary': 'Martin Odegaard', 'secondary': 'Vitinha'}},
        ]
        result = MODULE.hierarchy_quality(jobs, {}, date(2026, 9, 19))
        self.assertEqual(len(result), 2)
        self.assertTrue(all(r['status'] == 'possible_duplicate_player' for r in result))
        self.assertTrue(all(r['rank'] == 'primary' for r in result))

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
