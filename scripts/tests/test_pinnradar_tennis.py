import sys
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pinnradar_tennis as pilot

START=pilot.utc("2026-11-19T12:00:00Z")

def event(event_id=100, **kw):
    e=dict(sport_id=2,event_id=event_id,league_name="ATP Challenger Helsinki - Qualifiers",
           home="Test Home",away="Test Away",starts=START.isoformat(),event_type="prematch",is_have_odds=True,
           periods={"num_0":{"number":0,"status":"open","money_line":{"home":2.30,"away":1.65}}})
    return {**e, **kw}

def snap(events,minutes):
    return pilot.board_rows({"sport_id":2,"events":events},START-timedelta(minutes=minutes))

class MatchWinnerTest(unittest.TestCase):
    def test_only_complete_singles(self):
        e=event()
        wrong=[event(101,home="Test Home (Games)"),event(102,league_name="ATP Finals Doubles"),
               event(103,event_type="live"),event(104,home="Qualifier"),event(105,league_name="ITF X"),
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
