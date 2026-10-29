import copy, math, tempfile, unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from unittest.mock import patch
from tennis_elo_rebuild import advance, empty_state, digest, rating_rows, rebuild
from tennis_elo_shadow import instrument, summarize, fixture, settle, load

def match(day,w,l,key,s='Hard'):
    return {'key':key,'date':day,'available_date':day,'winner':w,'loser':l,'surface':s}

class EloTests(unittest.TestCase):
    def test_arithmetic(self):
        s=advance(empty_state(),[match('2026-01-01',1,2,'a')],'2026-01-02')
        self.assertEqual(s['ratings'],{'1|Hard':1511.,'2|Hard':1489.,'1|Overall':1511.,'2|Overall':1489.})
    def test_same_day_pre_day_order(self):
        h=[match('2026-01-01',1,2,'a'),match('2026-01-01',1,3,'b')]
        a=advance(empty_state(),h,'2026-01-02');b=advance(empty_state(),list(reversed(h)),'2026-01-02')
        self.assertEqual(a,b);self.assertEqual(a['ratings']['1|Overall'],1522.)
    def test_future_and_same_day_withheld(self):
        h=[match('2026-01-01',1,2,'a'),match('2026-01-02',2,1,'b')]
        a=advance(empty_state(),h,'2026-01-02');self.assertEqual(a['matches'],1)
    def test_delayed_date(self):
        r=match('2026-01-01',1,2,'a');r['available_date']='2026-01-15'
        self.assertEqual(advance(empty_state(),[r],'2026-01-15')['matches'],0)
    def test_incremental_equals_full(self):
        h=[match('2026-01-01',1,2,'a'),match('2026-01-02',2,3,'b'),match('2026-01-03',3,1,'c','Clay')]
        a=advance(empty_state(),h,'2026-01-02');advance(a,h,'2026-01-04')
        self.assertEqual(a,advance(empty_state(),h,'2026-01-04'))
        for surface in ['Overall','Hard','Clay']:
            v=[x for k,x in a['ratings'].items() if k.endswith('|'+surface)]
            self.assertAlmostEqual(sum(v),1500*len(v))
    def test_correction_replays(self):
        h=[match('2026-01-01',1,2,'a'),match('2026-01-02',2,3,'b')]
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            with patch('tennis_elo_rebuild.source_history',return_value=(h,{})):
                a,_=rebuild(Path(d),Path(d)/'out','2026-01-03')
                b,_=rebuild(Path(d),Path(d)/'out','2026-01-03')
                self.assertEqual(a['rating_hash'],b['rating_hash']);self.assertEqual(b['build_mode'],'incremental')
            h[0].update(winner=2,loser=1)
            with patch('tennis_elo_rebuild.source_history',return_value=(h,{})):
                c,_=rebuild(Path(d),Path(d)/'out','2026-01-03')
                self.assertEqual(c['build_mode'],'full_rebuild');self.assertNotEqual(c['rating_hash'],a['rating_hash'])
    def test_failed_history_preserves_candidate(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            p=Path(d)/'out'
            with patch('tennis_elo_rebuild.source_history',return_value=([match('2026-01-01',1,2,'a')],{})):rebuild(Path(d),p,'2026-01-02')
            original=(p/'candidate.json').read_bytes()
            with patch('tennis_elo_rebuild.source_history',side_effect=ValueError('bad input')):
                with self.assertRaises(ValueError):rebuild(Path(d),p,'2026-01-02')
            self.assertEqual(original,(p/'candidate.json').read_bytes())
    def test_instrumentation_fails_closed(self):
        with self.assertRaises(ValueError):instrument('def main(): pass')
    def test_mixed_outcomes_roi(self):
        rows=[]
        for y in [1,0]:
            rows.append({'result':'settled','y':y,'baseline':{'p1_win_prob':.6,'elo_diagnostics':{'final_expected_games':22}},
                'actual_games':20,'baseline_selection':{'lane':'provisional_hard','side':'P1'},'quote':{'odds1':2.5,'odds2':1.6}})
        r=summarize(rows,'baseline');self.assertEqual((r['wins'],r['losses'],r['stake'],r['profit'],r['roi_pct']),(1,1,2,.5,25.))
    def test_fixture_orientation(self):
        a={'tour_id':1,'round_id':4,'player1_id':3,'player2_id':2};b={**a,'player1_id':2,'player2_id':3}
        self.assertEqual(fixture(a),fixture(b))

class OperationalTests(unittest.TestCase):
    def test_daily_capture_bound_skips_compute(self):
        import datetime
        from tennis_elo_shadow import capture
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            p=Path(d);(p/'evidence').mkdir();(p/'evidence'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT010101Z.json.gz')).write_bytes(b'x')
            with patch('tennis_elo_shadow.run_engine',side_effect=AssertionError('must not run')):
                self.assertEqual(capture(p,p,{})['skipped'],'daily_capture_limit')
    def test_lock_prevents_concurrent_writer(self):
        from tennis_elo_shadow import process_lock
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            with process_lock(Path(d)):
                with self.assertRaises(OSError):
                    with process_lock(Path(d)):pass
            with process_lock(Path(d)):pass
    def test_exact_settlement_and_ambiguous_result(self):
        import json,csv
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            p=Path(d);f=p/'data/oncourt';f.mkdir(parents=True);out=p/'out';out.mkdir()
            r={'key':'8:4:1:2','kickoff':'2026-10-29T14:00:00Z','result':'pending','baseline':{'player1_id':1}}
            (out/'ledger.json').write_text(json.dumps([r]))
            (f/'stat_atp.csv').write_text('tour_id,round_id,winner_id,loser_id,w_ace,w_df,w_svpt,l_ace,l_df,l_svpt\n8,4,2,1,10,3,80,5,1,60\n')
            header='tour_id,round_id,winner_id,loser_id,date,result\n'
            row='8,4,2,1,2026-10-29,6-3 6-4\n'
            (f/'games_atp.csv').write_text(header+row)
            got=settle(p,out)[0];self.assertEqual(got['y'],0);self.assertEqual(got['actual_games'],19);self.assertEqual(got['actual_margin_p1'],-5)
            self.assertEqual(got['actual_stats']['1']['ace'],5)
            (f/'games_atp.csv').write_text(header+row+'8,4,1,2,2026-10-29,6-0 6-0\n')
            quarantined=settle(p,out)[0]
            self.assertEqual(quarantined['result'],'quarantined');self.assertNotIn('y',quarantined)
            self.assertEqual(quarantined['correction_history'][0]['y'],0)
            self.assertEqual(quarantined['settlement_events'][-1]['after']['result'],'quarantined');self.assertIn('at',quarantined['settlement_events'][-1])
            (f/'games_atp.csv').write_text(header+row)
            self.assertEqual(settle(p,out)[0]['result'],'settled')
            (out/'ledger.json').write_text(json.dumps([r]));(f/'games_atp.csv').write_text(header+row+'8,4,1,2,2026-10-29,6-0 6-0\n')
            got=settle(p,out)[0];self.assertEqual(got['result'],'pending');self.assertEqual(got['settlement_health'],'ambiguous_native_results')
    def test_no_data_not_zero_roi(self):
        from tennis_elo_shadow import weekly_text
        self.assertIsNone(summarize([],'baseline')['roi_pct']);self.assertIn('unavailable',weekly_text({}))
    def test_failure_never_calls_http_writer(self):
        import requests
        from tennis_elo_shadow import run_engine
        source="def main():\n    requests.post('https://example.invalid')\n"
        import ast
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            p=Path(d);(p/'scripts').mkdir();(p/'scripts/oncourt-compute-fair-odds.py').write_text('ignored')
            with patch('tennis_elo_shadow.instrument',return_value=ast.parse('import requests\n'+source)):
                with patch('requests.post') as writer:
                    with self.assertRaisesRegex(RuntimeError,'Research write forbidden'):run_engine(p,{}, {})
                    writer.assert_not_called()

if __name__=='__main__':unittest.main()

