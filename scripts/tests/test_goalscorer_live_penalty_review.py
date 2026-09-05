from __future__ import annotations

import importlib.util
import json
import runpy
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "goalscorer-live-penalty-review.py"
SPEC = importlib.util.spec_from_file_location("goalscorer_live_penalty_review", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
PENALTY_REVIEW = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "goalscorer-penalty-review.py"),
    run_name="goalscorer_penalty_review_test",
)


class GoalscorerLivePenaltyReviewTests(unittest.TestCase):
    def lineup(self, substitutions=None, events=None):
        primary = {"id": 1, "name": "First Player", "performance": {"substitutionEvents": substitutions or [], "events": events or []}}
        return {"starters": [primary] + [{"id": i, "name": f"Other {i}"} for i in range(2, 12)], "subs": [], "unavailable": []}

    def test_actual_lineup_timeline_proves_on_pitch_before_substitution(self):
        lineup = self.lineup([{"type": "subOut", "time": 70}])
        self.assertIs(MODULE._on_pitch_at(lineup, "First Player", 60)[0], True)
        self.assertIs(MODULE._on_pitch_at(lineup, "First Player", 80)[0], False)
        self.assertIsNone(MODULE._on_pitch_at(lineup, "First Player", 70)[0])

    def test_predicted_starter_or_missing_timeline_never_proves_availability(self):
        self.assertIsNone(MODULE._on_pitch_at({"primary_lineup_status": "confirmed_starter"}, "First Player", 30)[0])
        lineup = self.lineup()
        del lineup["starters"][0]["performance"]["substitutionEvents"]
        self.assertIsNone(MODULE._on_pitch_at(lineup, "First Player", 30)[0])

    def test_red_card_and_ambiguous_dismissal_order_are_respected(self):
        lineup = self.lineup(events=[{"type": "redCard", "time": 40}])
        self.assertIs(MODULE._on_pitch_at(lineup, "First Player", 35)[0], True)
        self.assertIs(MODULE._on_pitch_at(lineup, "First Player", 50)[0], False)
        self.assertIsNone(MODULE._on_pitch_at(lineup, "First Player", 40)[0])

    def test_exact_player_identity_is_required(self):
        self.assertIsNone(MODULE._on_pitch_at(self.lineup(), "Player", 30)[0])
        self.assertIs(MODULE._on_pitch_at(self.lineup(), "First Player", 30)[0], True)

    def test_unknown_event_type_does_not_silently_ignore_possible_dismissal(self):
        lineup = self.lineup(events=[{"type": "card", "cardType": "red", "time": 20}])
        self.assertIsNone(MODULE._on_pitch_at(lineup, "First Player", 30)[0])

    def test_hierarchy_file_supplies_fallback_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hierarchy.json"
            path.write_text(
                json.dumps(
                    {
                        "Sevilla": {
                            "primary": "Isaac Romero",
                            "secondary": "Peque Fernandez",
                            "tertiary": "Jon Guridi",
                            "last_verified": {"date": "2026-07-30"},
                        }
                    }
                ),
                encoding="utf-8",
            )
            hierarchy = MODULE._load_hierarchy_map(path, lambda value: value.lower())
            merged = MODULE._apply_hierarchy_fallback(
                {"primary": "", "secondary": "", "tertiary": "", "_source_path": ""},
                hierarchy["sevilla"],
            )

        self.assertEqual(merged["primary"], "Isaac Romero")
        self.assertEqual(merged["secondary"], "Peque Fernandez")
        self.assertEqual(merged["tertiary"], "Jon Guridi")
        self.assertEqual(merged["_generated_at"], "2026-07-30")

    def test_csv_writer_uses_repository_lf_endings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            MODULE._write_csv(path, [{field: "" for field in MODULE.FIELDNAMES}])
            self.assertNotIn(b"\r\n", path.read_bytes())

    def test_existing_match_context_wins_over_hierarchy_fallback(self):
        merged = MODULE._apply_hierarchy_fallback(
            {"primary": "Matchday Taker", "secondary": "", "tertiary": ""},
            {"primary": "Filed Primary", "secondary": "Filed Secondary", "tertiary": "Filed Third"},
        )
        self.assertEqual(merged["primary"], "Matchday Taker")
        self.assertEqual(merged["secondary"], "Filed Secondary")

    def test_tracked_primary_holds_without_lineup_context(self):
        classify = PENALTY_REVIEW["_classify_review_type"]
        context = {
            "primary": "Andres Martin",
            "secondary": "Sergio Canales",
            "tertiary": "Juan Carlos Arana",
            "primary_lineup_status": "unknown",
            "active_slot_pre_match": "",
        }

        self.assertEqual(
            classify(
                context=context,
                actual_role="primary",
                distinct_takers_in_match=1,
            ),
            "primary_held",
        )


if __name__ == "__main__":
    unittest.main()
