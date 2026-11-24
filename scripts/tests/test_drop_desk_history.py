import sys
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import drop_desk_history as history
import price_drop_watch as watch


class DeskTests(unittest.TestCase):
    def test_registered_draw_grades_only_a_bound_unique_opening_round(self):
        t={"binding":[17,4,11,12],"player":"Player One","opponent":"Player Two","league":"ATP Challenger Playford - R1",
           "tour":"Challenger","start":"2026-11-24T05:00:00Z","market":"spreads","line":-3.5,"new":2.25}
        schedule=[{"tour_id":17,"round_id":4,"player1_id":12,"player2_id":11,"result":""}]
        now=history.utc("2026-11-24T10:00:00Z")
        archive=({("player one","player two"):("player one","6-4 6-4")},"hash")
        with patch("desk_draw_scores.event_ids",return_value={"playford":7586}), patch("desk_draw_scores.load_draw",return_value=archive):
            grade=history.official_draw_outcome(t,[],schedule,now)
            self.assertEqual((grade["result"],grade["profit"],grade["draw_sha256"]),("Won",1.25,"hash"))
            for rejected,rows in ((dict(t,league="ATP Challenger Playford - Q1"),schedule),(dict(t,binding=None),schedule),
                                  (dict(t,opponent="Someone Else"),schedule),(t,2*schedule),(t,[dict(schedule[0],result="3-2")])):
                self.assertIsNone(history.official_draw_outcome(rejected,[],rows,now))
            self.assertIsNone(history.official_draw_outcome(t,[],schedule,history.utc(t["start"])))

    def test_draw_parser_requires_exact_city_week_players_winner_column_and_complete_score(self):
        from desk_draw_scores import draw_results
        from datetime import date
        def block(x,y,right,value): return (x,y,right,y+6,value)
        blocks=[block(20,20,300,"Playford, Australia\n23 November — 29 November 2026 | Challenger 75"),
                block(350,50,500,"Main Draw Singles")]
        for i in range(1,33):
            name={1:"ONE, Player",2:"TWO, Player"}.get(i,"OTHER, Entrant"+str(i))
            blocks.append(block(20,80+14*i,150,f"{i}\n{name}\nAUS"))
        result=[block(160,95,200,"P. One"),block(160,108,199,"63 764")]
        key=("player one","player two")
        day=date(2026,11,24)
        self.assertEqual(draw_results(blocks+result,"playford",day)[key],("player one","6-3 7-6(4)"))
        for docs,city,when in [(blocks+result,"other",day),(blocks+result,"playford",date(2026,11,30)),
                              (blocks+[result[0]],"playford",day),(blocks+result+[result[0]],"playford",day),
                              (blocks+[result[0],block(160,108,199,"63 32")],"playford",day)]:
            self.assertNotIn(key,draw_results(docs,city,when))

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
        for score in ("6-0","6-2 6-3 0-6 6-1","6-4 5-2","ret.","5-4 2-0 RET"):
            self.assertIsNone(history.outcome(self.t,[{**self.r,"result":score}],[],self.now))
        self.assertFalse(history.completed_score("6-4 6-4",3))
        self.assertTrue(history.completed_score("6-4 6-4 6-4",3))

    def test_unnumbered_board_does_not_bind_another_week_or_ambiguous_edition(self):
        t = dict(self.t, league="ATP Challenger Test City - R16")
        tour = dict(self.tours[1], name="Test City 2 Challenger")
        names = {7:"liam draxl", 8:"daniel milavsky"}
        self.assertEqual(history.bind(t,{1:tour},[],[self.r],names),[1,5,7,8])
        self.assertIsNone(history.bind(dict(t,league="ATP Challenger Test City 3 - R16"),{1:tour},[],[self.r],names))
        self.assertIsNone(history.bind(t,{1:tour},[],[dict(self.r,date="2026-11-13")],names))
        self.assertIsNone(history.bind(t,{1:tour,2:tour},[],[self.r,dict(self.r,tour_id=2)],names))

    def test_reviewed_alias_requires_both_players_and_registered_id_and_name(self):
        t = dict(self.t,player="Herbert Jody Maginley")
        r = dict(self.r,loser_id=36878)
        names = {36878:"jody maginley",8:"daniel milavsky"}
        self.assertEqual(history.bind(t,self.tours,[],[r],names),[1,5,36878,8])
        self.assertIsNone(history.bind(t,self.tours,[],[dict(r,loser_id=7)],{7:"jody maginley",8:names[8]}))
        self.assertIsNone(history.bind(t,self.tours,[],[r],{**names,36878:"another player"}))
        self.assertIsNone(history.bind(dict(t,opponent="Changed Player"),self.tours,[],[r],names))

    def test_private_draw_grades_only_the_verified_pair_after_start(self):
        t = dict(self.t,start="2026-11-24T01:00:00Z",market="spreads",line=2.5,new=1.9)
        now = datetime(2026,11,24,10,tzinfo=timezone.utc)
        key = (t["league"],history.utc(t["start"]),tuple(sorted((t["player"],t["opponent"]))))
        row = dict(self.r,date="2026-11-24",result="6-3 6-2")
        with patch.object(history,"draw_review",return_value={key:{"row":row}}):
            self.assertEqual(history.outcome(t,[],[],now)["result"],"Lost")
            self.assertIsNone(history.outcome(t,[],[],history.utc(t["start"])))
            self.assertIsNone(history.outcome(dict(t,binding=[1,5,7,9]),[],[],now))
            self.assertIsNone(history.outcome(t,[dict(row,result="4-2")],[],now))
            self.assertIsNone(history.outcome(dict(t,opponent="Other"),[],[],now))

    def test_original_opponent_replaced_requires_verified_replacement_fixture(self):
        t = dict(self.t,start="2026-11-22T14:00:00Z",binding=None)
        now = datetime(2026,11,24,10,tzinfo=timezone.utc)
        key = (t["league"],history.utc(t["start"]),tuple(sorted((t["player"],t["opponent"]))))
        review = {"replaced":{"tour_id":1,"round_id":5,"player":7,"original":8,"replacement":9}}
        actual = dict(self.r,winner_id=7,loser_id=9,date="2026-11-22")
        with patch.object(history,"draw_review",return_value={key:review}):
            self.assertEqual(history.outcome(t,[actual],[],now)["result"],"Void")
            self.assertIsNone(history.outcome(t,[],[],now))
            self.assertIsNone(history.outcome(t,[actual,self.r],[],now))

    def test_retirement_set_and_official_winner_including_disqualification(self):
        for score in ("6-2 3-0 RET","4-6 0-1 ret.","7-6(4) DEF.","6-7(5) 3-0 disqualified"):
            row = {**self.r, "result":score}
            self.assertEqual(history.outcome(self.t,[row],[],self.now)["result"],"Lost")
            self.assertEqual(history.outcome({**self.t,"binding":[1,5,8,7]},[row],[],self.now)["result"],"Won")
            for market in ("spreads","totals"):
                self.assertEqual(history.outcome({**self.t,"market":market},[row],[],self.now)["settled_stake"],0)
        for score in ("6-5 RET","6-6 RET","0-0 ret.","5-4 defaulted"):
            self.assertEqual(history.outcome(self.t,[{**self.r,"result":score}],[],self.now)["result"],"Void")
        self.assertIsNone(history.outcome(self.t,[{**self.r,"result":"8-1 RET"}],[],self.now))
        self.assertEqual(history.retirement_grade({"league":"ATP Next Gen Finals"},"3-4 2-1 RET",True)["result"],"Won")

    def test_wta_retirement_with_missing_or_partial_sets(self):
        t={**self.t,"tour":"WTA","league":"WTA Colina - SF","market":"winner"}
        game={"id":"79","date":t["start"],"venue":{"fullName":"Colina, Chile"},"round":{"displayName":"Semifinal"},
              "status":{"type":{"state":"post","name":"STATUS_RETIRED","completed":True}}}
        def result(first,second,winner=True):
            game["competitors"]=[{"id":str(i),"winner":won,"athlete":{"displayName":name},
                                  "linescores":[{"value":n} for n in values]}
                                 for i,(won,name,values) in enumerate(((winner,t["player"],first),(False,t["opponent"],second)))]
            return history.wta_result(t,[{"id":"1","groupings":[{"grouping":{"slug":"womens-singles"},"competitions":[game]}]}])
        self.assertEqual(result([2,0,0],[6,2,0])[1]["result"],"Won")
        self.assertEqual(result([5],[3])[1]["result"],"Void")
        self.assertIsNone(result([],[]))
        self.assertIsNone(result([6],[1],winner=False))

    def test_tape_keeps_rebounds_and_unchanged_prices_and_orientation(self):
        tape = {"slots":{},"series":{}}
        for slot,minute,h,a,x,y in [("1515",22,"A","B",5.02,1.2),("1530",37,"B","A",1.18,5.25),("1545",52,"A","B",5.25,1.18)]:
            snap={"observed":f"2026-11-19T15:{minute}:00+00:00","events":{"1":{"id":"1","fixture":"u","start":"s",
                  "home":h,"away":a,"home_price":x,"away_price":y}}}
            history.append_snapshot(tape,slot,snap)
            history.append_snapshot(tape,slot,snap)
        data=tape["series"]["1|u|s"]["quotes"]
        self.assertEqual([r[1] for r in data],[5.02,5.25,5.25])

    def test_existing_tape_adds_observed_limits_even_if_odds_stay_flat(self):
        tape = {"slots":{}, "series":{}}
        for i, cap in enumerate([500, 1500, 0, None]):
            slot = f"slot{i}"
            row = {"id":"1", "fixture":"ab", "start":"start", "home":"A", "away":"B", "home_price":2, "away_price":2}
            snap = {"observed":str(i), "events":{"1":row}}
            history.append_snapshot(tape, slot, snap)
            del tape["limit_slots"][slot]  # Simulate the price-only projection from the old version.
            if cap is not None:
                row["match_period_limits"] = {"max_money_line":cap}
            history.append_snapshot(tape, slot, snap)
            history.append_snapshot(tape, slot, snap)
        series = tape["series"]["1|ab|start"]
        self.assertEqual(len(series["quotes"]),4)
        self.assertEqual([v["amount"] for v in series["limits"].values()],[500,1500,0])
        self.assertTrue(all(v["currency"] == "USD" for v in series["limits"].values()))

    def test_roundup_contains_both_actual_observation_dates(self):
        row = {**self.t,"event_id":"11","before":"2026-11-18T23:59:21+00:00","after":"2026-11-19T00:13:45+00:00","old":5.1,"new":5.02,"both_shortened":False}
        msg = watch.roundup_text([row],row["after"])
        self.assertIn("5.1 at 18 Nov 23:59:21 UTC",msg)
        self.assertIn("5.02 at 19 Nov 00:13:45 UTC",msg)
