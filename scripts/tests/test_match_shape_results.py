import csv,json,tempfile,unittest,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import tennis_match_shape_results as R
NOW=datetime(2026,11,5,23,59,tzinfo=timezone.utc)
class SupplementalTests(unittest.TestCase):
 def write(self,root,name,rows):
  p=root/'data/oncourt'/name;p.parent.mkdir(parents=True,exist_ok=True)
  with p.open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
 def test_walkover_is_exact_fixture_not_completed_win(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.write(root,'today_atp.csv',[dict(tour_id='21362',round_id='6',player1_id='1',player2_id='2',date='2026-11-05',result='w/o')])
   row=dict(fixture_key='21362|6|1|2',quote={'scheduled_start':'2026-11-05T18:00:00Z'})
   extra=R.supplemental(root,[row],NOW);self.assertEqual(extra[row['fixture_key']]['status'],'excluded')
   row['fixture_key']='21361|6|1|2';self.assertEqual(R.supplemental(root,[row],NOW),{})
 def test_replacement_requires_same_edition_round_and_completed_result(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);row=dict(fixture_key='21362|4|1|2',quote={'scheduled_start':'2026-11-03T11:10:00Z'})
   self.write(root,'games_atp.csv',[dict(tour_id='21362',round_id='4',winner_id='3',loser_id='2',date='2026-11-03',result='6-3 6-1')])
   extra=R.supplemental(root,[row],NOW);self.assertIn('opponent_changed',extra[row['fixture_key']]['reason'])
   row['fixture_key']='21362|5|1|2';self.assertEqual(R.supplemental(root,[row],NOW),{})
class ScheduleTests(unittest.TestCase):
 def test_only_exact_blank_date_is_recovered_without_native_mutation(self):
  from tennis_breakpoint_forward import norm
  names={norm('Casper Ruud'):[1],norm('Nuno Borges'):[2]};tours={9:{'name':'Paris','rank':'3','court_id':'3'}}
  row={'tour_id':'9','round_id':'9','player1_id':'1','player2_id':'2','date':'','result':''}
  index=(names,{},tours,[row],{})
  q={'home':'Casper Ruud','away':'Nuno Borges','group':'Paris','captured_at':'2026-11-05T23:00:00Z','scheduled_start':'2026-11-06T19:30:00Z'}
  self.assertTrue(R.resolve_quote(q,index)['native_date_was_blank']);self.assertEqual(row['date'],'')
  for changed in [{**row,'date':'2026-11-07'},{**row,'result':'6-3 6-1'},{**row,'player2_id':'3'}]:
   with self.assertRaises(ValueError):R.resolve_quote(q,(names,{},tours,[changed],{}))
  with self.assertRaises(ValueError):R.resolve_quote(q,(names,{},tours,[row,dict(row)],{}))
if __name__=='__main__':unittest.main()
