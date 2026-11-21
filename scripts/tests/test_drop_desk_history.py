import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import drop_desk_history as history
import price_drop_watch as watch


class DeskTests(unittest.TestCase):
    def setUp(self):
        self.t = {"player":"Liam Draxl","opponent":"Daniel Milavsky","league":"ATP Challenger Drummondville - R16",
                  "tour":"Challenger","start":"2026-11-19T23:30:00+00:00","binding":[1,5,7,8]}
        self.tours = {1:{"id":1,"date":"2026-11-16","name":"Drummondville Challenger"}}
        self.r = {"tour_id":1,"round_id":5,"date":"2026-11-20","winner_id":8,"loser_id":7,"result":"3-6 6-4 7-5"}
        self.now = datetime(2026,11,21,tzinfo=timezone.utc)

    def test_wta_result_requires_exact_singles_fixture_and_grades_locked_line(self):
        t={**self.t,"tour":"WTA 125","league":"WTA 125k Colina - SF","market":"totals","side":0,"line":20.5,"new":1.95}
        athletes=[{"id":"11","winner":True,"athlete":{"displayName":t["player"]},"linescores":[{"value":6},{"value":6}]},
                  {"id":"12","winner":False,"athlete":{"displayName":t["opponent"]},"linescores":[{"value":3},{"value":4}]}]
        game={"id":"79","date":t["start"],"venue":{"fullName":"Colina, Chile"},"round":{"displayName":"Semifinal"},
              "status":{"type":{"state":"post","name":"STATUS_FINAL","completed":True}},"competitors":athletes}
        group={"grouping":{"slug":"womens-singles"},"competitions":[game]}
        def result(tick,grp):
            return history.wta_result(tick,[{"id":"Colina-2026","groupings":[grp]}])
        self.assertEqual(result(t,group)[1]["result"],"Lost")
        self.assertEqual(result({**t,"market":"spreads","line":-3.5},group)[1]["profit"],0.95)
        self.assertEqual(result({**t,"market":"winner"},group)[1]["score"],"6-3 6-4")
        self.assertIsNone(result(t,{**group,"competitions":[game,game]}))
        self.assertIsNone(result(t,{**group,"grouping":{"slug":"womens-doubles"}}))
        self.assertIsNone(result({**t,"league":"WTA 125k Quito - SF"},group))
        self.assertIsNone(result({**t,"league":"WTA 125k Colina - QF"},group))

    def test_exact_round_and_ids_survive_utc_date_change(self):
        names = {7:"liam draxl",8:"daniel milavsky"}
        self.assertEqual(history.bind(self.t,self.tours,[],[self.r],names),[1,5,7,8])
        self.assertIsNone(history.bind(self.t,self.tours,[],[{**self.r,"round_id":9}],names))
        self.assertEqual(history.outcome(self.t,[self.r],[],self.now)["result"],"Lost")
        self.assertIsNone(history.outcome(self.t,[{**self.r,"date":"2026-11-22"}],[],self.now))
        self.assertIsNone(history.outcome(self.t,[self.r,{**self.r,"winner_id":7,"loser_id":8}],[],self.now))

    def test_void_incomplete_and_set_counts(self):
        self.assertEqual(history.outcome(self.t,[{**self.r,"result":"W/O"}],[],self.now)["result"],"Void")
        for score in ("6-1 2-0 ret.","6-0","6-2 6-3 0-6 6-1","6-4 5-2"):
            self.assertIsNone(history.outcome(self.t,[{**self.r,"result":score}],[],self.now))
        self.assertFalse(history.completed_score("6-4 6-4",3))
        self.assertTrue(history.completed_score("6-4 6-4 6-4",3))

    def test_tape_keeps_rebounds_and_unchanged_prices_and_orientation(self):
        tape = {"slots":{},"series":{}}
        for slot,minute,h,a,x,y in [("1515",22,"A","B",5.02,1.2),("1530",37,"B","A",1.18,5.25),("1545",52,"A","B",5.25,1.18)]:
            snap={"observed":f"2026-11-19T15:{minute}:00+00:00","events":{"1":{"id":"1","fixture":"u","start":"s",
                  "home":h,"away":a,"home_price":x,"away_price":y}}}
            history.append_snapshot(tape,slot,snap)
            history.append_snapshot(tape,slot,snap)
        data=tape["series"]["1|u|s"]["quotes"]
        self.assertEqual([r[1] for r in data],[5.02,5.25,5.25])

    def test_roundup_contains_both_actual_observation_dates(self):
        row = {**self.t,"event_id":"11","before":"2026-11-18T23:59:21+00:00","after":"2026-11-19T00:13:45+00:00","old":5.1,"new":5.02,"both_shortened":False}
        msg = watch.roundup_text([row],row["after"])
        self.assertIn("5.1 at 18 Nov 23:59:21 UTC",msg)
        self.assertIn("5.02 at 19 Nov 00:13:45 UTC",msg)
