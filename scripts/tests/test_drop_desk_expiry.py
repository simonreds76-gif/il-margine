import sys, unittest
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import drop_desk_expiry as expiry
from pinnradar_tennis import utc


class ExpiryTests(unittest.TestCase):
    def setUp(self):
        self.now=utc("2026-11-19T17:00:00Z")
        self.moves=[{"event_id":str(i),"fixture":"f"+str(i),"move_id":str(i),"start":t,"league":"ATP Test","player":"Player "+str(i),"opponent":"Other "+str(i),
            "before":"2026-11-19T15:06:23Z","after":"2026-11-19T15:22:22Z","old":2.13,"new":1.98,"both_shortened":False}
            for i,t in enumerate(("2026-11-19T17:00:00Z","2026-11-19T18:00:00Z"))]
        self.latest={"observed":(self.now-timedelta(minutes=5)).isoformat(),"events":{m["event_id"]:{"fixture":m["fixture"],"start":m["start"],"home":m["player"],"away":m["opponent"]} for m in self.moves}}
        self.state={"messages":{"882":{"observed":self.moves[0]["after"],"moves":self.moves,"visible":["0","1"],"closed":[],"kind":"text"}}}
        self.edits=[]
        self.store=type("Storage",(),{"put":lambda s,k,v,replace:True})()
    def check(self):
        def edit(chat,mid,text,kind):
            self.edits.append((chat,mid,text))
            return "edited",kind
        return expiry.reconcile(self.store,self.state,self.latest,self.now,get_chat=lambda:"private",edit=edit,pause=lambda _:None)
    def test_partial_then_closed_in_original_message(self):
        self.check()
        self.assertEqual(len(self.edits),1)
        self.assertNotIn("Player 0",self.edits[0][2])
        self.assertIn("Player 1",self.edits[0][2])
        self.check()
        self.assertEqual(len(self.edits),1)
        self.now+=timedelta(hours=1)
        self.check()
        self.assertIn("Roundup closed",self.edits[1][2])
        self.assertEqual([row[1] for row in self.edits],[882,882])
        self.assertEqual(self.state["messages"],{})
    def test_early_suspension_is_distinct_from_start_and_recovers(self):
        self.now-=timedelta(seconds=1)
        row=self.latest["events"].pop("0")
        self.check()
        self.assertEqual(self.state["messages"]["882"]["closed"],[])
        self.latest["events"]["0"]=row
        self.check()
        self.assertIn("Player 0",self.edits[-1][2])
    def test_retimed_identity_does_not_revive_old_alert(self):
        self.latest["events"]["1"]["start"]="2026-11-20T18:00:00Z"
        self.check()
        self.assertFalse(self.state["messages"])
        self.assertIn("Roundup closed",self.edits[0][2])
    def test_stale_board_hides_unconfirmed_picks(self):
        self.latest["observed"]=(self.now-timedelta(minutes=20)).isoformat()
        self.check()
        self.assertIn("No selections currently",self.edits[0][2])
        self.assertEqual(self.state["messages"]["882"]["closed"],["0"])
    def test_explicit_in_play_evidence_overrides_stale_prematch_row(self):
        import pinnradar_tennis as p
        from test_pinnradar_tennis import event,START
        a=event()
        for live in ({**a,"event_type":"live"},{**a,"event_id":222,"event_type":"live","home":a["away"],"away":a["home"]}):
            for seq in ([a,live],[live,a]):
                board=p.board_rows({"sport_id":2,"events":seq},START-timedelta(minutes=40))
                self.assertEqual(board["events"],{})
                self.assertEqual(board["excluded"]["confirmed_in_play"],1)
                started,_=p.advance({},board)
                later=p.board_rows({"sport_id":2,"events":[a]},START-timedelta(minutes=35))
                still_closed,_=p.advance(started,later)
                self.assertFalse(still_closed["events"])

    def test_edit_failure_does_not_block_other_roundups_or_commit_failed_edit(self):
        self.state["messages"]["883"]=deepcopy(self.state["messages"]["882"])
        def edit(chat,mid,text,kind):
            if mid==882:raise RuntimeError("temporary failure")
            return "edited",kind
        _, n, failed=expiry.reconcile(self.store,self.state,self.latest,self.now,
            get_chat=lambda:"private",edit=edit,pause=lambda _:None)
        self.assertEqual((n,failed),(1,["882"]))
        self.assertEqual(self.state["messages"]["882"]["visible"],["0","1"])
        self.assertEqual(self.state["messages"]["883"]["visible"],["1"])

    def test_no_send_when_start_passes_during_destination_check(self):
        from price_drop_watch import deliver
        seen=self.now-timedelta(seconds=35)
        move={**self.moves[0],"start":(self.now+timedelta(seconds=1)).isoformat()}
        mem=type("Read",(),{"get":lambda self,k:None})()
        self.assertEqual(deliver({"observed":seen.isoformat(),"moves":[move]},mem,now=seen,
            get_chat=lambda:"private",dispatch_clock=lambda:self.now),"quiet")

    def test_games_slice(self):
        import os
        from unittest.mock import patch
        from test_pinnradar_tennis import event,START
        import pinnradar_tennis as p
        match=event()
        when=START-timedelta(minutes=45)
        period={"number":0,"status":"open","spreads":{"-2.5":{"hdp":-2.5,"home":1.9,"away":2.0}},
            "totals":{"22.5":{"points":22.5,"over":1.91,"under":1.97},"2.5":{"points":2.5,"over":2.2,"under":1.71}}}
        games=event(200,home=match["home"]+" (Games)",away=match["away"]+" (Games)",parent_id=100,periods={"num_0":period})
        with patch.dict(os.environ,{"DROP_SHOT_GAMES_AUDIT_FROM":when.isoformat()}):
            snap=lambda events,t=when:p.board_rows({"sport_id":2,"events":events},t)
            candidate=snap([match,games])["games_market_sample"]["100"]
            self.assertEqual(candidate["totals"],{"22.5":[1.91,1.97]})
            self.assertEqual(candidate["spreads"],{"-2.5":[1.9,2.0]})
            self.assertFalse(snap([match,{**games,"parent_id":999}])["games_market_sample"])
            self.assertFalse(snap([match,games,games])["games_market_sample"])
            self.assertNotIn("games_market_sample",snap([match,games],when+timedelta(minutes=30)))
    def test_implied_change_and_actual_interval(self):
        from price_drop_watch import roundup_text
        text=roundup_text([self.moves[0]],self.moves[0]["after"])
        self.assertIn("Price-implied probability +3.56pp over 15m 59s",text)
        self.assertIn("1h 37m to scheduled start at detection",text)
        self.assertNotIn("sharp",text.lower())
