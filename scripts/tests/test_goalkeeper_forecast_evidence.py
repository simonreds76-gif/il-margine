from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from goalkeeper_forecast_evidence import archive, source_hashes


class ForecastEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.json'
        self.source.write_text('{}')
        self.hashes = source_hashes([self.source])
        self.now = datetime(2026, 10, 3, 12, tzinfo=UTC)
        self.params = {'features': [f'x{i}' for i in range(9)], 'alpha': .07}
        self.row = {'event_id': '1', 'goalkeeper': 'Keeper', 'bookmaker': 'Bet365', 'line': '3.5', 'side': 'over',
            'captured_at': (self.now - timedelta(minutes=2)).isoformat(),
            'kickoff_at': (self.now + timedelta(hours=1)).isoformat(),
            '_research_quote': {'odds_decimal': '2.0'}, '_research_features': [1.] * 9,
            'candidate_status': 'no_value'}

    def capture(self, rows=None):
        return archive(self.root / 'evidence', rows if rows is not None else [self.row], self.params, self.hashes, now=self.now)

    def test_nonselected_prices_and_exact_features_are_saved_once(self):
        self.assertEqual(self.capture()['saved'], 1)
        path = next((self.root / 'evidence/packets').glob('*.json'))
        before = path.read_bytes()
        packet = json.loads(before)
        self.assertEqual(packet['offers'][0]['candidate_status'], 'no_value')
        self.assertEqual(packet['offers'][0]['_research_features'], [1.] * 9)
        self.assertEqual(self.capture()['saved'], 0)
        self.assertEqual(path.read_bytes(), before)

    def test_late_stale_future_and_naive_quotes_are_excluded(self):
        for change in ({'kickoff_at': self.now.isoformat()},
                       {'captured_at': (self.now - timedelta(hours=7)).isoformat()},
                       {'captured_at': (self.now + timedelta(minutes=1)).isoformat()},
                       {'captured_at': '2026-10-03T11:59:00'}):
            with self.subTest(change=change):
                self.assertEqual(self.capture([{**self.row, **change}])['saved'], 0)

    def test_changed_sources_block_capture(self):
        self.source.write_text('{"changed":true}')
        self.assertEqual(self.capture()['status'], 'BLOCKED')

    def test_conflicting_contracts_never_saved(self):
        result = self.capture([self.row, {**self.row, '_research_quote': {'odds_decimal': '3.0'}}])
        self.assertEqual(result['saved'], 0)
        self.assertIn('ambiguous_duplicate_contract', result['counts'])

    def test_no_feature_vector_remains_visible_as_blocked(self):
        row = {**self.row, '_research_features': None, 'candidate_status': 'blocked'}
        self.assertEqual(self.capture([row])['saved'], 1)

    def test_invalid_vector_never_saved(self):
        self.assertEqual(self.capture([{**self.row, '_research_features': [float('nan')] * 9}])['saved'], 0)


if __name__ == '__main__':
    unittest.main()
