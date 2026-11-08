import csv,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build_matchday_supplement import build

class SupplementTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  self.people=[dict(id='1',name='Player One',birthdate='2000-01-01',country='USA'),dict(id='2',name='Player Two',birthdate='2001-01-01',country='GBR')]
  self.tours=[dict(id='10',name='Test Challenger',rank='1',court_id='3')]
  self.games=[dict(winner_id='1',loser_id='2',tour_id='10',round_id='4',result='6-4 6-3',date='2026-11-01')]
  self.schedule=[dict(league='Challenger',match_date='2026-11-09',player1_name='Player One',player2_name='Player Two')]
 def tearDown(self):self.temp.cleanup()
 def run_build(self,old=None):
  for filename,rows in [('players_atp.csv',self.people),('tours_atp.csv',self.tours),('games_atp.csv',self.games)]:
   with (self.root/filename).open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
  return build(self.root,self.schedule,[],'2026-11-08',old)
 def test_real_record_and_idempotence(self):
  r,a=self.run_build();self.assertEqual(a['matches'],1);self.assertEqual(r,self.run_build(r)[0]);self.assertEqual(next(iter(r['pairs'].values()))['matches'][0]['odds'],[None,None])
 def test_ambiguous_names_are_not_merged(self):
  self.people.append({**self.people[0],'id':'3'});r,a=self.run_build();self.assertEqual(a['pairs'],0)
 def test_old_namesake_is_rejected(self):
  self.people[0]['birthdate']='1950-01-01';r,a=self.run_build();self.assertEqual(a['pairs'],0)
 def test_inactive_name_is_rejected(self):
  self.games[0]['date']='2020-01-01';r,a=self.run_build();self.assertEqual(a['pairs'],0)
 def test_retirement_and_junior_excluded(self):
  self.games.extend([{**self.games[0],'round_id':'5','result':'6-4 1-0 ret.','date':'2026-11-02'},
                     {**self.games[0],'tour_id':'11','date':'2026-11-03'}]);self.tours.append({**self.tours[0],'id':'11','name':'Test Junior'})
  r,a=self.run_build();self.assertEqual(a['matches'],1)
 def test_source_correction_preserves_record_and_quarantines_only_pair(self):
  old,_=self.run_build();self.games[0]['result']='6-0 6-0';new,_=self.run_build(old)
  p=next(iter(new['pairs'].values()));self.assertEqual(p['matches'],next(iter(old['pairs'].values()))['matches']);self.assertEqual(p['quarantined'],'result_changed')
 def test_later_result_is_appended(self):
  old,_=self.run_build();self.games.append({**self.games[0],'tour_id':'12','date':'2026-11-07'});self.tours.append({**self.tours[0],'id':'12'})
  new,a=self.run_build(old);self.assertEqual(a['matches'],2)

 def test_completed_fixture_is_confirmed_by_native_pair_event_and_date(self):
  old,_=self.run_build()
  request={'pair':'player one|player two','date':'2026-11-01','event':'ATP Challenger Test - R1'}
  _,audit=build(self.root,[],[],'2026-11-08',old,[request])
  self.assertEqual(audit['postMatchChecks'][0]['status'],'confirmed')
 def test_missing_result_is_reported_without_fabricating_or_removing_records(self):
  old,_=self.run_build()
  request={'pair':'player one|player two','date':'2026-11-04','event':'ATP Challenger Other - R1'}
  new,audit=build(self.root,[],[],'2026-11-08',old,[request])
  self.assertEqual(audit['postMatchChecks'][0]['status'],'overdue_result')
  self.assertEqual(new,old)

 def test_next_day_updates_retained_pair_without_schedule_or_history_rewrite(self):
  old,audit=self.run_build()
  self.games.append({**self.games[0],'date':'2026-11-08','round_id':'5'})
  self.run_build()  # write the updated source fixture
  new,next_audit=build(self.root,[],[],'2026-11-09',old,audit['requests'])
  pair=next(iter(new['pairs'].values()))
  self.assertEqual(len(pair['matches']),2)
  self.assertEqual(pair['matches'][0],next(iter(old['pairs'].values()))['matches'][0])
  self.assertEqual(pair['checkedThrough'],'2026-11-09')
  self.assertEqual(next_audit['requests'],audit['requests'])

if __name__=='__main__':unittest.main()

