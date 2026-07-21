from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
MODULE_PATH = SCRIPTS / "tennis-props-compare-bet365.py"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("tennis_props_compare_bet365", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class LegacyTeamTotalNormalizationTests(unittest.TestCase):
    def test_away_team_total_becomes_away_player_market(self) -> None:
        row = {
            "player": "Gonzalo Bueno",
            "opponent": "Tiago Pereira",
            "market": "match_aces",
            "raw_market_name": "Team Total (Aces) Away",
        }
        result = MODULE.normalize_legacy_team_total_row(row)
        self.assertEqual(result["market"], "aces")
        self.assertEqual(result["player"], "Tiago Pereira")
        self.assertEqual(result["opponent"], "Gonzalo Bueno")
        self.assertEqual(row["market"], "match_aces")

    def test_home_team_total_keeps_home_player(self) -> None:
        row = {
            "player": "Gonzalo Bueno",
            "opponent": "Tiago Pereira",
            "market": "match_double_faults",
            "raw_market_name": "Team Total (Double Faults) Home",
        }
        result = MODULE.normalize_legacy_team_total_row(row)
        self.assertEqual(result["market"], "double_faults")
        self.assertEqual(result["player"], "Gonzalo Bueno")
        self.assertEqual(result["opponent"], "Tiago Pereira")

    def test_plain_match_total_is_unchanged(self) -> None:
        row = {
            "player": "Gonzalo Bueno",
            "opponent": "Tiago Pereira",
            "market": "match_aces",
            "raw_market_name": "Totals (Aces)",
        }
        self.assertEqual(MODULE.normalize_legacy_team_total_row(row), row)


class PlayerOnlyFallbackTests(unittest.TestCase):
    def test_populated_pair_cannot_fallback_by_player_only(self) -> None:
        self.assertFalse(MODULE.can_fallback_player_only("Gonzalo Bueno", "Tiago Pereira"))

    def test_missing_opponent_can_fallback_by_player_only(self) -> None:
        self.assertTrue(MODULE.can_fallback_player_only("Gonzalo Bueno", ""))

    def test_placeholder_player_can_use_named_opponent(self) -> None:
        self.assertTrue(MODULE.can_fallback_player_only("Total", "Gonzalo Bueno"))


if __name__ == "__main__":
    unittest.main()
