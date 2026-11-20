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
        self.removed=[]
        self.store=type("Storage",(),{"put":lambda s,k,v,replace:True})()
    def check(self):
        def edit(chat,mid,text,kind):
            self.edits.append((chat,mid,text))
            return "edited",kind
        return expiry.reconcile(self.store,self.state,self.latest,self.now,get_chat=lambda:"private",
            edit=edit,remove=lambda chat,mid:self.removed.append((chat,mid)),pause=lambda _:None)
    def test_partial_then_closed_in_original_message(self):
        self.check()
        self.assertEqual(len(self.edits),1)
        self.assertNotIn("Player 0",self.edits[0][2])
        self.assertIn("Player 1",self.edits[0][2])
        self.check()
        self.assertEqual(len(self.edits),1)
        self.now+=timedelta(hours=1)
        self.check()
        self.check()
        self.assertEqual([row[1] for row in self.edits],[882])
        self.assertEqual(self.removed,[("private",882)])
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
        self.assertEqual(self.edits,[])
        self.assertEqual(self.removed,[("private",882)])
    def test_stale_board_hides_unconfirmed_picks(self):
        self.latest["observed"]=(self.now-timedelta(minutes=20)).isoformat()
        self.check()
        self.assertIn("current quotes unavailable",self.edits[0][2])
        self.assertIn("Player 1",self.edits[0][2])
        self.assertNotIn("Player 0",self.edits[0][2])
        self.assertFalse(self.removed)
        self.assertEqual(self.state["messages"]["882"]["closed"],["0"])
        self.check()
        self.assertEqual(len(self.edits),1)
        self.latest["observed"]=self.now.isoformat()
        self.check()
        self.assertEqual(self.state["messages"]["882"]["visible"],["1"])

    def test_telegram_removal_uses_only_original_id_and_requires_ack(self):
        from unittest.mock import patch
        with patch.object(expiry,"telegram",return_value=True) as api:
            expiry.remove_roundup("private",882)
            api.assert_called_once_with("deleteMessages",{"chat_id":"private","message_ids":[882]})
        with patch.object(expiry,"telegram",return_value=False), self.assertRaises(RuntimeError):
            expiry.remove_roundup("private",882)

    def test_failed_removal_can_retry_without_sending_or_editing(self):
        from unittest.mock import Mock
        self.now+=timedelta(hours=1)
        _,_,failed=expiry.reconcile(self.store,self.state,self.latest,self.now,get_chat=lambda:"private",
            edit=Mock(side_effect=AssertionError),remove=Mock(side_effect=RuntimeError))
        self.assertEqual(failed,["882"])
        self.check()
        self.assertEqual(self.removed,[("private",882)])
        self.assertFalse(self.edits)

    def test_expiry_after_delete_window_keeps_dated_record_in_place(self):
        self.state["messages"]["882"]["delivered_at"]=(self.now-timedelta(hours=48)).isoformat()
        self.now+=timedelta(hours=1)
        self.check()
        self.assertFalse(self.removed)
        self.assertIn("Historical prices at detection",self.edits[0][2])
        self.assertIn("Player 0",self.edits[0][2])
        self.assertFalse(self.state["messages"])

    def test_migration_recovers_only_recent_fully_started_messages(self):
        from unittest.mock import patch
        opened = self.state["messages"]["882"]
        def discover(store,recent,now):
            for mid in ("882","901","902","903"):
                recent["messages"][mid]=deepcopy(opened)
            for mid in ("901","902"):
                recent["messages"][mid]["moves"]=[self.moves[0]]
            recent["messages"]["902"]["delivered_at"]=(now-timedelta(hours=48)).isoformat()
        with patch.object(expiry,"discover",side_effect=discover):
            expiry.recover_closed_notices(self.store,self.state,self.now)
        self.assertTrue(self.state["silent_expiry"])
        self.assertIs(self.state["messages"]["882"],opened)
        self.assertEqual(set(self.state["messages"]),{"882","901"})
        self.check()
        self.assertEqual(self.removed,[("private",901)])
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
        def captured(events, t=when):
            return p.board_rows({"sport_id":2,"events":events},t)["events"]["100"].get("contracts",{})
        lines=captured([match,games])
        self.assertEqual(set(lines),{"totals:22.5","spreads:2.5"})
        self.assertEqual(lines["totals:22.5"]["prices"],[1.91,1.97])
        self.assertEqual(lines["spreads:2.5"]["prices"],[2.0,1.9])
        self.assertFalse(captured([match,{**games,"parent_id":999}]))
        self.assertFalse(captured([match,games,games]))
        self.assertEqual(lines,captured([match,games],when+timedelta(minutes=30)))

    def test_implied_change_and_actual_interval(self):
        from price_drop_watch import roundup_text
        text=roundup_text([self.moves[0]],self.moves[0]["after"])
        self.assertIn("Price-implied probability +3.56pp over 15m 59s",text)
        self.assertIn("1h 37m to scheduled start at detection",text)
        self.assertNotIn("sharp",text.lower())
