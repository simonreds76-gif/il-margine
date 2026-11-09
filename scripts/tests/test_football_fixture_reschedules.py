import copy, importlib.util, json, sys, unittest
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from football_fixture_identity import FixtureIndex
from football_count_reconciliation import reconcile
spec=importlib.util.spec_from_file_location('fix_paired',ROOT/'scripts/team-shots-paired-reference.py')
P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P);V=P.V

def row(day='2026-10-31',home='Lyon',away='Angers',league='ligue-1',**kw):
 return dict(match_date=day,league=league,home_team=home,away_team=away,pick_id=day,match_id=day,**kw)

class FixtureRepairTests(unittest.TestCase):
 def test_reschedule_alias_line_book_and_side_changes_never_register_again(self):
  original=row(book_odds=2.22,result='pending');before=copy.deepcopy(original)
  fresh=row('2026-11-01','Olympique Lyon','Angers SCO',book_odds=1.8,line=10.5,side='under')
  idx=FixtureIndex();out=idx.first_only([original],[fresh,fresh])
  self.assertEqual(out,[before]);self.assertEqual(original,before)
  with patch.object(V,'archive_index',return_value=idx):self.assertEqual(V.merge_shadow_ledger([original],[fresh]),[before])
 def test_genuine_return_leg_next_season_and_other_competition_remain_distinct(self):
  original=row()
  new=[row('2026-11-01','Angers','Lyon'),row('2027-10-31'),row('2026-11-01',league='cup')]
  self.assertEqual(len(FixtureIndex().first_only([original],new)),4)
 def test_cups_do_not_use_one_home_leg_per_season_assumption(self):
  self.assertEqual(len(FixtureIndex().first_only([row(league='cup')],[row('2026-11-01',league='cup')])),2)
 def test_verified_id_bridges_season_boundary_and_wrong_source_id_does_not(self):
  quotes=[dict(row(day),event_id='72036262',source='odds_api_io') for day in ['2026-06-30','2026-07-02']]
  self.assertEqual(len(FixtureIndex(quotes).first_only([row('2026-06-30')],[row('2026-07-02')])),1)
  for q in quotes:q['source']='unknown_native_id'
  self.assertEqual(len(FixtureIndex(quotes).first_only([row('2026-06-30')],[row('2026-07-02')])),2)
 def test_conflicting_provider_id_never_merges_different_clubs(self):
  quotes=[dict(row(),event_id='1',source='odds_api_io'),dict(row(home='Lens'),event_id='1',source='odds_api_io')]
  self.assertEqual(len(FixtureIndex(quotes).first_only([row()],[row(home='Lens')])),2)
 def test_timestamp_keeps_actual_execution_and_reference_first_publication(self):
  old=[dict(pick_id='p',published_at_utc='2026-10-29T10:00:00Z')]; before=copy.deepcopy(old)
  fresh=[dict(pick_id='p',bookmaker='Grosvenor',book_odds=2.1,published_at_utc='2026-10-31T10:00:00Z',price_captured_at_utc='2026-10-31T10:02:00Z',probability_reference_captured_at_utc='2026-10-31T10:00:00Z')]
  V.stamp_publications(old,fresh,datetime(2026,10,31,10,3,tzinfo=timezone.utc))
  self.assertEqual(fresh[0]['price_captured_at_utc'],'2026-10-31T10:02:00Z')
  self.assertEqual(fresh[0]['probability_reference_captured_at_utc'],'2026-10-31T10:00:00Z')
  self.assertEqual(fresh[0]['published_at_utc'],old[0]['published_at_utc']);self.assertEqual(old,before)
 def test_paired_all_four_models_keep_original_no_bet_after_move(self):
  old=row();new=row('2026-11-01');new['models']={m:dict(p_over=.8,minimum_edge=.03) for m in P.MODELS};new.update(odds={'over':2,'under':2},contract_id='new')
  P.select_first_scan([new],[old]);self.assertTrue(all(f['selected_side'] is None for f in new['models'].values()))
 def test_all_four_curves_use_same_settled_rows_and_ignore_pending(self):
  rows=[];base=[]
  for i,actual in [(1,15),(2,5),(3,None)]:
   r=row(f'2026-10-0{i}',home=f'Team{i}');r.update(contract_id=str(i),kickoff_utc=f'2026-10-0{i}T15:00:00Z',team=f'Team{i}',line=10.5,odds={'over':2.,'under':2.},models={m:dict(p_over=.6,mean=12,selected_side='over') for m in P.MODELS});rows.append(r)
   if actual is not None:base.append(dict(date=r['match_date'],league=r['league'],home_team=r['home_team'],away_team=r['away_team'],team=r['team'],shots_for=actual))
  before=copy.deepcopy(rows);s=P.summarize(rows,base,datetime(2026,11,9,tzinfo=timezone.utc))
  for m in P.MODELS:
   h=s['models'][m]['profit_history'];p=s['models'][m]['hypothetical_selections']
   self.assertEqual(h['settled'],p['settled']);self.assertEqual(h['profit'],p['pnl_units']);self.assertEqual([d['cumulative'] for d in h['days']],[1,0]);self.assertEqual(p['pending'],1)
  self.assertEqual(rows,before)
 def test_lyon_overlay_keeps_raw_rows_and_removes_only_verified_repeat(self):
  case=json.loads((ROOT/'config/football-count-reconciliations.json').read_text())['cases'][0]
  rows=[dict(pick_id=case['retained_pick_id'],result='pending'),dict(pick_id=case['duplicate_pick_id'],bookmaker='Bet365',line='10.5',side='under',book_price_at_publication='1.8',result='won',pnl_units='0.8')]
  before=copy.deepcopy(rows);effective,audit=reconcile(rows,ROOT)
  self.assertEqual(effective,[rows[0]]);self.assertEqual(rows,before);self.assertEqual(audit['excluded_duplicates'],1)
  rows[1]['line']='9.5'
  with self.assertRaises(ValueError):reconcile(rows,ROOT)

if __name__=='__main__':unittest.main()
