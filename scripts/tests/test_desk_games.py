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

    def scan(self, last, minutes, price, line=22.5, reverse=False, present=True, start=None, cap=3000,
             tour="ATP", total_odds=None):
        row = dict(id="1",fixture="ab",home="A",away="B",home_price=price,away_price=2.01,
                   start=(start or self.t+timedelta(days=3)).isoformat(),tour=tour,league=tour+" Test - QF")
        if reverse:
            row.update(home="B",away="A",home_price=2.01,away_price=price)
        if present:
            row["contracts"] = desk_games.contracts(dict(home=row["home"],away=row["away"],
                totals={str(line):[price if total_odds is None else total_odds,2.01]},spreads={("3" if reverse else "-3"):([2.01,price] if reverse else [price,2.01])}))
        if cap is not None:
            row["match_period_limits"] = {"max_money_line": cap}
            for pair in row.get("contracts", {}).values():
                pair["reported_market_max"] = {"amount": cap}
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

    def test_earlier_alert_is_not_repeated_in_final_hour(self):
        start = self.t + timedelta(minutes=100)
        state,_ = self.scan({},0,2.5,start=start)
        state,b = self.scan(state,15,2.25,start=start)
        alerts = desk_games.alert_moves(b)
        self.assertEqual(len(alerts),1)
        self.assertFalse(any(m["detected_in_final_hour"] for m in alerts))
        self.assertIn("Pre-match tennis moves",roundup_text(alerts,b["observed"]))
        for minute, price in [(30,2.2),(45,2.0),(60,1.8)]:
            state,b = self.scan(state,minute,price,start=start)
            self.assertFalse(desk_games.alert_moves(b))

    def test_strict_threshold_and_final_hour_context(self):
        self.assertFalse(desk_games.alert_crossing(6.25,5))
        self.assertTrue(desk_games.alert_crossing(6.26,5))
        start = self.t + timedelta(minutes=70)
        state,_ = self.scan({},0,2.5,start=start)
        state,b = self.scan(state,15,2.2,start=start)
        alerts = desk_games.alert_moves(b)
        self.assertEqual(len(alerts),1)
        self.assertTrue(all(m["detected_in_final_hour"] and not m["wholly_in_final_hour"] for m in alerts))
        self.assertFalse(desk_games.alert_moves({**b, "policy":"same-line-4pp-final-hour-v2"}))

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
        state.pop("desk_match_issued")
        state["desk_issued"]["ab|winner|0"] = start.isoformat()
        state, batch = self.scan(state,15,2.0,start=start)
        self.assertFalse(desk_games.alert_moves(batch))
        self.assertEqual(len(batch["moves"]),3)

    def test_board_includes_low_limits_and_first_eligible_drop_is_sent_once(self):
        for cap in (None, 0, 50, 199.99):
            with self.subTest(cap=cap):
                state, _ = self.scan({}, 0, 3.0, cap=1500)
                state, low = self.scan(state, 15, 2.5, cap=cap)
                self.assertEqual(len(low["moves"]), 3)
                self.assertFalse(low["alert_ids"])
                state, flat = self.scan(state, 30, 2.5, cap=200)
                self.assertFalse(desk_games.alert_moves(flat))
                state, later = self.scan(state, 45, 2.3, cap=200)
                self.assertEqual(len(desk_games.alert_moves(later)), 1)
                for m in desk_games.alert_moves(later):
                    self.assertEqual(m["new"], 2.3)
                    self.assertEqual(m["alert_detection_limit"], {"amount": 200, "currency": "USD"})
                _, again = self.scan(state, 60, 2.1, cap=1000)
                self.assertFalse(again["alert_ids"])

    def test_delivery_rechecks_exact_market_cap_in_saved_batch(self):
        state, _ = self.scan({}, 0, 3, cap=50)
        _, batch = self.scan(state, 15, 2.5, cap=200)
        selected, = desk_games.alert_moves(batch)
        self.assertEqual(selected["market"], "spreads")
        self.assertEqual(len(batch["moves"]),3)
        self.assertFalse(desk_games.alert_moves(dict(batch, policy=desk_games.PRIOR_ALL_DAY_POLICY)))
        for invalid in (None, {"amount": 199.99, "currency": "USD"},
                        {"amount": 500, "currency": "EUR"}, {"amount": float("nan"), "currency": "USD"}):
            selected["alert_detection_limit"] = invalid
            self.assertEqual(desk_games.alert_moves(batch), [])

    def test_first_scan_dominates_later_stronger_or_opposite_move_on_either_tour(self):
        for tour in ("ATP","Challenger","WTA","WTA 125"):
            with self.subTest(tour=tour):
                state,_=self.scan({},0,2.5,tour=tour,total_odds=2.5)
                state,b=self.scan(state,15,2.22,tour=tour,total_odds=2.05)
                selected, = desk_games.alert_moves(b)
                self.assertEqual((selected["market"],selected["new"]),("totals",2.05))
                self.assertEqual(len(b["moves"]),3)
                for minutes,price,line in ((30,2.2,24),(45,1.65,24)):
                    state,b=self.scan(state,minutes,price,tour=tour,line=line,reverse=True)
                    self.assertEqual(desk_games.alert_moves(b),[])
                self.assertTrue(any(m.get("line")==24 for m in b["moves"]))

    def test_each_fixture_in_group_has_its_own_selection_and_old_batch_cannot_send(self):
        state,_=self.scan({},0,2.5)
        _,b=self.scan(state,15,2.2,total_odds=2.1)
        one, = desk_games.alert_moves(b)
        other = dict(one,fixture="cd",tour="WTA",move_id="other")
        combined=dict(b,moves=[*b["moves"],other],alert_ids=[m["move_id"] for m in b["moves"]]+["other"])
        self.assertEqual([m["move_id"] for m in desk_games.alert_moves(combined)],[one["move_id"],"other"])
        self.assertEqual(desk_games.alert_moves(dict(combined,policy=desk_games.PRIOR_LINE_POLICY)),[])
        self.assertEqual(desk_games.alert_moves(dict(combined,observed=self.t.isoformat())),[])

    def test_migrate_receipted_and_reserved_matches_including_reschedule(self):
        start = self.t+timedelta(days=2)
        state,_=self.scan({},0,2.5,start=start)
        state["desk_match_issued"]=desk_games.seed_match_alerts(
            {"desk_late_issued":{"other|winner|0":start.isoformat(),"ab|totals:23|1":start.isoformat()}})
        self.assertEqual(set(state["desk_match_issued"]),{"ab","other"})
        state,b=self.scan(state,15,2.,start=start)
        self.assertFalse(desk_games.alert_moves(b))
        postponed=start+timedelta(days=14)
        state,b=self.scan(state,30,2.3,start=postponed)
        self.assertEqual(state["desk_match_issued"]["ab"],postponed.isoformat())
        _,b=self.scan(state,45,1.8,start=postponed)
        self.assertFalse(desk_games.alert_moves(b))

    def test_dispatch_checks_confirmed_record_after_local_state_loss(self):
        state,_=self.scan({},0,2.5)
        _,b=self.scan(state,15,2.2,total_odds=2.1)
        winner,=desk_games.alert_moves(b)
        class Memory:
            def __init__(self,locks):
                self.locks=locks
            def get(self,path):
                return {"locks":{"telegram":self.locks}}
        self.assertEqual(desk_games.dispatch_moves(b,Memory({})),[winner])
        self.assertEqual(desk_games.dispatch_moves(b,Memory({"ab":{"move_id":"older"}})),[])
        self.assertEqual(desk_games.dispatch_moves(b,Memory({"ab":winner})),[winner])
        with self.assertRaises(RuntimeError):
            desk_games.dispatch_moves(b,Memory(None))

    def test_generic_games_cap_never_qualifies_an_alternate_line(self):
        self.assertIsNone(desk_games.market_limit({"games_period_limits":{"max_total":20000}},{"market":"totals"}))

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
