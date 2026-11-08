import sys, unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from matchday_saved_schedule import validate_rows
class SavedScheduleTests(unittest.TestCase):
 def setUp(self):
  self.now=datetime(2026,11,8,18,tzinfo=timezone.utc);self.stamp='2026-11-08T17:42:00Z'
  self.row=dict(captured_at=self.stamp,league='Challenger',league_name='Brisbane',player1_name='One',player2_name='Two',match_date='2026-11-09',kickoff_iso='2026-11-09T01:00:00Z')
 def test_valid_exact_capture(self):self.assertEqual(validate_rows([self.row],self.stamp,self.now),[self.row])
 def test_mixed_capture_rejected(self):
  with self.assertRaises(ValueError):validate_rows([{**self.row,'captured_at':'2026-11-07T17:42:00Z'}],self.stamp,self.now)
 def test_stale_or_future_capture_rejected(self):
  for now in (self.now+timedelta(days=2),self.now-timedelta(days=2)):
   with self.assertRaises(ValueError):validate_rows([self.row],self.stamp,now)
 def test_truncated_and_empty_capture_rejected(self):
  for rows in ([],[self.row]*250):
   with self.assertRaises(ValueError):validate_rows(rows,self.stamp,self.now)
if __name__=='__main__':unittest.main()
