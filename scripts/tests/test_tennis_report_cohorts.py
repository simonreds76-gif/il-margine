"""Prevent misleading evidence summaries without loading private live ledgers."""
import ast
from pathlib import Path
import unittest

source = (Path(__file__).resolve().parents[1] / 'weekly-research-report.py').read_text(encoding='utf-8')
tree = ast.parse(source)
selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('rate_trend_text', 'v4_cohort_text')]
namespace = {'Any': object, 'evidence_freshness': lambda *a, **k: {'status': 'FRESH'}}
exec(compile(ast.Module(body=selected, type_ignores=[]), '<report functions>', 'exec'), namespace)

class ReportCohortTests(unittest.TestCase):
    def test_v4_observations_are_not_bets_or_pooled_training(self):
        text = namespace['v4_cohort_text']({'history_cohorts': [
            {'version':'legacy-unversioned','settled':241},
            {'version':'current','settled':42}], 'signals_settled':0})
        self.assertIn('current: 42 settled observations', text)
        self.assertIn('0 settled v4 selections', text)
        self.assertIn('before the forecast month', text)
        self.assertNotIn('283', text)

    def test_trend_results_keep_versions_and_line_counts_separate(self):
        item = lambda roi: {'independent_fixtures':17, 'candidate':{'bets':13,'roi_pct':roi}}
        text = namespace['rate_trend_text']({'tennis_rate_trend': {
            'markets': {'aces':item(99)}, 'history_versions': {
                'legacy-unversioned':{'aces':item(-49)}, 'current':{'aces':item(-65)}}}})
        self.assertIn('[current]: 17 settled fixtures', text)
        self.assertIn('Astra ROI -65.0% (13 selected lines)', text)
        self.assertIn('[legacy archive]', text)
        self.assertNotIn('+99.0%', text)
        self.assertIn('correlated', text)

    def test_unversioned_input_does_not_claim_corrected_cohort(self):
        text = namespace['rate_trend_text']({'tennis_rate_trend': {'markets':{'aces':{}}}})
        self.assertIn('mixed/unversioned archive', text)

    def test_v3_count_test_is_not_presented_as_betting_approval(self):
        self.assertIn("betting evidence {proof.get('status', 'UNKNOWN')}; count test", source)

if __name__ == '__main__': unittest.main()
