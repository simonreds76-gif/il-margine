import importlib.util, json, sys, tempfile, unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
S=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(S))
import tennis_input_health as h

class InputHealth(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,29,12,tzinfo=timezone.utc)
        self.fixtures=[dict(tour_id=4,round_id=5,player1_id=1,player2_id=2,surface='Hard',computed_at=self.now.isoformat())]
        self.elo=[dict(player_id=p,surface=s,elo=1600+p,match_count=0,updated_at='2026-02-26T00:00:00Z') for p in (1,2) for s in ('Hard','Overall')]
        self.meta=dict(profile_completed_at=(self.now-timedelta(days=2)).isoformat(),context_generated_at=self.now.isoformat(),context_status='READY',history_generated_at=self.now.isoformat(),history_status='CURRENT')
    def report(self,elo=None,meta=None):
        return h.evaluate(self.fixtures,elo if elo is not None else self.elo,self.elo,meta or self.meta,self.now)
    def test_present_ratings_never_certified_without_lineage(self):
        r=self.report();self.assertEqual(r['status'],'UNVERIFIED');self.assertEqual(r['fixtures_with_missing_elo'],0)
    def test_one_fresh_timestamp_does_not_hide_old_or_missing(self):
        self.elo[0]['updated_at']=self.now.isoformat();r=self.report(self.elo[:-1]);self.assertEqual(r['status'],'MISSING');self.assertFalse(r['timestamp_is_verified_refresh_cutoff'])
    def test_zero_match_counts_are_not_default_elo(self):
        r=self.report();self.assertEqual(r['zero_match_count_rows'],4);self.assertEqual(r['status'],'UNVERIFIED')
    def test_duplicate_rating_rejected(self):
        with self.assertRaises(ValueError):self.report(self.elo+self.elo[:1])
    def test_nan_rejected(self):
        self.elo[0]['elo']=float('nan')
        with self.assertRaises(ValueError):self.report()
    def test_schedule_specific_age_checks(self):
        self.meta['profile_completed_at']=(self.now-timedelta(days=8)).isoformat();self.meta['context_generated_at']=(self.now-timedelta(days=2)).isoformat()
        r=self.report();self.assertEqual(r['checks']['weekly_profiles'],'CURRENT');self.assertEqual(r['checks']['context'],'STALE')
    def test_future_stamp_invalid(self):
        self.meta['profile_completed_at']=(self.now+timedelta(days=1)).isoformat();self.assertEqual(self.report()['checks']['weekly_profiles'],'INVALID_FUTURE')
    def test_fingerprint_ignores_timestamp_and_order_only(self):
        fp=h.fingerprint(self.elo);self.elo[0]['updated_at']=self.now.isoformat();self.assertEqual(fp,h.fingerprint(self.elo[::-1]));self.elo[0]['elo']+=1;self.assertNotEqual(fp,h.fingerprint(self.elo))
    def test_immutable_capture_cannot_rewrite(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            p=Path(tmp)/'x.json';h.immutable(p,{'a':1});h.immutable(p,{'a':1})
            with self.assertRaises(ValueError):h.immutable(p,{'a':2})
    def test_lossless_capture_and_capacity_guard(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            out=Path(tmp);value={'a':[1,2,3]}
            h.immutable_capture(out,'one','before',value)
            self.assertEqual(h.read_capture(out/'runs/one','before'),value)
            with patch.object(h,'MAX_CAPTURE_BYTES',1),self.assertRaises(h.CaptureCapacityError):
                h.immutable_capture(out,'two','before',value)
            self.assertEqual(h.read_capture(out/'runs/one','before'),value)
    def test_observer_failure_nonfatal_and_visible(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp,patch.object(h,'record',side_effect=RuntimeError('secret URL must not appear')):
            r=h.safe_observe(Path(tmp),'before','test');self.assertEqual(r['status'],'CHECK_FAILED');self.assertNotIn('secret',json.dumps(r));self.assertEqual(h.load_status(Path(tmp))['status'],'CHECK_FAILED')
    def test_malformed_health_does_not_break_digest(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            p=Path(tmp)/h.RELATIVE/'status.json';p.parent.mkdir(parents=True);p.write_text('bad');self.assertEqual(h.load_status(Path(tmp))['status'],'CHECK_FAILED')
    def test_cross_day_static_ratings_despite_exact_results(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            root=Path(tmp);p=root/'data/oncourt/today_atp.csv';p.parent.mkdir(parents=True)
            p.write_text('tour_id,round_id,player1_id,player2_id,date,result\n4,5,1,2,2026-10-28,6-3 6-2\n')
            old=dict(observed_at='2026-10-27T20:00:00Z',elo_rows=self.elo)
            new=dict(observed_at=self.now.isoformat(),elo_rows=self.elo)
            self.assertEqual(len(h.unchanged_after_results(root,old,new)),4)
            old['observed_at']='2026-10-28T20:00:00Z';self.assertEqual(h.unchanged_after_results(root,old,new),[])
    def test_reporting_edits_do_not_change_dedup_functions(self):
        import ast
        before=S.parents[1]/'before/scripts/tennis-daily-signal-digest.py'
        if not before.exists():self.skipTest('before image only present in installation audit')
        old=ast.parse(before.read_text(encoding='utf-8-sig'));new=ast.parse((S/'tennis-daily-signal-digest.py').read_text(encoding='utf-8-sig'))
        old={n.name:ast.dump(n,include_attributes=False) for n in old.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
        new={n.name:ast.dump(n,include_attributes=False) for n in new.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
        self.assertEqual([n for n in old if old[n]!=new[n]],['render_messages'])
    def test_new_warning_text_does_not_resend_a_saved_selection(self):
        path=S/'tennis-daily-signal-digest.py'
        spec=importlib.util.spec_from_file_location('input_health_digest_test',path)
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
        signal=module.Signal(section='CORE',priority=0,labels=['STRICT'],match='A vs B',selection='A @ 2.0',edge_pct=6,
                             key=('2026-10-29','a','b','ml','a'))
        state={'signal_ids':[module.signal_id(signal)],'digest_hash':'old-message-content'}
        self.assertEqual(module.new_signals_since_state([signal],state,'2026-10-29'),[])
        state['signal_ids']=[]
        self.assertEqual(module.new_signals_since_state([signal],state,'2026-10-29'),[signal])

if __name__=='__main__':unittest.main()
