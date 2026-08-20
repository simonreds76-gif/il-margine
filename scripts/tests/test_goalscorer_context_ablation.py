from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "goalscorer-context-ablation.py"
SPEC = importlib.util.spec_from_file_location("goalscorer_context_ablation_test", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def row(day: date, player: str, team: str, opponent: str, position: str, npxg: float):
    return SimpleNamespace(
        match_date=day,
        match_date_str=day.isoformat(),
        player_id=player,
        team_key=team,
        opponent_key=opponent,
        is_home=True,
        position=position,
        npxg=npxg,
    )


class GoalscorerContextAblationTests(unittest.TestCase):
    def test_current_fixture_never_enters_its_own_context(self) -> None:
        rows = [
            row(date(2026, 8, 1), "p1", "a", "b", "FW", 5.0),
            row(date(2026, 8, 4), "p2", "c", "b", "FW", 0.1),
        ]
        context = MODULE.build_causal_context(rows)
        first = context[("2026-08-01", "p1", "a", "b")]
        second = context[("2026-08-04", "p2", "c", "b")]
        self.assertEqual(first.opponent_position_matches, 0)
        self.assertEqual(second.opponent_position_matches, 1)

    def test_rest_is_calculated_from_prior_fixture_only(self) -> None:
        rows = [
            row(date(2026, 8, 1), "p1", "a", "b", "FW", 0.2),
            row(date(2026, 8, 3), "p1", "a", "c", "FW", 0.3),
        ]
        context = MODULE.build_causal_context(rows)
        second = context[("2026-08-03", "p1", "a", "c")]
        self.assertEqual(second.team_rest_days, 2.0)
        self.assertEqual(second.team_short_rest, 1.0)
        self.assertEqual(second.opponent_rest_days, 7.0)

    def test_position_buckets_are_stable(self) -> None:
        self.assertEqual(MODULE.position_bucket("FWR"), "forward")
        self.assertEqual(MODULE.position_bucket("AMC"), "attacking_midfield")
        self.assertEqual(MODULE.position_bucket("DMC"), "midfield")
        self.assertEqual(MODULE.position_bucket("DC"), "defender")


if __name__ == "__main__":
    unittest.main()
