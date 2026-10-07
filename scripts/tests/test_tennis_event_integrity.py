import copy
import importlib.util
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tennis_event_integrity import clean_event_rows, completed_score, revision_records, revision_transition_allowed
spec = importlib.util.spec_from_file_location("board_integrity", Path(__file__).resolve().parents[1] / "build-tennis-props-board.py")
board = importlib.util.module_from_spec(spec)
spec.loader.exec_module(board)


class EventIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.game = dict(winner_id="1", loser_id="2", tour_id="21356", round_id="4", date="2026-10-06", result="6-4 7-6(5)")
        self.stat = {**self.game, "w_ace": "10", "l_ace": "6", "w_df": "1", "l_df": "2", "w_svpt": "60", "l_svpt": "70"}
        self.names = {"1": "Player One", "2": "Player Two"}

    def test_revision_cohorts_never_mix_old_and_repaired_predictions(self):
        original = {"id": "old"}
        repaired = {"id": "new", "implementation_revision": "completed-singles-by-phase-v1"}
        current, archived = revision_records([original, repaired], "completed-singles-by-phase-v1")
        self.assertEqual(current, [repaired])
        self.assertEqual(archived, [original])

    def test_only_named_frozen_registration_can_migrate(self):
        previous = "82a9d822d2a17fdb9acf88db8779d0d4648fc28679a4d28fa290a358ecd13294"
        config = {"supersedes_config_hash": previous, "implementation_revision": "completed-singles-by-phase-v1"}
        self.assertTrue(revision_transition_allowed(previous, config))
        self.assertFalse(revision_transition_allowed("another-registration", config))
        self.assertFalse(revision_transition_allowed(previous, {}))

    def test_retirement_and_incomplete_scores_rejected(self):
        for score in ["6-4 2-0 RET", "6-4 2-0", "W/O", "6-4 6-4 4-6", "6-4 [10-8]"]:
            self.assertFalse(completed_score(score), score)
        self.assertTrue(completed_score("6-4 6-7(5) 6-3"))

    def test_doubles_and_unknown_identity_rejected(self):
        for names in [{"1": "A/B", "2": "C/D"}, {"1": "A"}]:
            self.assertEqual(clean_event_rows([self.stat], [self.game], names)[1], [])

    def test_missing_counts_never_become_zero(self):
        bad = {**self.stat, "w_ace": ""}
        self.assertEqual(clean_event_rows([bad], [self.game], self.names)[1], [])

    def test_duplicate_exact_rows_count_once(self):
        stats, games, counts = clean_event_rows([self.stat]*2, [self.game]*2, self.names)
        self.assertEqual((len(stats), len(games)), (1, 1))
        self.assertEqual(counts["duplicate_rows_removed"], 2)

    def test_conflicting_dates_and_statistics_held_out(self):
        self.assertEqual(clean_event_rows([self.stat], [self.game, {**self.game, "date": "2026-10-05"}], self.names)[1], [])
        self.assertEqual(clean_event_rows([self.stat, {**self.stat, "w_ace": "11"}], [self.game], self.names)[1], [])

    def environment(self, games, schedules, with_history=True, generic_rate="0.0001"):
        current=dict(id="21356",name="Shanghai Rolex Masters - Shanghai",date="2026-10-05",country="CHN",court_id="1",rank="3")
        prior={**current,"id":"old","date":"2025-10-01"}
        tours={"21356":current,**({"old":prior} if with_history else {})}
        history=[]; history_stats=[]
        for phase in ("1","4"):
            for i in range(20):
                g={**self.game,"tour_id":"old","round_id":phase,"date":"2025-10-03","winner_id":str(100+i)}
                history.append(g)
                history_stats.append({**self.stat,**{k:g[k] for k in ("winner_id","loser_id","tour_id","round_id")},"w_ace":"5" if phase=="1" else "15","l_ace":"3" if phase=="1" else "9"})
        current_stats=[{**self.stat,**{k:g[k] for k in ("winner_id","loser_id","tour_id","round_id")}} for g in games]
        def load(tour,ids):
            return (history_stats,history) if ids=={"old"} else (current_stats,games)
        with patch.object(board,"load_current_event_rows",side_effect=load),patch.object(board,"load_oncourt_tours",return_value=tours):
            return board.load_current_tournament_environment(schedules,date(2026,10,7),{}, {("ATP","Hard","all"):{"ace_rate":generic_rate,"df_rate":generic_rate}})

    def schedule(self,round_id):
        return {"tour":"ATP","tour_id":"21356","tournament":"Shanghai","surface":"Hard","round_id_raw":round_id}

    def test_qualifying_contributes_against_the_same_events_qualifying(self):
        games=[{**self.game,"round_id":"1","winner_id":str(i)} for i in (1,3)]
        result=self.environment(games,[self.schedule("4")])[("ATP","21356","main_draw")]
        self.assertEqual(result["qualifying_matches"],"2")
        self.assertEqual(result["main_draw_matches"],"0")
        self.assertGreater(float(result["ace_factor"]),1)
        self.assertAlmostEqual(float(result["reference_ace_rate"]),8/130,places=4)
        self.assertEqual(result["baseline_source"],"same_event_prior_editions")

    def test_generic_surface_cannot_change_a_tournament_adjustment(self):
        games=[{**self.game,"winner_id":str(i)} for i in (1,3)]
        first=self.environment(games,[self.schedule("4")],generic_rate="0.001")
        second=self.environment(games,[self.schedule("4")],generic_rate="0.99")
        self.assertEqual(first,second)
        neutral=self.environment(games,[self.schedule("4")],with_history=False)[("ATP","21356","main_draw")]
        self.assertEqual(neutral["ace_factor"],"1.0000")
        self.assertEqual(neutral["df_factor"],"1.0000")
        self.assertEqual(neutral["sample_flag"],"NO_USABLE_EVENT_REFERENCE")

    def test_reference_rejects_other_venues_courts_levels_and_duplicate_editions(self):
        current=dict(name="Shanghai Rolex Masters - Shanghai",date="2026-10-05",country="CHN",court_id="1",rank="3")
        good={**current,"date":"2025-10-01"}
        for changed in ({"country":"USA"},{"court_id":"3"},{"rank":"1"},{"name":"Other Open - Beijing"},{"date":"2026-10-01"}):
            self.assertEqual(board.previous_event_editions(current,{"x":{**good,**changed}}),{})
        self.assertEqual(board.previous_event_editions(current,{"a":good,"b":good}),{})
        self.assertEqual(board.previous_event_editions(current,{"a":good}),{"a":good})

    def test_phase_mix_uses_weighted_phase_references(self):
        games=[{**self.game,"round_id":"1"},{**self.game,"winner_id":"3","round_id":"4"}]
        row=self.environment(games,[self.schedule("4")])[("ATP","21356","main_draw")]
        # 16 observed aces in each match; qualifying expects 8 and main draw 24.
        self.assertEqual(row["ace_factor"],"1.0000")
        self.assertEqual((row["qualifying_matches"],row["main_draw_matches"]),("1","1"))

    def test_same_day_and_future_results_excluded(self):
        for day in ["2026-10-07","2026-10-08"]:
            row=self.environment([{**self.game,"date":day}],[self.schedule("4")])[("ATP","21356","main_draw")]
            self.assertEqual(row["matches"],"0")

    def test_prior_day_completed_main_draw_is_used(self):
        row=self.environment([copy.copy(self.game)],[self.schedule("4")])[("ATP","21356","main_draw")]
        self.assertEqual(row["matches"],"1")
        self.assertEqual(row["latest_result_date"],"2026-10-06")

    def test_oncourt_indoor_hard_is_not_grass(self):
        self.assertEqual(board.SURFACE_BY_COURT["3"],"Hard")
        self.assertEqual(board.SURFACE_BY_COURT["4"],"Carpet")


if __name__ == "__main__":
    unittest.main()
