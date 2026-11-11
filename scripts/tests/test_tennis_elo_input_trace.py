"""Input lineage preserves forecasts, IDs, fallbacks and immutable captures."""
import os,copy,gzip,hashlib,json,sys,tempfile,types,unittest
from pathlib import Path
from datetime import date,datetime,timezone
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tennis_elo_input_trace as trace
import tennis_ml_evidence as E
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
TEST_TMP=os.environ.get('ILM_TEST_TMP')
class InputTraceTests(unittest.TestCase):
    def data(self,root):
        rows=[dict(tour_id=10,round_id=4,player1_id=1,player2_id=2,surface='I.hard',p_elo=.6000,p1_win_prob=.51)]
        state={'elo_lookup':{(1,'I.hard'):1500.,(1,'Overall'):1600.,(2,'Overall'):1700.,(99,'Hard'):1900.},
            'elo_rows':[{'player_id':1,'surface':'I.hard','elo':None,'SECRET':'DO_NOT_SAVE'},{'player_id':2,'surface':'Overall','elo':1700.},{'player_id':99,'surface':'Hard','elo':1900.}],
            'stats':{(1,'I.hard'):{'match_count':12}},'input_day':date(2026,11,11),'headers':{'Authorization':'DO_NOT_SAVE'},'base':'DO_NOT_SAVE'}
        state.update({k:{} for k in (*trace.PLAYER_MAPS,*trace.TOUR_MAPS)})
        state['atp_rank_by_player']={1:8,2:15,99:100}
        state['recent_activity_by_player']={1:{'matches_last_21d':5,'last_match_date':'2026-11-10'}}
        frame=types.SimpleNamespace(f_code=types.SimpleNamespace(co_filename=str(root/'scripts/oncourt-compute-fair-odds.py'),co_name='main'),f_locals=state,f_globals={'DEFAULT_ELO':1500,'ELO_RELIABILITY_MIN':.55,'SECRET':'DO_NOT_SAVE'})
        return rows,state,frame
    def folder(self,t):
        r=Path(t);(r/'scripts').mkdir();(r/'scripts/oncourt-compute-fair-odds.py').write_text('# fixed pricing')
        return r
    def test_allowlist_raw_coerced_missing_and_player_independence(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as t:
            r=self.folder(t);rows,state,frame=self.data(r);before=copy.deepcopy((rows,state))
            b=trace.build_trace(r,rows,frame,datetime(2026,11,11,20,tzinfo=timezone.utc));x=json.loads(b)
            self.assertNotIn(b'DO_NOT_SAVE',b);self.assertEqual((rows,state),before)
            self.assertEqual(x['raw_elo_rows'][0]['elo'],None)
            k={(i['player_id'],i['surface']):i for i in x['elo_lookup']}
            self.assertTrue(k[1,'I.hard']['present']);self.assertEqual(k[1,'I.hard']['value'],1500)
            self.assertFalse(k[2,'I.hard']['present']);self.assertEqual(k[2,'Overall']['value'],1700)
            self.assertNotIn('99',x['loaded_inputs']['atp_rank_by_player'])
            self.assertEqual(x['elo_lookup_rows'],4)
    def test_changed_input_same_prediction_is_retained_and_deduplicated(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as t:
            r=self.folder(t);rows,state,frame=self.data(r);before=copy.deepcopy(rows);now=datetime(2026,11,11,20,tzinfo=timezone.utc)
            def observe_stub(*a,**k):return 'not registered'
            stubs={n:types.SimpleNamespace(observe=observe_stub) for n in ['tennis_indoor_paper','tennis_first_return_paper','tennis_indoor_expansion']}
            with patch.dict(sys.modules,stubs),patch.object(E.sys,'_getframe',return_value=frame):
                self.assertEqual(E.capture_components(r,rows,now),'saved:1')
                self.assertEqual(E.capture_components(r,rows,now),'unchanged')
                state['elo_lookup'][1,'Overall']=1601.
                self.assertEqual(E.capture_components(r,rows,now),'saved:1')
            self.assertEqual(rows,before)
            files=list((r/'data/tennis-ml-research/components/2026-11-11').glob('*.json'));self.assertEqual(len(files),2)
            for p in files:
                j=json.loads(p.read_bytes());b=gzip.decompress((p.parent/j['input_trace_file']).read_bytes())
                self.assertEqual(hashlib.sha256(b).hexdigest(),j['input_trace_sha256'])
                self.assertEqual(sha(p.parent/j['model_source_file']),j['model_file_sha256'])
                self.assertEqual(j['rows'],before);self.assertEqual(j['schema_version'],2)
    def test_diagnostic_fault_does_not_drop_forecasts(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as t:
            r=self.folder(t);rows,state,frame=self.data(r);now=datetime(2026,11,11,20,tzinfo=timezone.utc)
            stubs={n:types.SimpleNamespace(observe=lambda *a,**k:'not registered') for n in ['tennis_indoor_paper','tennis_first_return_paper','tennis_indoor_expansion']}
            with patch.dict(sys.modules,stubs),patch.object(trace,'build_trace',side_effect=ValueError('bad metadata')):
                self.assertEqual(E.capture_components(r,rows,now),'saved:1')
            p=next(r.glob('data/tennis-ml-research/components/*/*.json'));j=json.loads(p.read_bytes())
            self.assertEqual(j['rows'],rows);self.assertEqual(j['input_trace_status'],'unavailable:ValueError')
    def test_midnight_does_not_claim_exact_clock_and_old_schema_is_distinct(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as t:
            r=self.folder(t);rows,state,frame=self.data(r)
            self.assertTrue(json.loads(trace.build_trace(r,rows,frame,datetime(2026,11,12,tzinfo=timezone.utc)))['crossed_calendar_day'])
            self.assertIsNone(trace.build_trace(r,rows,None,datetime.now(timezone.utc)))

if __name__=='__main__':unittest.main()
