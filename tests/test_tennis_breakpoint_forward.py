import json,sys,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import tennis_breakpoint_forward as bp
from tennis_breakpoint_model import nb_over

class ForwardTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]);self.root=Path(self.tmp.name);self.out=self.root/bp.RELATIVE;self.out.mkdir(parents=True)
  self.code=Path(__file__).resolve().parents[1];self.time=datetime(2026,11,1,17,tzinfo=timezone.utc)
  bp.atomic(self.out/'registration.json',{'activated_at':self.time.isoformat(),'hashes':bp.fingerprints(self.code)})
 def tearDown(self):self.tmp.cleanup()
 def quote(self,**kw):
  return dict({'tour':'ATP','id':'quote1','event_id':'event1','offer_id':'offer1','capture_at':(self.time+timedelta(minutes=1)).isoformat(),'scheduled_start':(self.time+timedelta(hours=2)).isoformat(),'home':'A Player','away':'B Player','group':'Paris','line':10.5,'over':2.0,'under':1.8},**kw)
 def save_quote(self,q):bp.append(self.root/bp.EVIDENCE/'quotes.jsonl',[q])
 def test_old_quotes_cannot_be_forward(self):
  self.save_quote(self.quote(capture_at=(self.time-timedelta(minutes=1)).isoformat()));r=bp.capture(self.root,self.out,self.code,self.time);self.assertEqual(r['forecasts'],0);self.assertEqual(r['exclusions']['PRE_ACTIVATION_QUOTE'],1)
 def test_no_history_does_not_invent_forecast(self):
  self.save_quote(self.quote())
  with self.assertRaisesRegex(ValueError,'missing_or_changed_history'):bp.capture(self.root,self.out,self.code,self.time+timedelta(minutes=2))
 def test_stale_quotes_excluded(self):
  self.save_quote(self.quote());r=bp.capture(self.root,self.out,self.code,self.time+timedelta(minutes=45));self.assertEqual(r['exclusions']['STALE_OR_STARTED'],1)
 def test_changed_frozen_code_blocks(self):
  reg=bp.load(self.out/'registration.json');reg['hashes']={};bp.atomic(self.out/'registration.json',reg)
  with self.assertRaisesRegex(ValueError,'frozen_code'):bp.capture(self.root,self.out,self.code,self.time)
 def test_tail_is_monotone_and_finite(self):
  probs=[nb_over(12,.1122885057410778,k+.5)[0] for k in range(40)];self.assertEqual(probs,sorted(probs,reverse=True));self.assertTrue(all(0<p<1 for p in probs))
 def index(self,**kw):
  row={'tour_id':'100','date':'2026-11-01','player1_id':'1','player2_id':'2','round_id':'1',**kw}
  return ({'aplayer':[1],'bplayer':[2]}, {}, {100:{'name':'Paris Masters - Paris','rank':'3','court_id':'3'}},[row],{})
 def test_qualifying_indoor_maps(self):
  m=bp.map_quote(self.quote(),self.index());self.assertEqual(m['phase'],'qualifying');self.assertEqual(m['surface'],'Indoor hard')
 def test_wrong_date_not_guessed(self):
  with self.assertRaisesRegex(ValueError,'UNMAPPED_EXACT'):bp.map_quote(self.quote(),self.index(date='2026-11-02'))
 def test_unknown_player_not_guessed(self):
  with self.assertRaisesRegex(ValueError,'UNMAPPED_PLAYER'):bp.map_quote(self.quote(home='Player'),self.index())
 def test_result_conflict_not_settled(self):
  f={**self.quote(),'quote_id':'quote1','fixture_id':'100:1:1:2','cohort':'FORWARD_PAPER','selected':True,'p1_id':1,'p2_id':2,'edition_id':'100','round_id':'1','mu_C':12,'p_over_C':.6,'mkt_over':.5,'alpha':.1122885}
  bp.append(self.out/'forecasts.jsonl',[f]);bp.append(self.root/bp.EVIDENCE/'results.jsonl',[{'quote_id':'quote1','status':'COMPLETED_RESEARCH_OUTCOME','native_fixture':'1:3:100:1','y':15,'score':'6-4 6-3','result_date':'2026-11-01','validated_counts':{'w_bpfaced':5,'w_bpsaved':4,'w_bpof':10,'w_bpw':4,'l_bpfaced':10,'l_bpsaved':6,'l_bpof':5,'l_bpw':1}}]);r=bp.summarize(self.out,self.root/bp.EVIDENCE);self.assertEqual(r['settled_fixtures'],0);self.assertIsNone(r['roi_pct'])
 def test_correct_result_and_dedup_preserve_profit(self):
  f={**self.quote(),'quote_id':'quote1','fixture_id':'100:1:1:2','cohort':'FORWARD_PAPER','selected':True,'p1_id':1,'p2_id':2,'edition_id':'100','round_id':'1','mu_C':12,'p_over_C':.6,'mkt_over':.5,'alpha':.1122885}
  bp.append(self.out/'forecasts.jsonl',[f]);s={'quote_id':'quote1','status':'COMPLETED_RESEARCH_OUTCOME','native_fixture':'2:1:100:1','y':15,'score':'6-4 6-3','result_date':'2026-11-01','validated_counts':{'w_bpfaced':5,'w_bpsaved':4,'w_bpof':10,'w_bpw':4,'l_bpfaced':10,'l_bpsaved':6,'l_bpof':5,'l_bpw':1}};bp.append(self.root/bp.EVIDENCE/'results.jsonl',[s,s]);r=bp.summarize(self.out,self.root/bp.EVIDENCE);self.assertEqual((r['bets'],r['wins'],r['profit']),(1,1,1));self.assertEqual(bp.capture(self.root,self.out,self.code,self.time)['new_forecasts'],0)
 def test_empty_roi_not_zero(self):self.assertIsNone(bp.summarize(self.out,self.root/bp.EVIDENCE)['roi_pct'])
 def history(self,generated=None):
  (self.out/'history.csv.gz').write_bytes(b'history')
  bp.atomic(self.out/'history-status.json',{'generated_at':generated or self.time.isoformat(),'last_result':'2026-10-31','history_sha256':bp.sha(self.out/'history.csv.gz')})
 def test_history_not_available_at_quote_is_excluded(self):
  self.history((self.time+timedelta(minutes=3)).isoformat());self.save_quote(self.quote())
  with patch.object(bp,'identity_index',return_value=self.index()):r=bp.capture(self.root,self.out,self.code,self.time+timedelta(minutes=4))
  self.assertEqual(r['new_forecasts'],0);self.assertEqual(r['exclusions']['HISTORY_NOT_AVAILABLE_AT_QUOTE'],1)
 def test_real_capture_once_and_opponent_change_new_fixture(self):
  self.history();self.save_quote(self.quote());index=self.index()
  def predict(h,f,df):
   return bp.pd.DataFrame([{'fixture_id':r.fixture_id,'capture_at':r.capture_at,'mu_C':12.,'p_over_C':.6,'tail_crosscheck_abs':0.,'bet_C':1} for r in df.itertuples()])
  with patch.object(bp,'identity_index',return_value=index),patch.object(bp,'load_history',return_value=None),patch.object(bp,'forecast',side_effect=predict):
   self.assertEqual(bp.capture(self.root,self.out,self.code,self.time+timedelta(minutes=2))['new_forecasts'],1)
   self.assertEqual(bp.capture(self.root,self.out,self.code,self.time+timedelta(minutes=3))['new_forecasts'],0)
  self.save_quote(self.quote(id='q2',away='C Player'))
  names,aliases,tours,today,hashes=self.index(player2_id='3');names['cplayer']=[3]
  with patch.object(bp,'identity_index',return_value=(names,aliases,tours,today,hashes)),patch.object(bp,'load_history',return_value=None),patch.object(bp,'forecast',side_effect=predict):
   self.assertEqual(bp.capture(self.root,self.out,self.code,self.time+timedelta(minutes=4))['new_forecasts'],1)
  rr=bp.rows(self.out/'forecasts.jsonl');self.assertEqual(len({r['fixture_id'] for r in rr}),2);self.assertTrue(all(r['real_stake']==0 for r in rr))
 def test_invalid_counts_never_settle(self):
  f={'phase':'main_draw','best_of':3,'tournament':'Paris'}
  s={'score':'6-4 6-3','result_date':'2026-11-01','y':15,'validated_counts':{'w_bpfaced':5,'w_bpsaved':4,'w_bpof':10,'w_bpw':4,'l_bpfaced':10,'l_bpsaved':6,'l_bpof':5,'l_bpw':1}}
  self.assertTrue(bp.strict_outcome(f,s));s['validated_counts']['w_bpof']=11;self.assertFalse(bp.strict_outcome(f,s))
 def test_retirement_never_settles(self):
  self.assertFalse(bp.strict_outcome({'phase':'main_draw'},{'score':'6-4 1-0 RET','y':3}))
if __name__=='__main__':unittest.main()
