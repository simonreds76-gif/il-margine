from __future__ import annotations

import importlib.util
import unittest
from unittest.mock import Mock, patch
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
    def test_existing_pairs_beyond_supabase_cap_are_not_reinserted(self):
        page1 = [{"tour_id": 1, "player1_id": n + 1, "player2_id": n + 1001} for n in range(1000)]
        page2 = [{"tour_id": 21362, "player1_id": 31392, "player2_id": 31358}]
        responses = [Mock(json=Mock(return_value=page)) for page in (page1, page2)]
        with patch.object(module.requests, "get", side_effect=responses) as get:
            pairs = module.fetch_open_pairs("https://example.invalid", {})
        self.assertIn((21362, 31358, 31392), pairs)
        self.assertEqual([c.kwargs["params"]["offset"] for c in get.call_args_list], ["0", "1000"])

    def test_later_page_failure_cannot_return_partial_population(self):
        first = Mock(json=Mock(return_value=[{"tour_id": 1, "player1_id": 1, "player2_id": 2}] * 1000))
        with patch.object(module.requests, "get", side_effect=[first, RuntimeError("temporarily unavailable")]):
            with self.assertRaises(RuntimeError):
                module.fetch_open_pairs("https://example.invalid", {})

    def test_reviewed_munar_identity_recovers_short_name(self):
        alias = {"tour": "ATP", "source_name": "Jaume Munar", "native_id": 31358,
                 "native_name": "Jaume Antoni Munar Clar", "birthdate": "1997-05-05",
                 "evidence": "Reviewed native/archive identity"}
        player = {"id": 31358, "name": alias["native_name"], "birthdate": alias["birthdate"]}
        resolve = module.build_player_resolver([player], [alias])
        self.assertEqual(resolve("Jaume Munar"), (31358, "reviewed_id_name_dob_alias"))

    def test_alias_identity_drift_and_homonyms_are_rejected(self):
        alias = {"tour": "ATP", "source_name": "Short Name", "native_id": 1,
                 "native_name": "Long Full Name", "birthdate": "1997-05-05", "evidence": "reviewed"}
        player = {"id": 1, "name": "Long Full Name", "birthdate": "1997-05-05"}
        for changed in ({**player, "birthdate": "1998-05-05"}, {**player, "name": "Other Player"}):
            self.assertIsNone(module.build_player_resolver([changed], [alias])("Short Name")[0])
        self.assertIsNone(module.build_player_resolver([player, {"id": 2, "name": "Short Name"}], [alias])("Short Name")[0])
        self.assertIsNone(module.build_player_resolver([player], [alias, {**alias, "native_id": 2}])("Name")[0])

    def test_wrong_tour_and_unreviewed_alias_are_not_used(self):
        player = {"id": 1, "name": "Long Full Name", "birthdate": "1997-05-05"}
        alias = {"tour": "ATP", "source_name": "Short Name", "native_id": 1,
                 "native_name": player["name"], "birthdate": player["birthdate"], "evidence": "reviewed"}
        for changed in ({**alias, "tour": "WTA"}, {**alias, "evidence": ""}):
            self.assertIsNone(module.build_player_resolver([player], [changed])("Short Name")[0])

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
