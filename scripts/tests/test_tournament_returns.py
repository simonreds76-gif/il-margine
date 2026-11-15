import unittest,importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('returns',Path(__file__).parents[1]/'build-tennis-tournament-returns.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ReturnsTest(unittest.TestCase):
 def test_pair_orientation_and_equal_prices(self):
  rows=[dict(p1='a',p2='b',o1=1.5,o2=3,winner='a',priceBasis='x'),dict(p1='c',p2='d',o1=2.5,o2=1.7,winner='c',priceBasis='x'),dict(p1='e',p2='f',o1=1.9,o2=1.9,winner='e',priceBasis='x')]
  r=m.profit(rows)
  self.assertEqual((r['paired'],r['pickems'],r['bettable']),(3,1,2))
  self.assertEqual(r['favourite']['profit'],-.5);self.assertEqual(r['underdog']['profit'],.5)
  self.assertEqual(r['favourite']['roi'],-25);self.assertEqual(r['underdog']['roi'],25)
 def test_no_bets_not_zero_return(self):self.assertIsNone(m.profit([])['favourite']['roi'])
 def test_only_completed_results(self):
  self.assertTrue(m.complete('7-6(5) 6-4',2));self.assertFalse(m.complete('6-2 2-1 ret.',2));self.assertFalse(m.complete('w/o',2));self.assertFalse(m.complete('6-4 6-4',3))
class EditionCompletionTest(unittest.TestCase):
 def test_completed_final_not_year_controls_status(self):
  row=dict(date='2026-06-21',tour_id='q',round_id='12',winner_id='a',loser_id='b',result='6-4 6-4')
  self.assertEqual(m.edition_completion([row],2)['state'],'completed')
  self.assertEqual(m.edition_completion([row],2)['completedAt'],'2026-06-21')
  self.assertEqual(m.edition_completion([],2)['state'],'unverified')
  self.assertEqual(m.edition_completion([dict(row,result='6-4 2-0')],2)['state'],'unverified')
  self.assertEqual(m.edition_completion([row,row],2)['state'],'unverified')
class TerminalFinalTest(unittest.TestCase):
 def test_retired_final_finishes_event_but_never_enters_roi(self):
  row=dict(date='2026-10-06',tour_id='b',round_id='12',winner_id='a',loser_id='b',result='7-6(3) 0-1 ret.')
  self.assertEqual(m.edition_completion([row],2)['state'],'completed')
  self.assertFalse(m.complete(row['result'],2))
  self.assertEqual(m.edition_completion([dict(row,result='6-4 2-0 suspended')],2)['state'],'unverified')
 def test_official_evidence_is_exact_edition_metadata_only(self):
  edition=dict(id='d',year=2026,event='Dubai',surface='outdoor-hard',completion={'state':'unverified','completedAt':None})
  evidence=[dict(tourId='d',year=2026,event='Dubai',surface='outdoor-hard',completedAt='2026-02-28')]
  self.assertEqual(m.official_completion(evidence,edition,[],'2026-11-15')['state'],'completed')
  self.assertEqual(m.official_completion(evidence,dict(edition,year=2027),[],'2027-11-15')['state'],'unverified')
  self.assertEqual(m.official_completion(evidence,edition,[],'2026-02-27')['state'],'unverified')
  self.assertEqual(m.official_completion(evidence,edition,[{}],'2026-11-15')['state'],'unverified')
if __name__=='__main__':unittest.main()
