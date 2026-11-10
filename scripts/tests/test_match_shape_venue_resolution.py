import sys, unittest, copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tennis_match_shape_results import resolve_quote
from tennis_breakpoint_forward import norm
class VenueTests(unittest.TestCase):
 def setUp(self):
  self.q=dict(home='Adrian Mannarino',away='Alexander Shevchenko',group='Stockholm Open',scheduled_start='2026-11-10T12:00:00Z',captured_at='2026-11-10T10:15:00Z')
  self.t=dict(id='21363',name='BNP Paribas Nordic Open - Stockholm',court_id='3',date='2026-11-09',rank='2')
  self.r=dict(tour_id='21363',round_id='4',player1_id='1',player2_id='2',date='2026-11-10',result='')
 def index(self,rows=None,tour=None):return ({norm(self.q['home']):[1],norm(self.q['away']):[2]}, {},{21363:tour or self.t},rows or [self.r],{'fixture':'unchanged'})
 def test_sponsor_variant(self):
  before=copy.deepcopy((self.q,self.index()));x=resolve_quote(self.q,self.index());self.assertEqual(x['edition_id'],'21363');self.assertEqual(x['venue_event_key'],'stockholm');self.assertEqual(before,(self.q,self.index()))
 def test_blank_date(self):
  self.r['date']='';x=resolve_quote(self.q,self.index());self.assertTrue(x['native_date_was_blank'])
 def test_different_date(self):
  self.r['date']='2026-11-11'
  with self.assertRaises(ValueError):resolve_quote(self.q,self.index())
 def test_wrong_opponent(self):
  self.r['player2_id']='3'
  with self.assertRaises(ValueError):resolve_quote(self.q,self.index())
 def test_wrong_event(self):
  self.q['group']='Vienna Open'
  with self.assertRaises(ValueError):resolve_quote(self.q,self.index())
 def test_ambiguous_event_name(self):
  self.t['name']='Lyon BNP Paribas Nordic Open - Stockholm'
  with self.assertRaises(ValueError):resolve_quote(self.q,self.index())
 def test_duplicate_rounds(self):
  with self.assertRaises(ValueError):resolve_quote(self.q,self.index(rows=[self.r,{**self.r,'round_id':'5'}]))
 def test_finished(self):
  self.r['result']='6-4 6-4'
  with self.assertRaises(ValueError):resolve_quote(self.q,self.index())
 def test_challenger(self):
  self.t['name']='Stockholm Challenger';self.t['rank']='1'
  with self.assertRaises(ValueError):resolve_quote(self.q,self.index())
 def test_qualifying(self):
  self.r['round_id']='2';self.assertEqual(resolve_quote(self.q,self.index())['phase'],'qualifying')
 def test_unsupported_future_season(self):
  self.t['date']='2027-11-09'
  with self.assertRaises(ValueError):resolve_quote(self.q,self.index())
 def test_old_exact_path(self):
  self.q['group']='Stockholm';x=resolve_quote(self.q,self.index());self.assertEqual(x['edition_id'],'21363')
 def test_quote_after_start(self):
  self.q['captured_at']='2026-11-10T12:01:00Z'
  with self.assertRaises(ValueError):resolve_quote(self.q,self.index())
if __name__=='__main__':unittest.main()

