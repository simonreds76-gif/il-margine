from __future__ import annotations

import importlib.util
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "supplement_masters_qualifying",
    ROOT / "scripts" / "supplement-masters-qualifying.py",
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class SupplementMastersQualifyingTests(unittest.TestCase):
    def test_cincinnati_is_current_masters_hard_tour(self) -> None:
        tours = module.find_current_masters_tours(
            [
                {
                    "id": "21347",
                    "name": "Cincinnati Open - Cincinnati",
                    "court_id": "1",
                    "date": "2026-08-10",
                    "rank": "3",
                }
            ],
            date(2026, 8, 11),
        )
        self.assertEqual(tours["cincinnati"]["tour_id"], 21347)
        self.assertEqual(tours["cincinnati"]["court_id"], 1)

    def test_full_compact_and_reversed_names_resolve_uniquely(self) -> None:
        resolve = module.build_player_resolver(
            [
                {"id": 1, "name": "Soon-Woo Kwon"},
                {"id": 2, "name": "Seongchan Hong"},
                {"id": 3, "name": "Bu Yunchaokete"},
            ]
        )
        self.assertEqual(resolve("Soonwoo Kwon")[0], 1)
        self.assertEqual(resolve("Seong Chan Hong")[0], 2)
        self.assertEqual(resolve("Yunchaokete Bu")[0], 3)

    def test_ambiguous_compact_name_is_rejected(self) -> None:
        resolve = module.build_player_resolver(
            [
                {"id": 1, "name": "Soon Woo Kwon"},
                {"id": 2, "name": "Soon-Woo Kwon"},
            ]
        )
        self.assertIsNone(resolve("Soonwoo Kwon")[0])

    def test_market_filter_rejects_challenger_and_doubles(self) -> None:
        target = date(2026, 8, 11)
        base = {
            "league": "ATP",
            "league_name": "ATP Cincinnati - Qualifiers",
            "match_date": "2026-08-11",
            "player1_name": "Player One",
            "player2_name": "Player Two",
        }
        self.assertTrue(module.is_qualifier_market(base, target))
        self.assertFalse(module.is_qualifier_market({**base, "league": "Challenger"}, target))
        self.assertFalse(module.is_qualifier_market({**base, "player1_name": "A / B"}, target))

    def test_duplicate_market_pair_is_emitted_once(self) -> None:
        rows = [
            {
                "league_name": "ATP Cincinnati - Qualifiers",
                "player1_name": "Player One",
                "player2_name": "Player Two",
                "match_date": "2026-08-11",
                "kickoff_iso": "2026-08-11T15:00:00Z",
            },
            {
                "league_name": "ATP Cincinnati - Qualifying",
                "player1_name": "Player Two",
                "player2_name": "Player One",
                "match_date": "2026-08-11",
                "kickoff_iso": "2026-08-11T15:00:00Z",
            },
        ]

        def resolve(name: str):
            return ({"Player One": 1, "Player Two": 2}.get(name), "test")

        resolved, unresolved = module.resolve_fixture_rows(
            rows,
            resolve,
            {"cincinnati": {"tour_id": 21347, "tour_name": "Cincinnati Open"}},
        )
        self.assertFalse(unresolved)
        self.assertEqual(len(resolved), 1)


if __name__ == "__main__":
    unittest.main()
