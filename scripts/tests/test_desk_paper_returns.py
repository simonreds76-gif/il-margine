import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desk_paper_returns import advance_paper, apply_retirement_review, summary, performance_report
from datetime import datetime, timezone


def scan(stamp, price=2, start="16:00", live=False, events=True, contracts=None):
    day="2026-11-20T"
    row=dict(id="a", fixture="uid", tour="ATP",league="ATP X - QF",start=day+start+":00+00:00",
             home="Zulu",away="Alpha",home_price=price,away_price=1.8,contracts=contracts or {})
    return {"observed":day+stamp+":00+00:00", "events":{"a":row} if events else {},
            "in_play_fixtures":["uid"] if live else []}


class PaperReturnsTest(unittest.TestCase):
    def test_month_and_lifetime_use_settled_stakes_and_isolate_circuits(self):
        def day(stamp, rows):
            atp = {"coveredScans":1, "rules":{"all4":summary(rows), "late4":summary([])}}
            wta = {"coveredScans":0, "rules":{"all4":summary([]), "late4":summary([])}}
            return {"through":stamp, "circuits":{"ATP":atp,"WTA":wta}}
        def entry(result, stake, profit):
            return {"fixture":"f", "result":result, "stake":stake, "profit":profit}
        days = {"2026-11-30":day("2026-11-30",[entry("Won",1,2)]),
                "2026-12-01":day("2026-12-01",[entry("Lost",1,-1),entry("Lost",1,-1),entry("Pending",0,0)])}
        report = performance_report(days)["circuits"]
        self.assertEqual(report["ATP"]["lifetime"]["all4"]["roi"],0)
        self.assertEqual(report["ATP"]["lifetime"]["all4"]["pending"],1)
        self.assertEqual(report["ATP"]["months"]["2026-11"]["all4"]["roi"],200)
        self.assertIsNone(report["WTA"]["lifetime"]["all4"]["roi"])

    def test_historical_retirement_correction_is_idempotent_at_original_odds(self):
        t = {"market":"winner","new":1.806,"after":"2026-11-20T12:15:00Z","start":"2026-11-21T07:00:00Z",
             "binding":[2,10,200,201],"league":"ATP Challenger Sydney - SF","result":"Void","stake":0,"profit":0}
        item = {"id":"abc","binding":t["binding"],"odds":1.806,"detected":t["after"],"evidence_sha256":"abc123",
                "official_result":{"tour_id":2,"round_id":10,"winner_id":200,"loser_id":201,"date":"2026-11-21","result":"6-2 3-0 RET"}}
        ledger={"tickets":{"abc":t}}
        now=datetime(2026,11,21,11,tzinfo=timezone.utc)
        for _ in range(2):
            apply_retirement_review(ledger,[item],now)
            self.assertEqual((t["result"],t["stake"],round(t["profit"],3)),("Won",1,.806))
        with self.assertRaises(ValueError):
            apply_retirement_review(ledger,[dict(item, odds=2)],now)

    def test_limit_belongs_to_the_detection_odds_and_never_carries_forward(self):
        s = {}
        for time, price, limit in (("12:00",2,900),("12:15",1.85,350),("12:30",1.82,None)):
            board = scan(time, price)
            if limit is not None:
                board["events"]["a"]["reported_market_max"] = {"amount":limit}
            tickets = advance_paper(s,board)
            if time == "12:15":
                self.assertEqual(tickets[0]["reported_market_max_at_detection"], {"amount":350})
            if time == "12:30":
                self.assertNotIn("reported_market_max_at_detection", tickets[0])

    def test_first_separate_thresholds_and_exact_odds(self):
        s={}
        self.assertEqual(advance_paper(s,scan("12:00")),[])
        first=advance_paper(s,scan("12:15",1.85))
        self.assertEqual([(x["rule"],x["player"],x["new"]) for x in first],[("all4","Zulu",1.85)])
        later=advance_paper(s,scan("12:30",1.82))
        self.assertEqual([(x["rule"],x["new"]) for x in later],[("all45",1.82)])
        self.assertEqual(advance_paper(s,scan("12:30",1.82)),[])
        self.assertEqual(advance_paper(s,scan("12:45",1.80)),[])

    def test_two_inside_hour_even_after_all_day_signal(self):
        s={}
        advance_paper(s,scan("14:45"))
        self.assertEqual({x["rule"] for x in advance_paper(s,scan("15:00",1.8))},{"all4","all45"})
        advance_paper(s,scan("15:15",2))
        late=advance_paper(s,scan("15:30",1.8))
        self.assertEqual({x["rule"] for x in late},{"late4","late45"})
        self.assertTrue(all("15:15" in x["before"] for x in late))

    def test_gap_absence_and_start(self):
        for gap in ("missing","long","inplay","rescheduled","at_start"):
            s={}; advance_paper(s,scan("15:00"))
            if gap=="missing": advance_paper(s,scan("15:15",events=False))
            at={"long":"15:45","at_start":"16:00"}.get(gap,"15:30")
            snap=scan(at,1.6,start="17:00" if gap=="rescheduled" else "16:00",live=gap=="inplay")
            self.assertEqual(advance_paper(s,snap),[],gap)

    def test_total_and_spread_directions_and_partial_roi(self):
        s={}
        def markets(a,b):
            return {"spreads:2.5":{"market":"spreads","labels":["Alpha +2.5 games","Zulu -2.5 games"],
                    "prices":[2,a],"line":2.5},"totals:22":{"market":"totals","labels":["Over","Under"],
                    "prices":[b,2],"line":22}}
        advance_paper(s,scan("12:00",contracts=markets(2,2)))
        rows=advance_paper(s,scan("12:15",contracts=markets(1.8,1.8)))
        self.assertEqual({(t["market"],t["side"],t["line"],t["player"]) for t in rows},
                         {("spreads",1,-2.5,"Zulu"),("totals",0,22,"Alpha")})
        stats=summary([dict(fixture="a",result="Half won",stake=1,profit=.4),dict(fixture="a"),
                       dict(fixture="b",result="Void",stake=0,profit=0),dict(fixture="a",result="Push",stake=1,profit=0)])
        self.assertEqual((stats["fixtures"],stats["stake"],stats["roi"],stats["pending"]),(2,2,20,1))
