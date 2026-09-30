import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tennis_monitor_integrity import ledger_health, timestamp

class IntegrityTests(unittest.TestCase):
    def test_old_unmatched_rows_are_not_current_pending_or_voided(self):
        old=dict(date='2026-08-13',player1='A',player2='B',settlement_status='no_match')
        recent=dict(old,date='2026-09-30',settlement_status='pending')
        settled=dict(old,settlement_status='settled')
        data=ledger_health([old,recent,settled],datetime(2026,9,30,12,tzinfo=timezone.utc))
        self.assertEqual((data['unresolved'],data['overdue'],data['recent_pending']),(2,1,1))
        self.assertEqual(data['issues'][0]['settlement_status'],'no_match')
        self.assertEqual(old['settlement_status'],'no_match')
    def test_aware_scheduled_time_controls_overdue(self):
        row=dict(date='2026-08-13',scheduled_start_utc='2026-09-30T23:00:00Z',settlement_status='pending')
        self.assertEqual(ledger_health([row],datetime(2026,9,30,12,tzinfo=timezone.utc))['overdue'],0)
        self.assertIsNone(timestamp('2026-09-30T10:00:00'))

if __name__=='__main__': unittest.main()
