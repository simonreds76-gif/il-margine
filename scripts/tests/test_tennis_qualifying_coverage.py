import sys,unittest
from pathlib import Path
from datetime import datetime,date,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tennis_qualifying_coverage as Q

class QualifyingTests(unittest.TestCase):
    def test_beijing_not_limited_to_masters_list(self):
        self.assertEqual(Q.event_key('China Open - Beijing'),Q.event_key('ATP Beijing - Qualifiers'))
        self.assertIsNone(Q.event_key('WTA Beijing - Qualifiers'))
        target=date(2026,9,27)
        tours=Q.current_tours([dict(id='1',name='China Open - Beijing',date='2026-09-28',rank='3',court_id='1')],target)
        schedule=[dict(tour_id='1',date='2026-09-27',player1_id='10',player2_id='20',round_id='2')]
        missing=Q.missing_qualifier_keys(schedule,tours,[],target)
        self.assertIn('beijing',missing)
        self.assertIn(9,Q.fallback_leagues([dict(id=9,name='ATP Beijing - Qualifiers')],missing))
        market=dict(player1_name='A',player2_name='B',league_name='ATP Beijing - Qualifiers',odds1=2,odds2=2,kickoff_iso='2026-09-27T10:00:00Z')
        resolver=lambda name: ({'A':10,'B':20}[name],None)
        before=Q.schedule_coverage(schedule,tours,[market],resolver,target,datetime(2026,9,27,9,tzinfo=timezone.utc))
        self.assertEqual(before[0]['with_current_prices'],1)
        after=Q.schedule_coverage(schedule,tours,[market],resolver,target,datetime(2026,9,27,11,tzinfo=timezone.utc))
        self.assertEqual(after[0]['missing_prices'],1)

if __name__=='__main__':unittest.main()
