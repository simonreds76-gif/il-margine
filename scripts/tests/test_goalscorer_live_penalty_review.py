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

    def test_pitch_status_distinguishes_starter_sub_and_unavailable(self):
        lineup = {
            "starters": [
                {"name": "Starter", "performance": {"substitutionEvents": [{"type": "subOut", "time": 70}]}}
            ],
            "subs": [
                {"name": "Early Sub", "performance": {"substitutionEvents": [{"type": "subIn", "time": 53}]}},
                {"name": "Late Sub", "performance": {"substitutionEvents": [{"type": "subIn", "time": 87}]}},
            ],
            "unavailable": [{"name": "Suspended Player", "reason": "suspended"}],
        }
        best_match = PENALTY_REVIEW["best_name_match"] if "best_name_match" in PENALTY_REVIEW else None
        if best_match is None:
            utils = runpy.run_path(str(Path(__file__).resolve().parents[1] / "goalscorer_penalty_utils.py"))
            best_match = utils["best_name_match"]

        self.assertEqual(MODULE._player_at_penalty_status(lineup, "Starter", 57, best_match), "Yes - starter")
        self.assertEqual(MODULE._player_at_penalty_status(lineup, "Early Sub", 57, best_match), "Yes - bench, on 53'")
        self.assertEqual(MODULE._player_at_penalty_status(lineup, "Late Sub", 57, best_match), "No - bench, on 87'")
        self.assertEqual(MODULE._player_at_penalty_status(lineup, "Suspended Player", 57, best_match), "No - suspended")


if __name__ == "__main__":
    unittest.main()
