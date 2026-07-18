from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "tennis-guard-audit.py"
SPEC = importlib.util.spec_from_file_location("tennis_guard_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def row(**overrides):
    values = {
        "date": "2025-03-10",
        "surface": "Hard",
        "series": "Masters 1000",
        "confidence": "high",
        "value_pct": "20",
        "bet_side": "loser",
        "our_prob": "0.80",
        "pinnacle_prob_novig": "0.65",
        "pinnacle_odds": "1.45",
        "pinnacle_odds_loser": "3.00",
        "has_pinnacle_odds": "True",
    }
    values.update(overrides)
    return MODULE.parse_row(values)


class TennisGuardAuditTests(unittest.TestCase):
    def test_guard_flags_separate_gap_side_flip_and_heavy_dog(self):
        parsed = row()
        self.assertIsNotNone(parsed)
        flags = MODULE.guard_flags(parsed)
        self.assertFalse(flags["model_favourite_below_1_25"])
        self.assertTrue(flags["model_market_gap_above_10pp"])
        self.assertFalse(flags["model_market_side_flip"])
        self.assertTrue(flags["masters_hard_heavy_favourite_dog"])

        flipped = row(our_prob="0.40", pinnacle_prob_novig="0.65")
        self.assertIsNotNone(flipped)
        flipped_flags = MODULE.guard_flags(flipped)
        self.assertTrue(flipped_flags["model_market_side_flip"])

    def test_atp500_short_favourite_is_profile_scoped(self):
        parsed = row(series="ATP500", our_prob="0.60", pinnacle_prob_novig="0.58")
        self.assertIsNotNone(parsed)
        flags = MODULE.guard_flags(parsed)
        self.assertTrue(flags["atp500_hard_short_favourite"])
        self.assertFalse(flags["masters_hard_heavy_favourite_dog"])

    def test_audit_reports_unique_overlap_without_double_counting(self):
        only_model = row(our_prob="0.85", pinnacle_prob_novig="0.78", bet_side="winner", pinnacle_odds="1.20")
        overlap = row(our_prob="0.85", pinnacle_prob_novig="0.60")
        clean = row(our_prob="0.60", pinnacle_prob_novig="0.58", bet_side="winner", pinnacle_odds="1.70")
        self.assertTrue(only_model and overlap and clean)

        audit = MODULE.audit_profile([only_model, overlap, clean], lambda _: True)
        self.assertEqual(audit["before_guards"]["bets"], 3)
        self.assertEqual(audit["after_all_replayable_guards"]["bets"], 1)
        model_guard = audit["guards"]["model_favourite_below_1_25"]
        self.assertEqual(model_guard["flagged"]["bets"], 2)
        self.assertEqual(model_guard["unique"]["bets"], 0)

    def test_volume_200_profile_rules(self):
        hard_slam = row(series="Grand Slam", confidence="medium", value_pct="5")
        clay_500 = row(surface="Clay", series="ATP500", confidence="high", value_pct="10")
        clay_250 = row(surface="Clay", series="ATP250", confidence="high", value_pct="50")
        self.assertTrue(hard_slam and clay_500 and clay_250)
        self.assertTrue(MODULE._volume_200_candidate(hard_slam))
        self.assertTrue(MODULE._volume_200_candidate(clay_500))
        self.assertFalse(MODULE._volume_200_candidate(clay_250))


if __name__ == "__main__":
    unittest.main()
