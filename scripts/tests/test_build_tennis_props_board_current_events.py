from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


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
            "Millennium Estoril Open - Estoril": "Estoril",
            "Generali Open - Kitzbuhel": "Kitzbuhel",
            "Generali Open - Kitzbühel": "Kitzbuhel",
        }
        for raw, expected in aliases.items():
            with self.subTest(raw=raw):
                self.assertEqual(MODULE.canonical_tournament_name(raw), expected)

    def test_unknown_main_tour_schedule_uses_location_suffix(self) -> None:
        self.assertEqual(
            MODULE.scheduled_tournament_name("Mifel Tennis Open - Los Cabos"),
            "Los Cabos",
        )


class CurrentEventRowsCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        MODULE._CURRENT_EVENT_ROWS_CACHE.clear()

    def tearDown(self) -> None:
        MODULE._CURRENT_EVENT_ROWS_CACHE.clear()

    def test_large_exports_are_read_once_for_repeated_feature_loads(self) -> None:
        with mock.patch.object(
            MODULE,
            "_read_current_event_rows",
            side_effect=([{"tour_id": "101"}], [{"tour_id": "101"}]),
        ) as reader:
            first = MODULE.load_current_event_rows("atp", {"101"})
            second = MODULE.load_current_event_rows("atp", {"101"})

        self.assertIs(first, second)
        self.assertEqual(reader.call_count, 2)

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
