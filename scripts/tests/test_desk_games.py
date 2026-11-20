from datetime import timedelta
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import desk_games
import drop_desk_expiry as expiry
import drop_desk_history as history
import pinnradar_tennis as pilot
from price_drop_watch import roundup_text


class GamesDesk(unittest.TestCase):
    t = pilot.utc("2026-11-19T19:00:00Z")

    def scan(self, last, minutes, price, line=22.5, reverse=False, present=True, start=None):
        row = dict(id="1",fixture="ab",home="A",away="B",home_price=price,away_price=2.01,
                   start=(start or self.t+timedelta(days=3)).isoformat(),tour="ATP",league="ATP Test - QF")
        if reverse:
            row.update(home="B",away="A",home_price=2.01,away_price=price)
        if present:
            row["contracts"] = desk_games.contracts(dict(home=row["home"],away=row["away"],
                totals={str(line):[price,2.01]},spreads={("3" if reverse else "-3"):([2.01,price] if reverse else [price,2.01])}))
        snap={"observed":(self.t+timedelta(minutes=minutes)).isoformat(),"events":{"1":row}}
        state,_=pilot.advance(last,snap,track_first=False)
        batch=desk_games.compare(last,snap,state,set())
        return state,batch

    def test_overnight_cumulative_crossing_stays_on_board(self):
        state, _=self.scan({},0,2.2)
        state, first=self.scan(state,15,2.13)
        self.assertEqual(first["alert_ids"],[])
        state,batch=self.scan(state,16*60,2.,reverse=True)
        self.assertEqual(batch["alert_ids"],[])
        self.assertEqual({(m["selection"],m["old"],m["new"]) for m in batch["moves"]},
                         {("A",2.2,2.),("A -3 games",2.2,2.),("Over 22.5 games",2.2,2.)})
        self.assertTrue(all(m["before"]==self.t.isoformat() for m in batch["moves"]))
        self.assertIn("Over 22.5 games",roundup_text(batch["moves"],batch["observed"]))
        state,again=self.scan(state,16*60+15,1.92)
        self.assertTrue(again["moves"])
        self.assertFalse(again["alert_ids"])

    def test_final_hour_rebases_after_earlier_move_then_alerts_once(self):
        start = self.t + timedelta(minutes=90)
        state, _ = self.scan({}, 0, 2.9, start=start)
        state, early = self.scan(state, 15, 2.3, start=start)
        self.assertTrue(early["moves"])
        self.assertFalse(desk_games.alert_moves(early))
        state, boundary = self.scan(state, 30, 2.2, start=start)
        self.assertFalse(boundary["alert_ids"])
        state, small = self.scan(state, 45, 2.1, start=start)
        self.assertFalse(small["alert_ids"])
        state, batch = self.scan(state, 60, 2.0, reverse=True, start=start)
        alerts = desk_games.alert_moves(batch)
        self.assertEqual({m["selection"] for m in alerts}, {"A", "A -3 games", "Over 22.5 games"})
        self.assertTrue(all(m["old"] == 2.2 and m["before"] == boundary["observed"] for m in alerts))
        self.assertIn("Final-hour", roundup_text(alerts, batch["observed"]))
        state, repeat = self.scan(state, 75, 1.8, start=start)
        self.assertTrue(repeat["moves"])
        self.assertFalse(repeat["alert_ids"])
        self.assertFalse(desk_games.alert_moves({**batch, "policy":"same-line-4pp-prematch-v1"}))
        self.assertFalse(desk_games.alert_moves({**batch, "moves":[dict(m, before=early["observed"]) for m in alerts]}))

    def test_line_absence_gap_and_start_reset_late_signal(self):
        start = self.t + timedelta(hours=1)
        state, _ = self.scan({},0,2.5,start=start)
        state, _ = self.scan(state,15,2.5,present=False,start=start)
        state, batch = self.scan(state,30,2.,start=start)
        self.assertEqual([m["market"] for m in desk_games.alert_moves(batch)],["winner"])
        state, batch = self.scan(state,60,1.5,start=start)
        self.assertFalse(batch["alert_ids"])
        state, _ = self.scan({},0,2.5,start=start)
        state, gap = self.scan(state,45,2.,start=start)
        self.assertFalse(gap["alert_ids"])

    def test_existing_issued_contracts_remain_deduplicated_on_upgrade(self):
        start = self.t + timedelta(hours=1)
        state, _ = self.scan({},0,2.5,start=start)
        state.pop("desk_late_issued")
        state["desk_issued"]["ab|winner|0"] = start.isoformat()
        state, batch = self.scan(state,15,2.0,start=start)
        self.assertEqual({m["market"] for m in desk_games.alert_moves(batch)},{"spreads","totals"})

    def test_changed_line_or_start_never_compared(self):
        state,_=self.scan({},0,2.5)
        state,b=self.scan(state,15,1.7,line=23.5)
        self.assertFalse(any(m["market"]=="totals" for m in b["moves"]))
        state,b=self.scan(state,30,1.5,start=self.t+timedelta(days=2))
        self.assertFalse(b["moves"])

    def test_closed_line_unavailable_and_walkover_void(self):
        state,_=self.scan({},0,2.4)
        state,b=self.scan(state,15,1.8)
        ticket=next(m for m in b["moves"] if m["market"]=="totals")
        state,_=self.scan(state,30,1.8,present=False)
        self.assertEqual(expiry.eligibility(ticket,state,self.t+timedelta(minutes=30)),"unavailable")
        self.assertEqual(history.outcome({**ticket,"binding":[1,9,2,3]},[],
            [{"tour_id":1,"round_id":9,"player1_id":2,"player2_id":3,"result":"wo"}],self.t+timedelta(days=5))["result"],"Void")

    def test_games_graded_at_issued_line_and_price(self):
        ticket={"new":2.25,"side":0}
        for market,line,side,won,label,pl in [
            ("spreads",-2,0,True,"Push",0),("spreads",2.5,1,False,"Won",1.25),
            ("spreads",-3,0,True,"Lost",-1),("totals",26,0,False,"Push",0),
            ("totals",26.25,0,True,"Half lost",-0.5),("totals",25.75,0,True,"Half won",0.625),
            ("totals",26.5,1,False,"Won",1.25)]:
            g=desk_games.grade({**ticket,"market":market,"line":line,"side":side},[(7,6),(7,6)],won)
            self.assertEqual((g["result"],g["profit"],g["settled_stake"]),(label,pl,1))
