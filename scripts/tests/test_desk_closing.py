import sys
import unittest
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desk_closing import closing,display
from desk_start_clocks import opening_point,link_candidates
from bs4 import BeautifulSoup


class DeskClose(unittest.TestCase):
    def setUp(self):
        self.t=dict(fixture="fixture-a",league="Example - SF",player="Player One",opponent="Player Two",
                    tour="WTA",selection="Over 21.5 games",contract="totals:21.5",side=0,
                    new=2.1,after="2026-11-21T10:02:00Z",sent="2026-11-21T10:03:00Z")
        self.clock=dict(start_report="2026-11-21T10:41:00Z",players=["Player Two","Player One"],league=self.t["league"])
        self.q=lambda mm,price:[f"2026-11-21T10:{mm}:00Z",price,1.9]
        def series(quotes):return {"players":["Over 21.5 games","Under 21.5 games"],"quotes":quotes}
        self.tape={"slots":{i:self.q(i,2)[0] for i in ("02","17","32","47")},
                   "series":{"42|fixture-a|2026-11-21T10:25:00Z|totals:21.5":series([self.q("02",2.1),self.q("17",1.95)]),
                             "42|fixture-a|2026-11-21T10:45:00Z|totals:21.5":series([self.q("32",2),self.q("47",1.5)])}}
    def compare(self):
        return closing(self.t,datetime.fromisoformat(self.t["sent"]),self.clock,lambda day:self.tape)
    def test_exact_last_observed_before_play(self):
        c=self.compare()
        self.assertEqual((c["odds"],c["minutes"],c["change"]),(2,9,5))
        self.assertEqual(display(self.t,"telegram")["at"],self.t["sent"])
    def test_other_line_unavailable(self):
        self.t["contract"]="totals:22.5"
        self.assertIsNone(self.compare())
    def test_scope_is_exact_side(self):
        self.t["side"]=1
        self.assertIsNone(self.compare())
    def test_legacy_reversed_series(self):
        for series in self.tape["series"].values():
            series["players"].reverse()
            for tick in series["quotes"]:tick[1:3]=tick[1:3][::-1]
        self.assertEqual(self.compare()["odds"],2)
    def test_entry_only_is_unmeasured(self):
        self.clock["start_report"]="2026-11-21T10:09:00Z"
        self.assertIsNone(self.compare()["change"])
    def test_flat_from_new_scan_counts(self):
        list(self.tape["series"].values())[-1]["quotes"][0][1]=2.1
        self.assertEqual(self.compare()["change"],0)
    def test_missing_scan_pending(self):
        del self.tape["slots"]["17"]
        self.assertIsNone(self.compare())
    def test_wrong_players(self):
        self.clock["players"]=["Player One","Other"]
        self.assertIsNone(self.compare())
    def test_separate_event_for_same_players(self):
        key=list(self.tape["series"])[-1]
        self.tape["series"]["43"+key[2:]]=self.tape["series"].pop(key)
        self.assertIsNone(self.compare())
    def test_uncertain_minute(self):
        self.clock.update(start_report="2026-11-21T10:32:00Z",precision_seconds=60)
        self.assertIsNone(self.compare())
    def test_no_actual_clock_in_scorecard(self):
        self.assertIsNone(opening_point(BeautifulSoup("<title>Singles</title>","html.parser"),"sample"))
