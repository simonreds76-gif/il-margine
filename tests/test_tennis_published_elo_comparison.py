import sys,unittest,tempfile,json,copy,gzip,os,subprocess,hashlib
from pathlib import Path
from datetime import datetime,timezone,date,timedelta
from unittest.mock import patch
R=Path(os.environ.get('ILMARGINE_TEST_ROOT',Path(__file__).resolve().parents[1]));sys.path.insert(0,str(R/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import tennis_published_elo_comparison as P
import tennis_elo_shadow as S

def row(**kw):return dict(tour_id=77,round_id=4,player1_id=1,player2_id=2,player1='John Alpha',player2='Bill Beta',tour_name='Test Masters',event_key='Test',official_category='Masters 1000',series='Masters 1000',surface='Hard',confidence='high',p1_win_prob=.6,p2_win_prob=.4,p_a=.64,p_b=.62,best_of=3,**kw)
def q():return dict(odds1=1.9,odds2=2.2,market_p1=(1/1.9)/(1/1.9+1/2.2),captured_at='2026-10-31T08:00:00+00:00',kickoff_iso='2026-10-31T14:00:00+00:00')
def fixture_input(root):
 p=root/'data/oncourt/games_atp.csv';p.parent.mkdir(parents=True)
 p.write_text('winner_id,loser_id,tour_id,round_id,result,date\n1,3,60,4,6-3 6-4,2026-10-29\n2,3,61,4,6-4 6-2,2026-10-29\n')
 a=S.module(R/'scripts/oncourt-compute-recent-activity.py');pop,_=a.aggregate_activity([p],{1,2},date(2026,10,30))
 activity={x['player_id']:x for x in a.build_rows(pop,{3:1700})}
 old={(pid,s):v for pid,v in [(1,1800),(2,1750),(3,1700)] for s in ('Overall','Hard')}
 snap={'players':[dict(oncourt_id=pid,overall=v,surface_blended={'Hard':v}) for pid,v in [(1,1850),(2,1750),(3,1800)]],
  'observed_at':'2026-10-30T00:00:00+00:00','publication_date':'2026-10-26'}
 return old,activity,snap

class Tests(unittest.TestCase):
 def test_executed_entrypoint_is_the_fingerprinted_module(self):
  program="import sys,runpy,hashlib; p=sys.argv[1]; sys.argv=[p,'--help']\ntry: runpy.run_path(p,run_name='__main__')\nexcept SystemExit as e: assert e.code==0\nm=sys.modules['tennis_elo_shadow']; print('ACTIVE_HASH='+hashlib.sha256(open(m.__file__,'rb').read()).hexdigest())"
  env={**os.environ,'PYTHONPATH':str(R/'scripts')+os.pathsep+str(Path(S.__file__).parent)}
  result=subprocess.run([sys.executable,'-B','-c',program,str(S.__file__)],env=env,capture_output=True,text=True,timeout=15)
  self.assertEqual(result.returncode,0,result.stderr)
  self.assertIn('ACTIVE_HASH='+hashlib.sha256(Path(S.__file__).read_bytes()).hexdigest(),result.stdout)
 def test_stale_context_fails_before_database_reads(self):
  with tempfile.TemporaryDirectory() as td, patch.object(S,'manual_pending',return_value=False), patch('tennis_pricing_context.load_inputs',side_effect=ValueError('stale')), patch.object(S,'run_engine') as engine:
   with self.assertRaisesRegex(ValueError,'stale'):S.capture(Path(td),Path(td),{})
   engine.assert_not_called()
 def comparison(self,mutate=None,raises=False):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);ratings,activity,snap=fixture_input(root)
   if mutate:mutate(ratings,activity,snap)
   before=copy.deepcopy((ratings,activity));seen=[]
   def compute(*a,**kw):
    seen.append(copy.deepcopy((ratings,activity)))
    if raises:raise RuntimeError('stop')
    return [row()],[row()],[]
   real=S.module
   with patch.object(P,'snapshot_current',return_value=snap),patch.object(S,'module',side_effect=lambda p:real(R/'scripts'/p.name)):
    if raises:
     with self.assertRaises(RuntimeError):P.compare_inputs(root,compute,([row()],[row()],[]),ratings,activity,date(2026,10,30))
     self.assertEqual(before,(ratings,activity));return
    result=P.compare_inputs(root,compute,([row()],[row()],[]),ratings,activity,date(2026,10,30))
   self.assertEqual(before,(ratings,activity))
   return result,seen
 def test_full_dependency_recompute_and_restore(self):
  r,seen=self.comparison();self.assertEqual(r['counts']['paired'],1);self.assertEqual(seen[0][1][1]['avg_opponent_elo'],1800)
  saved=r['coverage'][P.fixture(row())]['inputs'][0]
  self.assertEqual(saved['saved_activity']['avg_opponent_elo'],1700)
  self.assertEqual(saved['saved_activity'],saved['rebuilt_current_activity'])
 def test_no_mixed_source_missing_opponent(self):
  r,_=self.comparison(lambda a,b,s:s['players'].pop());self.assertEqual(r['counts']['paired'],0);self.assertIn('published_opponent_rating_unavailable',r['exclusions'])
 def test_missing_player_excludes_pair(self):
  r,_=self.comparison(lambda a,b,s:s['players'].pop(0));self.assertEqual(r['counts']['paired'],0)
 def test_current_default_excludes_pair(self):
  r,_=self.comparison(lambda a,b,s:a.pop((3,'Overall')));self.assertIn('current_opponent_rating_unavailable',r['exclusions'])
 def test_activity_mismatch_not_silently_replaced(self):
  r,_=self.comparison(lambda a,b,s:b[1].update(matches_last_21d=2));self.assertEqual(r['counts']['paired'],0)
 def test_exception_restores_live_inputs(self):self.comparison(raises=True)
 def test_primary_gates_side_zero_is_valid(self):
  self.assertEqual(P.ml_selection(row(),q())['side'],0)
 def test_primary_gates_challenger_excluded(self):
  r=row();r['series']='ATP 250';self.assertIsNone(P.ml_selection(r,q())['side']);self.assertEqual(P.ml_selection(r,q(),'ev5')['side'],0)
 def test_reverse_spread_orientation(self):
  q1=q();raw=dict(player1_name='Bill Beta',player2_name='John Alpha',league_name='Test',league='ATP',spread_line='-2.5',spread_odds1='2',spread_odds2='1.8',**{k:q1[k] for k in ('captured_at','kickoff_iso')})
  s=P.spread_quote(row(),[raw],q1);self.assertEqual(s['line'],2.5);self.assertEqual(s['odds'],[1.8,2.0])
 def test_ambiguous_spread_rejected(self):
  q1=q();x=dict(player1_name='John Alpha',player2_name='Bill Beta',league_name='Test',league='ATP',spread_line='-2.5',spread_odds1='2',spread_odds2='1.8',**{k:q1[k] for k in ('captured_at','kickoff_iso')})
  self.assertIsNone(P.spread_quote(row(),[x,{**x,'spread_line':'-3.5'}],q1))
 def test_timestamp_mismatch_spread_rejected(self):
  self.assertIsNone(P.spread_quote(row(),[],q()))
 def test_quarter_spread_rejected(self):
  quote=q();raw=dict(player1_name='John Alpha',player2_name='Bill Beta',league_name='Test',league='ATP',spread_line='-2.25',spread_odds1='2',spread_odds2='1.8',**{k:quote[k] for k in ('captured_at','kickoff_iso')})
  self.assertIsNone(P.spread_quote(row(),[raw],quote))
 def test_reversed_ml_quote_is_normalized(self):
  from tennis_category_shadow import quote_for
  quote=q();raw=dict(player1_name='Bill Beta',player2_name='John Alpha',league_name='Test',league='ATP',odds1='2.2',odds2='1.9',**{k:quote[k] for k in ('captured_at','kickoff_iso')})
  parsed,reason=quote_for(row(),[raw]);self.assertEqual(reason,'verified');self.assertEqual(parsed['odds1'],1.9);self.assertEqual(parsed['odds2'],2.2)
  self.assertEqual(P.ml_selection(row(),parsed)['side'],0)
 def test_gate_blocked_handicap_not_scored(self):
  r={'key':'a','current':row(),'handicap':{'current':{'status':'priced','market_gate_blocked':True,'p1_conditional':.6,'quote':{'line':-2},'selection':{'side':None,'odds':2}}}}
  m=P.measure([r],{'a':{'status':'settled','margin_p1':3}},'current',market='handicap');self.assertEqual(m['scored_fixtures'],0);self.assertEqual(m['stake'],0)
 def test_forecast_tamper_detected(self):
  r={'key':'a','current':row(),'result':'pending'};r['forecast_sha256']=P.digest(r);P.check_forecast(r);r['current']['p1_win_prob']=.9
  with self.assertRaises(ValueError):P.check_forecast(r)
 def test_roi_denominator_pending_void_push(self):
  rows=[];out={}
  for key,status,y in [('1','settled',1),('2','settled',0),('3','pending',None),('4','research_void',None)]:
   r={'key':key,'current':row(),'selections':{'current':{'gates':{'side':0,'odds':2.5}}}};rows.append(r);out[key]={'status':status,'y':y}
  m=P.measure(rows,out,'current');self.assertEqual((m['wins'],m['losses'],m['stake'],m['profit'],m['roi_pct'],m['pending_bets'],m['research_void']),(1,1,2,.5,25,1,1))
 def test_push_refund(self):
  r={'key':'a','current':row(),'handicap':{'current':{'status':'priced','p1_conditional':.6,'quote':{'line':-2},'selection':{'side':0,'odds':2}}}}
  m=P.measure([r],{'a':{'status':'settled','margin_p1':2}},'current',market='handicap');self.assertEqual(m['pushes'],1);self.assertEqual(m['stake'],0);self.assertIsNone(m['roi_pct'])
 def test_existing_protocol_hash_changes_block(self):
  with tempfile.TemporaryDirectory() as td:
   out=Path(td);P.atomic(P.folder(out)/'registration.json',{'fingerprint':{'obsolete':True}})
   with patch.object(P,'model_hashes',return_value={}):P.save_capture(R,out,{'state':'compared'},{},[],datetime.now(timezone.utc),source_hashes={},evidence_path=out/'absent')
   self.assertEqual(P.load(P.folder(out)/'health.json')['state'],'blocked')
 def capture_case(self,change=None):
  td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup);out=Path(td.name)
  now=datetime.now(timezone.utc);key=P.fixture(row())
  quote=dict(player1_name='John Alpha',player2_name='Bill Beta',league_name='Test',league='ATP',odds1='1.9',odds2='2.2',kickoff_iso=(now+timedelta(hours=14)).isoformat(),captured_at=(now-timedelta(minutes=3)).isoformat())
  c=dict(state='compared',dependency_hashes={},started_at=(now-timedelta(minutes=1)).isoformat(),snapshot_observed_at=(now-timedelta(hours=1)).isoformat(),snapshot_date=now.date().isoformat(),snapshot_sha256='frozen',source_age_days=0,coverage={key:{'eligible':True}},rows={key:row()},counts={'total':1,'paired':1,'excluded':0},exclusions={})
  if change:change(c,quote,now)
  evidence=out/'test.json.gz';evidence.write_bytes(gzip.compress(json.dumps({'query_responses':[]}).encode()))
  def run():
   with patch.object(P,'model_hashes',return_value={}):P.save_capture(R,out,c,{key:row()},[quote],now,source_hashes={},evidence_path=evidence)
  return out,run,c
 def test_capture_duplicate_does_not_replace(self):
  out,run,c=self.capture_case();run();before=(P.folder(out)/'ledger.json').read_bytes();run();self.assertEqual(before,(P.folder(out)/'ledger.json').read_bytes())
  self.assertEqual(P.load(P.folder(out)/'health.json')['new_observations'],0)
 def test_expired_quote_not_recorded(self):
  out,run,c=self.capture_case(lambda c,q,n:q.update(captured_at=(n-timedelta(hours=3)).isoformat()));run();self.assertFalse((P.folder(out)/'ledger.json').exists())
 def test_future_quote_not_recorded(self):
  out,run,c=self.capture_case(lambda c,q,n:q.update(captured_at=(n+timedelta(minutes=3)).isoformat()));run();self.assertFalse((P.folder(out)/'ledger.json').exists())
 def test_already_started_not_recorded(self):
  out,run,c=self.capture_case(lambda c,q,n:q.update(kickoff_iso=(n-timedelta(seconds=1)).isoformat()));run();self.assertFalse((P.folder(out)/'ledger.json').exists())
 def test_match_starts_during_handicap_pricing(self):
  out,run,c=self.capture_case(lambda c,q,n:q.update(kickoff_iso=(n+timedelta(seconds=5)).isoformat()))
  class Later(datetime):
   @classmethod
   def now(cls,tz=None):return datetime.now(timezone.utc)+timedelta(seconds=20)
  def slow(*args):
   P.datetime=Later
   return {'status':'no_price'}
  original=P.datetime
  try:
   with patch.object(P,'handicap',side_effect=slow):run()
  finally:P.datetime=original
  self.assertFalse((P.folder(out)/'ledger.json').exists())
  self.assertEqual(P.load(P.folder(out)/'health.json')['quote_health']['started_during_handicap_pricing'],1)
 def test_future_source_is_rejected(self):
  out,run,c=self.capture_case(lambda c,q,n:c.update(snapshot_observed_at=n.isoformat()))
  with self.assertRaisesRegex(ValueError,'future_source'):run()
 def test_changed_dependency_rejected(self):
  out,run,c=self.capture_case(lambda c,q,n:c.update(dependency_hashes={'changed':'yes'}))
  with self.assertRaisesRegex(ValueError,'dependencies_changed'):run()
 def test_actual_result_and_immutable_forecast(self):
  out,run,c=self.capture_case();run();dest=P.folder(out);before=(dest/'ledger.json').read_bytes();r=P.load(dest/'ledger.json')[0]
  game=out/'data/oncourt/games_atp.csv';game.parent.mkdir(parents=True);game.write_text('winner_id,loser_id,tour_id,round_id,result,date\n1,2,77,4,6-3 6-4,'+r['kickoff'][:10]+'\n')
  P.settle(out,out);self.assertEqual((dest/'ledger.json').read_bytes(),before);o=P.load(dest/'outcomes.json');self.assertEqual(o[r['key']]['margin_p1'],5)
  rpt=P.report(out);self.assertEqual(rpt['cohorts']['ATP']['current_paired']['gates']['wins'],1)
 def test_wrong_round_or_date_not_joined(self):
  out,run,c=self.capture_case();run();dest=P.folder(out);r=P.load(dest/'ledger.json')[0];game=out/'data/oncourt/games_atp.csv';game.parent.mkdir(parents=True)
  game.write_text('winner_id,loser_id,tour_id,round_id,result,date\n1,2,77,3,6-3 6-4,'+r['kickoff'][:10]+'\n1,2,77,4,6-3 6-4,2026-01-01\n')
  P.settle(out,out);self.assertFalse((dest/'outcomes.json').exists())

if __name__=='__main__':unittest.main()
