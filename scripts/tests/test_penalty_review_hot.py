from pathlib import Path
import sys
import unittest
from unittest.mock import Mock,patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from penalty_review_hot import merge_rows,notify

def row(mid,date='2026-10-25'):
    return {'date':date,'actual_taker':'Player','event_evidence':[{'match_id':str(mid)}]}

class HotPenaltyTests(unittest.TestCase):
    def test_retains_other_matches_and_replaces_exact_fixture(self):
        old=[row(1),row(2)];fresh=[{**row(2),'actual_taker':'Correct player'}]
        result=merge_rows(old,fresh,{'2'},'2026-10-17')
        self.assertEqual(len(result),2);self.assertIn(row(1),result);self.assertIn(fresh[0],result)
    def test_failed_fixture_keeps_prior_evidence(self):
        self.assertEqual(merge_rows([row(1)],[],set(),'2026-10-17'),[row(1)])
    def test_verified_no_penalty_removes_stale_fixture(self):
        self.assertEqual(merge_rows([row(1)],[],{'1'},'2026-10-17'),[])
    def test_prunes_only_expired_window(self):
        self.assertEqual(merge_rows([row(1,'2026-10-01'),row(2)],[],set(),'2026-10-17'),[row(2)])
    def test_existing_undelivered_recent_rows_are_retried(self):
        older=row(1,'2026-10-24');recent=row(2)
        a=SimpleNamespace(DEFAULT_ALERT_STATE=Path('state.json'),REVIEW_FILES=[],
            load_alert_state=Mock(return_value={'items':{'already_sent':{}}}),load_reviews=Mock(return_value={'tickets':{}}),
            previous_rows=Mock(return_value=[older,recent]),current_rows=Mock(return_value=[older,recent]),
            priority_hierarchy_teams=Mock(return_value={}),new_actionable_rows=Mock(return_value=[]))
        with patch('penalty_review_hot.load',return_value=a),patch.object(Path,'exists',return_value=False):
            notify(Path('/isolated'),dry_run=True)
        args=a.new_actionable_rows.call_args.args
        self.assertEqual(args[1],[older]);self.assertEqual(args[3],{'already_sent'});a.load_reviews.assert_called_once()

if __name__=='__main__':unittest.main()
