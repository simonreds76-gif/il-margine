import importlib.util,json,unittest
from pathlib import Path
from unittest.mock import Mock,patch
p=Path(__file__).parents[1]/'run-fair-odds-refresh.py';s=importlib.util.spec_from_file_location('refresh_stamp',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_counts_must_agree(self):
  self.assertEqual(m.refresh_count('Computed 46 fair odds rows\n Synced daily_fair_odds: 46 current / 46 updated'),46)
  for text in ('','Computed 46 fair odds rows','Computed 46 fair odds rows\n Synced daily_fair_odds: 45 current'):
   with self.assertRaises(RuntimeError):m.refresh_count(text)
 def test_only_timestamp_written_to_current_table(self):
  old={'id':'abc','computed_at':'2026-11-11T10:00:00+00:00','p1_win_prob':.6};stamp='2026-11-12T12:00:00+00:00'
  with patch.object(m.requests,'get',side_effect=[Mock(ok=True,json=lambda:[old]),Mock(ok=True,json=lambda:[{**old,'computed_at':stamp}])]),patch.object(m.requests,'patch',return_value=Mock(ok=True)) as write:
   m.stamp_current('https://example.invalid',{},1,stamp)
  self.assertEqual(write.call_args.kwargs['json'],{'computed_at':stamp});self.assertEqual(write.call_args.args[0],'https://example.invalid/rest/v1/daily_fair_odds')
 def test_count_mismatch_does_not_write(self):
  with patch.object(m.requests,'get',return_value=Mock(ok=True,json=lambda:[])),patch.object(m.requests,'patch') as write:
   with self.assertRaises(RuntimeError):m.stamp_current('https://example.invalid',{},1,'2026-11-12T12:00:00+00:00')
  write.assert_not_called()
 def test_changed_prices_fail_readback(self):
  old={'id':'abc','p1_win_prob':.6};stamp='2026-11-12T12:00:00+00:00'
  with patch.object(m.requests,'get',side_effect=[Mock(ok=True,json=lambda:[old]),Mock(ok=True,json=lambda:[{**old,'p1_win_prob':.9,'computed_at':stamp}])]),patch.object(m.requests,'patch',return_value=Mock(ok=True)):
   with self.assertRaisesRegex(RuntimeError,'values changed'):m.stamp_current('https://example.invalid',{},1,stamp)
if __name__=='__main__':unittest.main()
