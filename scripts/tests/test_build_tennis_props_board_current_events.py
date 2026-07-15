from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
MODULE_PATH = SCRIPTS / "build-tennis-props-board.py"
SPEC = importlib.util.spec_from_file_location("build_tennis_props_board", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CurrentTournamentAliasTests(unittest.TestCase):
    def test_current_atp_clay_events_are_supported(self) -> None:
        aliases = {
            "Nordea Open - Bastad": "Bastad",
            "EFG Swiss Open - Gstaad": "Gstaad",
            "Plava Laguna Croatia Open - Umag": "Umag",
        }
        for raw, expected in aliases.items():
            with self.subTest(raw=raw):
                self.assertEqual(MODULE.canonical_tournament_name(raw), expected)

    def test_current_wta_events_are_supported(self) -> None:
        aliases = {
            "Athens Open - Athens": "Athens",
            "UniCredit Iasi Open - Iasi": "Iasi",
        }
        for raw, expected in aliases.items():
            with self.subTest(raw=raw):
                self.assertEqual(MODULE.canonical_tournament_name(raw), expected)


if __name__ == "__main__":
    unittest.main()
