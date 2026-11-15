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
if __name__=='__main__':unittest.main()
