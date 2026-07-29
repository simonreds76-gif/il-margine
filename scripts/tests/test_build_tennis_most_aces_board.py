from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
PATH = SCRIPTS / "build-tennis-most-aces-board.py"
SPEC = importlib.util.spec_from_file_location("build_tennis_most_aces_board_test", PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def side(
    player: str,
    opponent: str,
    mean: float,
    matches: int,
    svpt: int,
    *,
    l24m_matches: int | None = None,
    l24m_svpt: int | None = None,
    career_matches: int | None = None,
    career_svpt: int | None = None,
    activity_matches: int | None = None,
    activity_svpt: int | None = None,
) -> dict[str, str]:
    return {
        "date": "2026-07-30",
        "tour": "ATP",
        "tournament": "Washington",
        "round": "R16",
        "surface": "Hard",
        "player": player,
        "opponent": opponent,
        "projected_aces": str(mean),
        "aces_alpha": "0.180034",
        "v3_eligible": "true",
        "ace_confidence": "MED",
        "player_name_resolution": "exact",
        "opponent_name_resolution": "exact",
        "player_l12m_matches": str(matches),
        "player_l12m_svpt_sample": str(svpt),
        "player_l24m_matches": str(l24m_matches if l24m_matches is not None else matches),
        "player_l24m_svpt_sample": str(l24m_svpt if l24m_svpt is not None else svpt),
        "player_career4y_matches": str(career_matches if career_matches is not None else matches),
        "player_career4y_svpt_sample": str(career_svpt if career_svpt is not None else svpt),
        "player_activity_l12m_matches": str(activity_matches if activity_matches is not None else matches),
        "player_activity_l12m_svpt": str(activity_svpt if activity_svpt is not None else svpt),
        "notes": "",
    }


class MostAcesQuoteQualityTests(unittest.TestCase):
    def test_ready_pair_exposes_fair_prices(self) -> None:
        rows = MODULE.build_rows(
            [
                side("Taylor Harry Fritz", "Kamil Majchrzak", 12.0, 44, 3703),
                side("Kamil Majchrzak", "Taylor Harry Fritz", 6.0, 20, 1600),
            ],
            0.22,
        )
        self.assertEqual(rows[0]["quote_status"], "READY")
        self.assertTrue(rows[0]["fair_player1"])

    def test_recent_activity_with_main_tour_gap_keeps_research_prices(self) -> None:
        rows = MODULE.build_rows(
            [
                side("Rafael Jodar", "Kei Nishikori", 4.7, 14, 1002),
                side(
                    "Kei Nishikori", "Rafael Jodar", 3.7, 1, 73,
                    l24m_matches=23, l24m_svpt=1783,
                    career_matches=27, career_svpt=2050,
                    activity_matches=10, activity_svpt=712,
                ),
            ],
            0.22,
        )
        self.assertEqual(rows[0]["quote_status"], "COVERAGE_GAP_ESTIMATE")
        self.assertIn("P2_ACTIVITY_COVERAGE_GAP_10M_712SVPT_L12M", rows[0]["quote_reason"])
        self.assertEqual(rows[0]["player2_evidence_tier"], "COVERAGE_GAP")
        self.assertTrue(rows[0]["fair_player1"])
        self.assertGreater(float(rows[0]["p_player1"]), 0.0)

    def test_genuinely_thin_history_blocks_prices(self) -> None:
        rows = MODULE.build_rows(
            [
                side("Prospect One", "Prospect Two", 4.7, 2, 120),
                side("Prospect Two", "Prospect One", 3.7, 1, 73),
            ],
            0.22,
        )
        self.assertEqual(rows[0]["quote_status"], "BLOCKED_INPUT_QUALITY")
        self.assertIn("P1_INSUFFICIENT_HISTORY", rows[0]["quote_reason"])
        self.assertEqual(rows[0]["fair_player1"], "")

    def test_unresolved_name_blocks_prices(self) -> None:
        left = side("Unknown Name", "Player Two", 7.0, 20, 1500)
        left["player_name_resolution"] = "unresolved"
        rows = MODULE.build_rows(
            [left, side("Player Two", "Unknown Name", 5.0, 20, 1500)],
            0.22,
        )
        self.assertEqual(rows[0]["quote_status"], "BLOCKED_INPUT_QUALITY")
        self.assertIn("P1_NAME_UNRESOLVED", rows[0]["quote_reason"])


if __name__ == "__main__":
    unittest.main()
