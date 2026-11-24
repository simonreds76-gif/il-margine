import sys
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pinnradar_tennis as pilot
import price_drop_watch as watch

START=pilot.utc("2026-11-19T12:00:00Z")

def event(event_id=100, **kw):
    e=dict(sport_id=2,event_id=event_id,league_name="ATP Challenger Helsinki - Qualifiers",
           home="Test Home",away="Test Away",starts=START.isoformat(),event_type="prematch",is_have_odds=True,
           periods={"num_0":{"number":0,"status":"open","money_line":{"home":2.30,"away":1.65}}})
    return {**e, **kw}

def snap(events,minutes):
    return pilot.board_rows({"sport_id":2,"events":events},START-timedelta(minutes=minutes))

class ReportStorageTest(unittest.TestCase):
    report = "presentation/drop-paper-v1/first-match-v1/state.json"

    def test_transient_report_failure_retries_same_payload_once(self):
        for first in (Mock(status_code=520), pilot.requests.Timeout()):
            with self.subTest(first=first), patch.object(pilot.time, "sleep") as sleep:
                store = pilot.Store.__new__(pilot.Store)
                store.request = Mock(side_effect=[first, Mock(status_code=200)])
                self.assertTrue(store.put(self.report, {"through": "09:52"}, replace=True))
                one, two = store.request.call_args_list
                self.assertEqual(one, two)
                sleep.assert_called_once()

    def test_claims_and_permanent_failures_are_not_retried(self):
        for path, replace, status in (("attempts/test", False, 520), ("drop-deliveries-v2/test", True, 520),
                                      (self.report, True, 403)):
            with self.subTest(path=path):
                store = pilot.Store.__new__(pilot.Store)
                store.request = Mock(return_value=Mock(status_code=status))
                with self.assertRaisesRegex(RuntimeError, str(status)):
                    store.put(path, {}, replace=replace)
                store.request.assert_called_once()

    def test_persistent_failure_remains_visible(self):
        store = pilot.Store.__new__(pilot.Store)
        store.request = Mock(return_value=Mock(status_code=520))
        with patch.object(pilot.time, "sleep"), self.assertRaisesRegex(RuntimeError, "520"):
            store.put(self.report, {}, replace=True)
        self.assertEqual(store.request.call_count, 2)


class ClockTest(unittest.TestCase):
    def test_only_the_requested_utc_quarter_can_run(self):
        now = pilot.utc("2026-11-19T15:29:59Z")
        slot = pilot.utc("2026-11-19T15:15:00Z")
        for requested in (None, "", "2026-11-19T15:15:00Z"):
            self.assertEqual(pilot.requested_quarter(now, requested), slot)
        for requested in ("2026-11-19T15:00:00Z", "2026-11-19T15:30:00Z"):
            self.assertIsNone(pilot.requested_quarter(now, requested))
        for requested in ("bad", "2026-11-19T15:14:00Z", "2026-11-19T15:15:01Z"):
            with self.assertRaises(ValueError):
                pilot.requested_quarter(now, requested)

    def test_expired_dispatch_does_no_io(self):
        from unittest.mock import patch
        with patch.dict(pilot.os.environ, DROP_SHOT_SCHEDULED_SLOT="2000-01-01T00:00:00Z"):
            with patch.object(pilot, "Store", side_effect=AssertionError("unexpected access")):
                pilot.run()


class MatchWinnerTest(unittest.TestCase):
    def test_limits_follow_exact_line_through_reversal_without_period_fallback(self):
        parent = event(201, home="Zulu", away="Alpha")
        parent["periods"]["num_0"]["meta"] = {"max_moneyline": 1200}
        games = event(202, home="Zulu (Games)", away="Alpha (Games)", parent_id=201,
                      periods={"num_0":{"status":"open","meta":{"max_total":3500},
                               "spreads":{"-2.5":{"hdp":-2.5,"home":1.9,"away":2,"max":"100"},
                                          "-1.5":{"hdp":-1.5,"home":1.8,"away":2}},
                               "totals":{"21.5":{"points":21.5,"over":1.9,"under":2,"max":0,"currency":"USD"}}}})
        row = snap([parent, games], 30)["events"]["201"]
        markets = dict(pilot.desk_games.pairs(row))
        self.assertEqual(markets["spreads:2.5"]["reported_market_max"], {"amount":100})
        self.assertEqual(markets["totals:21.5"]["reported_market_max"], {"amount":0,"currency":"USD"})
        self.assertNotIn("reported_market_max", markets["spreads:1.5"])
        self.assertNotIn("reported_market_max", markets["winner"])
        self.assertEqual(row["match_period_limits"], {"max_moneyline":1200})
        self.assertEqual(row["games_period_limits"], {"max_total":3500})
        for value in (None, -1, "nan", "infinity", True, {}, "unpriced"):
            self.assertIsNone(pilot.reported_market_max({"max":value}))

    def test_wta_and_125_have_separate_labels_and_exact_games_contracts(self):
        parent = event(201,league_name="WTA 125k Colina - SF",home="Player Z",away="Player A")
        games = event(202,league_name=parent["league_name"],home="Player Z (Games)",away="Player A (Games)",
                      parent_id=201, periods={"num_0":{"status":"open",
                      "spreads":{"-2.5":{"hdp":-2.5,"home":1.87,"away":1.99}},
                      "totals":{"21.5":{"points":21.5,"over":1.91,"under":1.95}}}})
        board = snap([parent,games,event(203,league_name="WTA Dubai - SF"),
                      event(204,league_name="ITF Women Paris"),event(205,league_name="WTA Tokyo Doubles")],35)
        self.assertEqual(set(board["events"]),{"201","203"})
        self.assertEqual(board["events"]["201"]["tour"],"WTA 125")
        self.assertEqual(board["events"]["203"]["tour"],"WTA")
        markets=board["events"]["201"]["contracts"]
        self.assertEqual(markets["spreads:2.5"]["labels"],["Player A +2.5 games","Player Z -2.5 games"])
        self.assertEqual(markets["spreads:2.5"]["prices"],[1.99,1.87])
        self.assertEqual(markets["totals:21.5"]["prices"],[1.91,1.95])
        wrong=snap([parent,dict(games,parent_id=999)],35)
        self.assertNotIn("contracts",wrong["events"]["201"])

    def test_only_complete_singles(self):
        e=event()
        wrong=[event(101,home="Test Home (Games)"),event(102,league_name="ATP Finals Doubles"),
               event(103,home="Another Home",event_type="live"),event(104,home="Qualifier"),event(105,league_name="ITF X"),
               event(106,periods={"num_0":{"status":"suspended","money_line":{"home":2,"away":2}}}),
               event(107,home="L. One / T. Two"),event(108,is_have_odds=False),event(109,home="B",away="B"),
               event(110,home="C",periods={"num_0":{"status":"open","money_line":{"home":2,"away":None}}})]
        self.assertEqual(set(snap([e,*wrong],30)["events"]),{"100"})
        self.assertEqual(snap([e],-1)["events"],{})

    def test_ambiguous_duplicates_held_out(self):
        self.assertFalse(snap([event(),event(124)],30)["events"])

    def test_price_orientation_and_first_detection(self):
        e=event()
        state,_=pilot.advance({},snap([e],50))
        reversed_quote=event(home=e["away"],away=e["home"],periods={"num_0":{"status":"open","money_line":{"home":2,"away":1.85}}})
        state,moves=pilot.advance(state,snap([reversed_quote],35))
        self.assertEqual(len(moves),1)
        m=moves[0][1]
        self.assertEqual((m["player"],m["old"],m["new"]),("Test Home",2.3,1.85))
        self.assertTrue(m["move_pp"]>3)
        state,again=pilot.advance(state,snap([e],20))
        self.assertEqual(again,[])

    def test_stale_gap_disappearance_and_start_change(self):
        e=event()
        changed=event(periods={"num_0":{"status":"open","money_line":{"home":1.8,"away":2.1}}})
        state,_=pilot.advance({},snap([e],70))
        self.assertEqual(pilot.advance(state,snap([changed],15))[1],[])
        blank,_=pilot.advance(state,snap([],55))
        self.assertEqual(pilot.advance(blank,snap([changed],40))[1],[])
        revised={**changed,"starts":(START+timedelta(minutes=10)).isoformat()}
        self.assertEqual(pilot.advance(state,snap([revised],50))[1],[])
        late,_=pilot.advance(state,snap([revised],-1))
        self.assertTrue(next(iter(late["guards"].values()))["blocked"])

    def test_future_stamps_and_nonfinite_prices(self):
        e=event(periods={"num_0":{"status":"open","money_line":{"home":"nan","away":2.1}}})
        self.assertFalse(snap([e],60)["events"])
        state,_=pilot.advance({},snap([event()],40))
        self.assertIs(pilot.advance(state,snap([event()],60))[0],state)


class StoreStub:
    def __init__(self): self.data={}
    def get(self,key): return self.data.get(key)
    def put(self,key,value,replace=False):
        if not replace and key in self.data: return False
        self.data[key]=value
        return True


class EveryDropTest(unittest.TestCase):
    def setUp(self):
        self.t=watch.START+timedelta(hours=1)
        self.game=event(starts=(self.t+timedelta(hours=10)).isoformat())

    def capture(self,home,away,offset=0,swap=False,**kw):
        m=dict(self.game)
        m.update(kw)
        if swap: m["home"],m["away"]=m["away"],m["home"]
        m["periods"]={"num_0":{"status":"open","money_line":{"home":home,"away":away}}}
        return pilot.board_rows({"sport_id":2,"events":[m]}, self.t+timedelta(minutes=offset))

    def test_both_sides_shortened_early_and_no_magnitude_filter(self):
        prior=self.capture(2.13,1.88)
        now=self.capture(1.87,2.12,15,swap=True)
        sample=watch.observe(prior,now)
        self.assertEqual(sample["compared_pairs"],1)
        self.assertEqual({(m["player"],m["old"],m["new"]) for m in sample["moves"]},
                         {("Test Home",2.13,2.12),("Test Away",1.88,1.87)})
        self.assertTrue(all(m["both_shortened"] for m in sample["moves"]))
        self.assertEqual(sample,watch.observe(prior,now))
        self.assertTrue(min(m["move_pp"] for m in sample["moves"])<0)

    def test_baseline_gap_cutoff_and_new_start(self):
        now=self.capture(2.0,1.9,15)
        self.assertFalse(watch.observe(None,now)["moves"])
        self.assertFalse(watch.observe(self.capture(2.2,1.8,-65),now)["moves"])
        self.assertTrue(watch.observe(self.capture(2.2,1.8,-30),now)["too_far_apart"])
        self.assertFalse(watch.observe(self.capture(2.2,1.8),self.capture(2,1.9,15,starts=(self.t+timedelta(hours=11)).isoformat()))["moves"])
        self.assertFalse(watch.observe(self.capture(2.2,1.8),now,blocked={next(iter(now["events"].values()))["fixture"]})["moves"])

    def test_grouped_delivery_no_duplicates(self):
        batch=watch.observe(self.capture(2.13,1.88),self.capture(2.10,1.80,15))
        receipt, calls=StoreStub(),[]
        now=self.t+timedelta(minutes=15)
        def send(method,args):
            calls.append((method,args))
            return {"message_id":19,"date":int(now.timestamp()),"chat":{"id":123}}
        for expected in ("delivered","already delivered"):
            self.assertEqual(watch.deliver(batch,receipt,now=now,get_chat=lambda:"123",send=send),expected)
        self.assertEqual(len(calls),1)
        self.assertIn("2 observed price drops",calls[0][1]["text"])
        self.assertNotRegex(calls[0][1]["text"].lower(),r"pinnacle|pinnradar|oncourt|supabase|https?://")
        self.assertEqual(watch.deliver(batch,StoreStub(),now=now+timedelta(minutes=3),get_chat=lambda:"123",send=send),"quiet")
        self.assertEqual(watch.deliver({**batch,"moves":[]},StoreStub(),now=now,get_chat=lambda:"123",send=send),"quiet")

    def test_uncertain_delivery_is_not_repeated(self):
        batch=watch.observe(self.capture(2.13,1.88),self.capture(2.01,1.88,15))
        store=StoreStub()
        def uncertain(method, args): raise RuntimeError("response lost")
        for error in ("response lost","Uncertain Telegram receipt"):
            with self.assertRaisesRegex(RuntimeError,error):
                watch.deliver(batch,store,now=self.t+timedelta(minutes=15),get_chat=lambda:"123",send=uncertain)
