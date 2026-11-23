import hashlib
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import johnny_cards as job
from johnny_cards_review import Analyst, exact_choices, value_range

class Reader:
    def __init__(self, boards):
        self.boards=boards
        self.log=[]
        self.errors=0
    def read(self,name,args,_slot):
        self.log.append(name)
        return {"data":self.boards.get(args.get("competitionId"), {"context":"no fixtures · times UTC","listedCount":0,"fixtureCount":0})}

class MethodTests(unittest.TestCase):
    def test_calendar_summer_utc_and_started(self):
        doc={"context":"times UTC","fixtureCount":2,"listedCount":2,
             "fixturesSummary":"Premier League [competitionId league.0z9xjh1]:\n- 14:00 A v B (id a.1)\n- 10:30 C 1-0 D, live (id c.2)"}
        board=Reader({"premier-league.0z9xjh1":doc})
        games,coverage=job.calendar(board,"2027-05-22",job.utc("2027-05-22T11:05:00Z"))
        self.assertEqual([f["ko"] for f in games],["2027-05-22T14:00:00+00:00"])
        self.assertTrue(all(not l["gap"] for l in coverage))
        self.assertEqual(len(board.log),5)

    def test_missing_board_is_reported(self):
        reader=Reader({"serie-a.17atem7":{"fixtureCount":2,"listedCount":0}})
        self.assertEqual(job.calendar(reader,"2026-11-24",job.utc("2026-11-24T11:00:00Z"))[1][1]["gap"],"calendar unverified")

    def test_tie_two_people_does_not_name_opponent(self):
        player={"position":"LB"}
        opponents={"status":"predicted","players":[{"id":"a","position":"RW","name":"A"},{"id":"b","position":"RM","name":"B"}]}
        self.assertIsNone(job.distinct_opponent(player,opponents))

    def test_other_player_and_under_are_excluded(self):
        f={"home":"X","away":"Y","ko":"2026-11-24T15:00:00Z"}
        c={"player":{"name":"A. Smith"},"name":"Alex Smith"}
        quote={"best":{"odds":3.2,"ageMinutes":10,"bookmaker":"Book"}}
        doc={"context":"X v Y · kick-off 24 Nov 2026, 15:00 UTC",
             "markets":[{"name":"Player Fouls Committed","outcomes":[{**quote,"label":x} for x in
             ("Alex Smith Over 1.5","Andy Smith Over 1.5","Alex Smith Under 1.5")]}]}
        self.assertEqual([p["kind"] for p in job.offers(doc,f,c,"2026-11-24T11:00:00Z",job.utc("2026-11-24T11:00:01Z"))],["fouls"])
        self.assertFalse(job.offers(doc,f,c,"2026-11-24T11:00:00Z",job.utc("2026-11-24T15:01:00Z")))

    def test_exact_original_required(self):
        s=Mock()
        s.get.return_value={"text":"partial or changed copy"}
        with self.assertRaises(RuntimeError):
            with Analyst(s): pass

    def test_unknown_or_duplicate_model_choice_is_rejected(self):
        for indices in ([1],[0,0],[-1],[False]):
            with self.assertRaises(ValueError):exact_choices(indices,["only player"],4)

    def test_no_probability_from_a_grade_or_an_absent_range(self):
        self.assertIsNone(value_range({"odds":4},[]))
        self.assertIsNone(value_range({"odds":4},[0.2,0.1]))
        self.assertIsNone(value_range(None,[0.28,0.35]))
        result=value_range({"odds":4},[0.2,0.32])
        self.assertAlmostEqual(result["evLow"],-0.2)
        self.assertAlmostEqual(result["breakEven"],0.25)

    def test_empty_slate_does_not_invent_players(self):
        analyst=Mock()
        analyst.select_fixtures.return_value=[]
        board=job.scan(Reader({}),"2026-11-24",analyst,lambda:"2026-11-24T11:00:00Z")
        self.assertEqual(len(board["slate"]),0)
        self.assertEqual(len(board["calendar"]),5)
        analyst.select_players.assert_not_called()

    def test_retries_have_same_delivery_key(self):
        report={"day":"2026-11-24","at":"2026-11-24T11:00:00Z","failures":0,
                "slate":[],"calendar":[{"gap":"","league":l} for l in job.LEAGUES]}
        store=Mock();store.get.return_value={"days":{"2026-11-20":{"policy":"old"}}}
        with patch.object(job,"send_digest") as deliver:
            job.publish(store,report);job.publish(store,report)
            self.assertEqual([c.args[1] for c in deliver.call_args_list],["johnny-2026-11-24"]*2)
        self.assertIn("2026-11-20",store.put.call_args.args[1]["days"])

if __name__=="__main__":
    unittest.main()
