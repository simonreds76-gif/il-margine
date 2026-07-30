import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "apply-agent-club-penalty-audits.py"
SPEC = importlib.util.spec_from_file_location("apply_agent_club_penalty_audits", SCRIPT)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class SquadMembershipGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.order = {
            "primary": "Raphinha",
            "secondary": "Lamine Yamal",
            "tertiary": "Ferran Torres",
        }

    def test_accepts_three_confirmed_current_players(self) -> None:
        row = {
            "club": "Barcelona",
            "squad_membership": {
                position: {
                    "player": player,
                    "status": "confirmed",
                    "source_url": "https://www.fcbarcelona.com/en/football/first-team/players",
                    "checked_at": "2026-07-30",
                }
                for position, player in self.order.items()
            },
        }
        verified = MOD.confirmed_squad_membership(row, self.order)
        self.assertEqual(verified["primary"]["player"], "Raphinha")

    def test_rejects_departed_or_unconfirmed_player(self) -> None:
        order = dict(self.order)
        order["tertiary"] = "Robert Lewandowski"
        row = {
            "club": "Barcelona",
            "squad_membership": {
                "primary": {
                    "player": "Raphinha",
                    "status": "confirmed",
                    "source_url": "https://www.fcbarcelona.com/en/football/first-team/players",
                    "checked_at": "2026-07-30",
                },
                "secondary": {
                    "player": "Lamine Yamal",
                    "status": "confirmed",
                    "source_url": "https://www.fcbarcelona.com/en/football/first-team/players",
                    "checked_at": "2026-07-30",
                },
                "tertiary": {
                    "player": "Robert Lewandowski",
                    "status": "departed",
                    "source_url": "https://www.fcbarcelona.com/en/news/4504409/",
                    "checked_at": "2026-07-30",
                },
            },
        }
        with self.assertRaisesRegex(ValueError, "not confirmed"):
            MOD.confirmed_squad_membership(row, order)

    def test_prunes_change_logs_with_missing_evidence(self) -> None:
        evidence = [{"id": "valid-event"}]
        changes = [
            {"evidence_ids": ["valid-event"], "change_type": "valid"},
            {"evidence_ids": ["missing-event"], "change_type": "dangling"},
        ]
        cleaned = MOD.valid_change_log(changes, evidence)
        self.assertEqual([item["change_type"] for item in cleaned], ["valid"])


if __name__ == "__main__":
    unittest.main()
