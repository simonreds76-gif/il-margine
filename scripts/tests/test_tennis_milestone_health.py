import csv, importlib.util, tempfile, unittest
from pathlib import Path
from datetime import datetime, timezone
spec=importlib.util.spec_from_file_location('milestone_health',Path(__file__).resolve().parents[1]/'tennis-props-pipeline-health.py')
H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)
NOW=datetime(2026,9,30,12,tzinfo=timezone.utc)

class MilestoneTests(unittest.TestCase):
    def health(self,**changes):
        row=dict(event_id='1',date='2026-10-01',bookmaker='Bet365',player='A',opponent='B',market='aces',line='4.5',
                 over_odds='2',under_odds='',capture_ts='2026-09-30T11:00:00Z',match_start_utc='2026-10-01T02:00:00Z',
                 matched_board='yes',price_pair_status='over_only',trackable_shadow='true',bettable='false')
        row.update(changes)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'lines.csv'
            with p.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=row);w.writeheader();w.writerow(row)
            return H.build_health('2026-09-30',p,p,Path(tmp)/'signals.csv',now=NOW)

    def test_milestones_are_not_feed_failures(self):
        for market in ('aces','double_faults','match_aces','match_double_faults'):
            d=self.health(market=market)
            self.assertEqual(d['state'],'MILESTONE_SHADOW_READY')
            self.assertFalse(d['structural_error'])
            self.assertEqual(d['actionable_shadow_rows'],1)
            self.assertEqual(d['actionable_public_rows'],0)
            self.assertFalse(d['market_devig_available'])
    def test_no_qualifying_signal_is_still_valid_feed(self):
        self.assertEqual(self.health(trackable_shadow='false')['state'],'MILESTONE_MARKETS_AVAILABLE')
    def test_stale_and_future_captures_still_block(self):
        for stamp in ('2026-09-29T11:00:00Z','2026-09-30T14:00:00Z',''):
            d=self.health(capture_ts=stamp)
            self.assertTrue(d['structural_error']);self.assertEqual(d['actionable_shadow_rows'],0)
    def test_started_matches_not_actionable(self):
        d=self.health(match_start_utc='2026-09-30T10:00:00Z')
        self.assertEqual(d['actionable_shadow_rows'],0)
    def test_other_markets_do_not_inherit_milestone_exception(self):
        self.assertTrue(self.health(market='player_breaks')['structural_error'])
    def test_unmatched_board_still_fails(self):
        self.assertTrue(self.health(matched_board='no')['structural_error'])

if __name__=='__main__': unittest.main()
