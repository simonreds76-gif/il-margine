import itertools
import sys
import unittest
import copy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desk_match_returns import BASE, CLOSE, ROOT, ReportingStore, build, first_scan, settle, settlement_health


def item(code, new, minute="00", old=2, **fields):
    return dict(contract=code, side=0, after=f"2026-11-22T10:{minute}:00+00:00",
                old=old, new=new, **fields)


class MatchReturns(unittest.TestCase):
    def test_same_run_reads_written_grades_even_when_remote_still_serves_old_cache(self):
        from pinnradar_tennis import Store
        store=object.__new__(ReportingStore)
        store.writes,store.revision={},"test-revision"
        cache=BASE+"/rolling-cache-v2.json"
        data={"day":{"grade":"Won"}}
        with patch.object(Store,"put",return_value=True),patch.object(Store,"get",return_value={"stale":True}) as get:
            self.assertTrue(store.put(cache,data,True))
            data["day"]["grade"]="Pending"
            self.assertEqual(store.get(cache)["day"]["grade"],"Won")
            get.assert_not_called()
            store.get(ROOT+"/state.json")
            get.assert_called_once_with(ROOT+"/state.json?revision=test-revision")
        self.assertEqual(settle(item("winner",2,result="Won"),{},None)["result"],"Won")

    def test_overdue_health_counts_unique_fixtures_across_both_records(self):
        now=datetime(2026,11,24,12,tzinfo=timezone.utc)
        old=dict(start="2026-11-22T10:00:00Z",tour="Challenger",result="Pending",player="A",opponent="B",league="X")
        locks={"all":{"old":old,"done":dict(old,result="Won")},"telegram":{"old":old,"recent":dict(old,start="2026-11-24T10:00:00Z")}}
        rows=settlement_health(locks,now)["overdue"]
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["groups"],["all","telegram"])
    def test_first_scan_then_largest_unrounded_inverse_odds_move(self):
        # The biggest decimal change loses the simultaneous tie-break. The later 30 pp move is ignored.
        a = item("winner", 5, old=10)
        b = item("totals:23", 1.65, old=2)
        c = item("spreads:1", 1.25, minute="15", old=2)
        for order in itertools.permutations([a,b,c]):
            self.assertEqual(first_scan(order, lambda v:v), b)

    def test_display_rounding_and_exact_tie(self):
        a, b = item("spreads:1", 1.80001), item("totals:23", 1.80000)
        self.assertEqual(first_scan([a,b],lambda v:v),b)
        self.assertEqual(first_scan([b,dict(a,new=b["new"])],lambda v:v)["contract"],"spreads:1")

    def test_no_replacement_on_void_and_grades_at_sent_price(self):
        t = item("winner",2.4,old=3,message=17)
        for result, pnl, stake in [("Void",0,0),("Pending",0,0),("Lost",-1,1),("Won",1.4,1)]:
            graded = settle(t,{"result":result},None)
            self.assertAlmostEqual(graded["profit"],pnl)
            self.assertEqual(graded["stake"],stake)
        with self.assertRaises(ValueError):
            settle(t,{},{"message_id":17,"alerted_price":2.41,"result":"Won"})

    def test_replay_scope_and_retry_across_dates(self):
        class Memory:
            def __init__(self):
                self.objects = {}
            def get(self,key):
                return copy.deepcopy(self.objects.get(key))
            def put(self,key,value,replace):
                self.objects[key] = copy.deepcopy(value)
        store = Memory()
        first = dict(item("winner",1.8), fixture="f", tour="Challenger", league="L", selection="A",
                     player="A",opponent="B", before="2026-11-22T09:00:00Z",start="2026-11-24T13:00:00Z",
                     result="Void",stake=0,profit=0)
        other = dict(first,contract="totals:20",selection="Over 20 games",new=1.7,result="Lost",stake=1,profit=-1)
        later = dict(first,after="2026-11-23T09:00:00Z",contract="spreads:1",selection="A +1 games",
                     new=1.25,result="Won",profit=.25,stake=1)
        alert = dict(first, sent="2026-11-22T10:02:31Z", message=17, move_id="alert")
        cache = {day:dict(coverage={"ATP":1},tickets=[],receipts={})
                 for day in ("2026-11-19","2026-11-22","2026-11-23")}
        cache["2026-11-22"].update(tickets=[first,other],receipts={"first":[alert]})
        cache["2026-11-23"]["tickets"] = [later]
        store.objects[BASE+"/rolling-cache-v2.json"] = cache
        store.objects[BASE+"/rolling-30-v2/atp.json"] = {"through":"2026-11-23T09:00:00Z"}
        for tour in ("atp","wta"):
            store.objects[CLOSE+tour+".json"] = {"rows":[]}
        now = datetime(2026,11,23,10,tzinfo=timezone.utc)
        first_report = build(store,now,write=True)
        self.assertEqual(first_report,build(store,now,write=True))
        atp = first_report["ATP"]
        self.assertEqual((atp["all"]["entries"],atp["all"]["net"]),(1,-1))
        self.assertEqual((atp["telegram"]["entries"],atp["telegram"]["voids"],atp["telegram"]["stake"]),(1,1,0))
        self.assertEqual(atp["days"]["2026-11-23"]["all4"]["entries"],0)
        self.assertEqual(first_report["WTA"]["all"]["entries"],0)
        self.assertIn(ROOT+"/state.json",store.objects)
