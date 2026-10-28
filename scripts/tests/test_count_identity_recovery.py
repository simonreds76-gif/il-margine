import copy,csv,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from football_team_names import football_form_team_key as key
from football_count_results import count_result_index,exact_result,identity
def load(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/'scripts'/path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
V=load('identity_vnext','publish-football-vnext-shadow.py')
S=load('identity_settle','settle-football-research-lanes.py')
NOW=datetime(2026,10,28,20,tzinfo=timezone.utc)

class CountIdentityRecovery(unittest.TestCase):
 def test_shared_keys_and_idempotence(self):
  pairs=[('Stade Rennais FC','Rennes'),('Strasbourg Alsace','Strasbourg'),('Lazio Rome','Lazio'),
   ('Tottenham Hotspur','Tottenham'),('Inter Milano','Inter'),('1. FC Cologne','Koln'),
   ('TSG Hoffenheim','Hoffenheim'),('SC Paderborn 07','Paderborn'),('Bayer Leverkusen','Leverkusen'),
   ('Nottingham Forest','Nott\'m Forest'),('Deportivo Alaves','Alaves'),('Ipswich Town','Ipswich')]
  for a,b in pairs:
   self.assertEqual(key(a),key(b),(a,b));self.assertEqual(V.PUB.team_key(a),V.PUB.team_key(b))
   self.assertEqual(key(key(a)),key(a))
  self.assertNotEqual(key('Paris FC'),key('Paris Saint-Germain'))

 def fixture(self):
  return dict(pick_id='old-id',match_id='old-match-id',match_date='2026-10-25',league='ligue-1',
   home_team='Stade Rennais FC',away_team='Strasbourg Alsace',team='Stade Rennais FC',
   kickoff_utc='2026-10-25T16:15:00Z',line='16.5',side='over',book_price_at_publication='2.02',result='pending')

 def test_identity_repair_never_adds_second_selection(self):
  old=self.fixture();old['result']='lost';old['pnl_units']=-1
  new=dict(old,pick_id='new-id',match_id='new-id',home_team='Rennes',away_team='Strasbourg',book_price_at_publication='3.00')
  self.assertEqual(V.merge_shadow_ledger([old],[new]),[old])

 def test_exact_date_league_orientation_and_conflicts(self):
  r=self.fixture();e=dict(home_shots=15,away_shots=12,observed_at=NOW.isoformat(),source='football-data',evidence_path='saved.json')
  index={identity(r):e};self.assertIsNotNone(exact_result(r,index,NOW))
  for changed in [dict(r,match_date='2026-10-26'),dict(r,league='epl'),dict(r,home_team=r['away_team'],away_team=r['home_team'])]:
   self.assertIsNone(exact_result(changed,index,NOW))
  self.assertIsNone(exact_result(r,{identity(r):dict(e,conflicting_counts=['home_shots'])},NOW))
  self.assertIsNone(exact_result(r,index,datetime(2026,10,25,17,tzinfo=timezone.utc)))

 def test_pending_settles_without_rewriting_prices_or_settled_loss(self):
  r=self.fixture();old=dict(r,pick_id='settled',result='lost',pnl_units=-1,actual_team_shots=19)
  before=copy.deepcopy(old);e=dict(home_shots=15,away_shots=12,observed_at=NOW.isoformat(),source='football-data',evidence_path='saved.json')
  self.assertEqual(S.settle_team_shots([r,old],{},exact_results={identity(r):e}),1)
  self.assertEqual((r['result'],r['pnl_units'],r['actual_team_shots']),('lost',-1,15))
  self.assertEqual(r['book_price_at_publication'],'2.02');self.assertEqual(old,before)

 def test_reciprocal_base_fallback_and_disagreement_hold(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);path=root/'data/football-form/team-match-base.csv';path.parent.mkdir(parents=True)
   a=dict(date='2026-10-25',league='ligue-1',home_team='Rennes',away_team='Strasbourg',team='Rennes',opponent='Strasbourg',venue='home',shots_for=15,shots_against=12,match_source='fotmob_verified_fulltime')
   b=dict(a,team='Strasbourg',opponent='Rennes',venue='away',shots_for=12,shots_against=15)
   def write(rows):
    with path.open('w',newline='') as h:w=csv.DictWriter(h,fieldnames=list(a));w.writeheader();w.writerows(rows)
   write([a,b]);self.assertEqual(count_result_index(root,NOW)[identity(self.fixture())]['home_shots'],15)
   write([a]);self.assertEqual(count_result_index(root,NOW),{})
   write([a,dict(b,shots_against=99)]);self.assertEqual(count_result_index(root,NOW),{})
   write([dict(a,match_source='forecast'),dict(b,match_source='forecast')]);self.assertEqual(count_result_index(root,NOW),{})

 def test_frozen_dispersion_uses_same_team_after_alias_repair(self):
  p=dict(team_alpha={'serie-a|internazionale':{'alpha':.123}},league_alpha={'serie-a':.9},pooled_alpha=.8)
  self.assertEqual(V.team_alpha(p,'serie-a','Inter Milano'),.123)

if __name__=='__main__':unittest.main()
