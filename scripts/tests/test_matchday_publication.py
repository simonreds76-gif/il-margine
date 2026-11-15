import sys,json,csv,tempfile,unittest,hashlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
from matchup_refresh import prepare_context
from build_matchday_results import build_results
from build_matchday_context import generate

class ContextTests(unittest.TestCase):
 def test_bad_context_is_isolated_and_previous_bytes_retained(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);old=root/'checkout/public/tennis-matchday/context.json';old.parent.mkdir(parents=True);old.write_text('{"version":"saved"}')
   with patch('build_matchday_context.generate',side_effect=ValueError('Verified source hash mismatch')):
    prepare_context(root/'checkout',root/'candidate',{},[],'2026-11-15')
   self.assertEqual(old.read_bytes(),(root/'candidate/release/public/tennis-matchday/context.json').read_bytes())
   self.assertEqual(json.loads((root/'candidate/matchup-private/matchday-context-audit.json').read_text())['status'],'retained_previous')
 def test_failed_first_context_cannot_reuse_old_candidate(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);stale=root/'candidate/release/public/tennis-matchday/context.json';stale.parent.mkdir(parents=True);stale.write_text('{}')
   with patch('build_matchday_context.generate',side_effect=ValueError('bad')):prepare_context(root/'checkout',root/'candidate',{},[],'2026-11-15')
   self.assertFalse(stale.exists())
 def source(self,root):
  def write(name,rows):
   with (root/name).open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
  write('players_atp.csv',[{'id':'1','name':'One Player','birthdate':'2000-01-01'},{'id':'2','name':'Two Player','birthdate':'2000-01-01'}])
  write('tours_atp.csv',[{'id':'a','name':'Challenger Test','rank':'1','court_id':'3'},{'id':'itf','name':'ITF','rank':'0','court_id':'2'}])
  rows=[]
  for idx,(day,score,tour,rd) in enumerate([('2026-11-08','6-4 6-4','a','1'),('2026-11-14','6-4 1-0 ret.','a','9'),('2026-11-13','w/o','a','10'),('2026-11-15','6-0 6-0','a','12'),('2026-11-07','6-0 6-0','a','4'),('2026-11-14','def.','a','5'),('2026-11-14','6-0 6-0','itf','6'),('2026-11-14','6-0 6-0','a','')]):
   rows.append({'winner_id':'1','loser_id':'2','tour_id':tour,'round_id':rd,'date':day,'result':score})
  write('games_atp.csv',rows);write('today_atp.csv',[{'player1_id':'1','player2_id':'2','tour_id':'a','round_id':'12','date':'2026-11-15'}])
  receipt={'state':'VERIFIED','completed_at':'2026-11-15T10:00:00Z','exports':{p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in root.glob('*.csv')}}
  (root/'extraction-status.json').write_text(json.dumps(receipt))
 def test_results_window_status_and_blank_round(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.source(root);data,audit=build_results(root,'2026-11-15')
   self.assertEqual(len(data['matches']),3);self.assertEqual({m['status'] for m in data['matches']},{'completed','retired','walkover'})
   self.assertTrue(any(m['qualifying'] for m in data['matches']));self.assertEqual(audit['excluded'],{'unrecognised_score':1,'invalid_round':1})
   for m in data['matches']:self.assertNotIn('nativeId',m);self.assertNotIn('odds',m);self.assertFalse(m['id'].startswith('oc-'))
 def test_overlapping_result_correction_is_retained_and_audited(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.source(root)
   h={'version':'x','players':[{'id':'a','name':'One Player'},{'id':'b','name':'Two Player'}],'matches':[],'results':[]}
   prior,_=generate(root,h,[],'2026-11-15');prior['results']['matches'][0]['score']='previously verified'
   result,audit=generate(root,h,[],'2026-11-15',prior)
   self.assertIn('previously verified',[m['score'] for m in result['results']['matches']]);self.assertEqual(len(audit['retainedResults']),1)
 def test_winner_change_keeps_the_fixture_id(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.source(root);before,_=build_results(root,'2026-11-15')
   f=root/'games_atp.csv';rows=list(csv.DictReader(f.open(encoding='utf-8')))
   for r in rows:r['winner_id'],r['loser_id']=r['loser_id'],r['winner_id']
   with f.open('w',newline='',encoding='utf-8') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
   after,_=build_results(root,'2026-11-15');self.assertEqual({m['id'] for m in before['matches']},{m['id'] for m in after['matches']})
 def test_mixed_export_rejected_and_wrong_player_contract_not_zero(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.source(root);h={'players':[],'matches':[{'p1':'native','p2':'other'}]}
   with self.assertRaisesRegex(ValueError,'player index'):generate(root,h,[],'2026-11-15')
   (root/'today_atp.csv').write_text('changed')
   with self.assertRaisesRegex(ValueError,'Source changed'):generate(root,{'players':[]},[],'2026-11-15')
if __name__=='__main__':unittest.main()
