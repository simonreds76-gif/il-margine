import csv,json,sys,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
S=Path(__file__).resolve().parents[1];sys.path.insert(0,str(S))
import tennis_bookmaker_check as m
class Checks(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.addCleanup(self.tmp.cleanup)
  self.now=datetime(2026,11,14,11,tzinfo=timezone.utc)
  self.config={'market_bookmakers':{'tennis_props':['Sisal IT']},'direct_tennis_grosvenor':True,'direct_moviodds':{'tennis':True}}
  (self.root/'config').mkdir();(self.root/'config/odds-api-bookmaker-allocation.json').write_text(json.dumps(self.config))
  self.inbox=self.root/'data/tennis-props/inbox';self.inbox.mkdir(parents=True)
  self.files={k:self.inbox/(k+'.csv') for k in ['props','most_aces','most_df']}
  self.rows=[dict(date='2026-11-14',tour='ATP',tournament='Stockholm',player1='Taylor Fritz',player2='Thiago Tirante',bookmaker=b,player1_odds=1.7,draw_odds=10.,player2_odds=p,capture_ts=self.now.isoformat(),match_start_utc='2026-11-14T12:00:00Z') for b,p in [('Bet365',2.25),('Grosvenor',2.55),('Sisal IT',2.25)]]
  self.sources={b:{'status':'OK','captured_at':self.now.isoformat()} for b in m.expected_books(self.config)}
 def save(self,rows=None):
  rows=self.rows if rows is None else rows
  for k,p in self.files.items():
   with p.open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(self.rows[0]));w.writeheader()
    if k=='most_aces':w.writerows(rows)
  return m.save_receipt(self.inbox/'bookmaker-check-2026-11-14.json',self.config,self.sources,self.files,self.now.isoformat())
 def sig(self,book='Grosvenor',odds=2.55):
  return SimpleNamespace(performance_source=dict(self.rows[0],bookmaker=book,market='most_aces',recommended_side='P2',selected_odds=odds),scheduled_start_utc='2026-11-14T12:00:00Z',key=('same','fixture'),selection='Tirante')
 def test_all_sources_and_best_price(self):
  self.save();signals,report=m.preflight([self.sig()],self.root,'2026-11-14',now=self.now)
  self.assertEqual(len(signals),1);self.assertEqual(report['accepted'],1);self.assertIn('Grosvenor 2.55',signals[0].selection)
 def test_lower_eligible_price_cannot_escape(self):
  self.save();signals,report=m.preflight([self.sig('Bet365',2.25)],self.root,'2026-11-14',now=self.now)
  self.assertFalse(signals);self.assertEqual(report['checks'][0]['status'],'better_quote_not_evaluated')
 def test_failure_is_explicit_partial_not_absence(self):
  self.sources['Sisal IT']={'status':'SOURCE_FAILED','errors':['Timeout']};self.save(self.rows[:2])
  signals,report=m.preflight([self.sig()],self.root,'2026-11-14',now=self.now)
  self.assertEqual(len(signals),1);self.assertIn('source failed',signals[0].selection);self.assertIn('partial comparison',signals[0].selection)
 def test_missing_attempt_holds_props_only(self):
  del self.sources['Sisal IT'];self.save()
  unrelated=SimpleNamespace(performance_source={},key=(),selection='ML')
  signals,report=m.preflight([self.sig(),unrelated],self.root,'2026-11-14',now=self.now)
  self.assertEqual(signals,[unrelated]);self.assertEqual(report['held'],1)
 def test_stale_receipt(self):
  self.save();_,problem=m.check_receipt(self.root,'2026-11-14',now=self.now+timedelta(minutes=31));self.assertEqual(problem,'bookmaker_check_stale')
 def test_modified_snapshot_is_rejected(self):
  self.save();self.files['props'].write_text('changed');_,problem=m.check_receipt(self.root,'2026-11-14',now=self.now);self.assertEqual(problem,'bookmaker_snapshot_changed')
 def test_changed_configuration_requires_new_attempt(self):
  self.save();self.config['market_bookmakers']['tennis_props'].append('New Book');(self.root/'config/odds-api-bookmaker-allocation.json').write_text(json.dumps(self.config));_,problem=m.check_receipt(self.root,'2026-11-14',now=self.now);self.assertEqual(problem,'bookmaker_configuration_changed')
 def test_no_quotes_cannot_reuse_old_prices(self):
  self.save([]);signals,report=m.preflight([self.sig()],self.root,'2026-11-14',now=self.now);self.assertFalse(signals);self.assertEqual(report['checks'][0]['status'],'selected_quote_not_current')
 def test_reversed_orientation_price_stays_with_player(self):
  self.rows[1].update(player1='Thiago Tirante',player2='Taylor Fritz',player1_odds=2.55,player2_odds=1.7)
  self.save();signals,_=m.preflight([self.sig()],self.root,'2026-11-14',now=self.now);self.assertEqual(len(signals),1)
 def test_different_tournament_is_not_same_contract(self):
  self.rows[1]['tournament']='Paris';self.save();signals,_=m.preflight([self.sig('Bet365',2.25)],self.root,'2026-11-14',now=self.now);self.assertEqual(len(signals),1);self.assertIn('partial comparison',signals[0].selection)
 def test_conflicting_kickoff_holds(self):
  self.rows[1]['match_start_utc']='2026-11-14T13:00:00Z';self.save();signals,report=m.preflight([self.sig()],self.root,'2026-11-14',now=self.now);self.assertFalse(signals);self.assertEqual(report['checks'][0]['status'],'conflicting_current_kickoff')
 def test_errors_not_reported_as_empty_success(self):
  self.assertEqual(m.source_status({'status':'NO_VERIFIED_MARKETS','errors':['catalog:Timeout']},0),'SOURCE_FAILED')
if __name__=='__main__':unittest.main()
