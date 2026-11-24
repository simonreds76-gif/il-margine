import hashlib
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import johnny_cards as job
from johnny_cards_calendar import competition, only_unrelated_omissions
from johnny_cards_review import Analyst, exact_choices, value_range

class Reader:
    def __init__(self, boards):
        self.boards=boards
        self.log=[]
        self.errors=0
    def read(self,name,args,_slot):
        self.log.append(args)
        return {"data":self.boards.get(args["startOfDay"], {"context":"no fixtures · times UTC","listedCount":0,"fixtureCount":0})}

class MethodTests(unittest.TestCase):
    def test_calendar_summer_utc_and_started(self):
        start=int(job.utc("2027-05-22T10:00:00Z").timestamp())
        doc={"context":"times UTC","fixtureCount":3,"listedCount":3,
             "fixturesSummary":"Premier League (England) [competitionId league.0z9xjh1]:\n- 14:00 A v B (id a.1)\n- 10:30 C 1-0 D, live (id c.2)\nSerie B (Italy) [competitionId serie-b.3]:\n- 18:00 X v Y (id other.3)"}
        overnight={"context":"times UTC","fixtureCount":1,"listedCount":1,
                   "fixturesSummary":"Primera A (Colombia) [competitionId col.123]:\n- 01:20 Club A v Club B (id game.4)"}
        board=Reader({start:doc,start+14*3600:overnight})
        games,coverage=job.calendar(board,"2027-05-22",job.utc("2027-05-22T11:05:00Z"))
        self.assertEqual([f["ko"] for f in games],["2027-05-22T14:00:00+00:00","2027-05-23T01:20:00+00:00"])
        self.assertEqual(games[1]["competitionId"],"col.123")
        self.assertTrue(all(not l["gap"] for l in coverage))
        self.assertEqual(board.log[0]["startOfDay"], start)
        self.assertEqual(board.log[-1]["endOfDay"],start+86400)

    def test_partial_and_omitted_rows(self):
        now=job.utc("2026-11-24T11:00:00Z")
        reader=Reader({int(now.timestamp()):{}})
        self.assertTrue(any(x["gap"] for x in job.calendar(reader,now.date().isoformat(),now)[1]))
        d={"notListed":"2 more fixtures in 1 competition: Championship (England) [competitionId c.123] 2; end"}
        self.assertTrue(only_unrelated_omissions(d,2))
        self.assertFalse(only_unrelated_omissions(d,3))
        self.assertFalse(only_unrelated_omissions({"notListed":d["notListed"].replace("(England)","(Brazil)")},2))

    def test_competition_scope(self):
        for country in ("Brazil","South America","Argentina","Bolivia","Guyana","Suriname","French Guiana"):
            self.assertIsNotNone(competition("Example",country,"example.123"))
        self.assertIsNotNone(competition("UEFA Champions League","Europe","ucl.123"))
        self.assertIsNone(competition("AFC Champions League Elite","Asia","afc.123"))

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
        self.assertEqual(len(board["calendar"]),2)
        analyst.select_players.assert_not_called()

    def test_retries_have_same_delivery_key(self):
        report={"day":"2026-11-24","at":"2026-11-24T11:00:00Z","failures":0,
                "slate":[],"calendar":[{"gap":"","league":l} for l in ["test window"]]}
        store=Mock();store.get.return_value={"days":{"2026-11-20":{"policy":"old"}}}
        with patch.object(job,"send_digest") as deliver:
            job.publish(store,report);job.publish(store,report)
            self.assertEqual([c.args[1] for c in deliver.call_args_list],["johnny-2026-11-24"]*2)
        self.assertIn("2026-11-20",store.put.call_args_list[0].args[1]["days"])

    def test_recovery_edits_the_acknowledged_message(self):
        report={"day":"2026-11-24","at":"2026-11-24T17:00:00Z","failures":0,
                "slate":[],"calendar":[{"gap":"","league":"test window"}]}
        store=Mock()
        store.get.side_effect=[{"days":{}},{"state":"sent","message_id":17}]
        with patch.object(job,"telegram_private",return_value=("https://example.test","chat")), \
             patch.object(job.http,"post") as post, patch.object(job,"send_digest") as send:
            job.publish(store,report)
            self.assertEqual(post.call_args.kwargs["json"]["message_id"],17)
            self.assertTrue(post.call_args.args[0].endswith("/editMessageText"))
            send.assert_not_called()

if __name__=="__main__":
    unittest.main()
