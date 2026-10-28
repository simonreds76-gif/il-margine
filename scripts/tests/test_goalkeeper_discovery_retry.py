"""Regression tests for the 28 October fixture-discovery timeout."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent))
from test_goalkeeper_saves_live import capture


class DiscoveryRetryTests(unittest.TestCase):
    def test_transient_server_errors_retry_but_auth_and_quota_do_not(self):
        for status in (403, 429, 500, 502, 503, 504):
            error = capture.requests.HTTPError("secret URL", response=Mock(status_code=status))
            with self.subTest(status=status), patch.object(capture, 'request_json', side_effect=[error, []]) as get, patch.object(capture.time, 'sleep'):
                if status in (502, 503, 504):
                    self.assertEqual(capture.discover_events({}), ([], 2))
                    self.assertEqual(get.call_count, 2)
                else:
                    with self.assertRaises(capture.DiscoveryFailure) as raised:
                        capture.discover_events({})
                    self.assertNotIn('secret', str(raised.exception))
                    self.assertEqual(get.call_count, 1)

    def test_bad_payload_is_failure_not_empty_market(self):
        with patch.object(capture, 'request_json', return_value={'error': 'bad response'}), patch.object(capture.time, 'sleep') as sleep:
            with self.assertRaises(capture.DiscoveryFailure):
                capture.discover_events({})
            sleep.assert_not_called()

    def test_timeout_recovery_keeps_four_call_limit_and_defers_ten_fixtures(self):
        now = datetime.now(timezone.utc)
        events = [{'id': i, 'league': 'France - Ligue 1', 'date': (now + timedelta(hours=4)).isoformat()} for i in range(1, 31)]
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            args = ['capture', '--history', str(p/'h.csv'), '--status', str(p/'s.json'), '--market-inventory', str(p/'m.csv')]
            with patch.object(sys, 'argv', args), patch.object(capture, 'load_env'), patch.dict(os.environ, {'ODDS_API_KEY': 'test'}), patch.object(capture, 'request_json', side_effect=[capture.requests.ReadTimeout(), events, [], []]) as get, patch.object(capture.time, 'sleep'), patch.object(capture, 'capture_and_merge', return_value=([], {'errors': []})), patch('builtins.print'):
                capture.main()
            status = json.loads((p/'s.json').read_text())
            self.assertEqual(get.call_count, 4)
            self.assertEqual(status['requests_used'], 4)
            self.assertEqual(status['discovery_retries'], 1)
            self.assertEqual(status['events_selected'], 20)
            self.assertEqual(status['events_deferred_by_budget'], 10)
            self.assertEqual(sum(bool(v) for v in status['event_last_checked'].values()), 20)

    def test_repeated_timeout_preserves_history_and_last_success_timestamp(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            (p/'h.csv').write_text('original history\n')
            previous = {'generated_at': '2026-10-28T10:00:00Z', 'last_publication_at': '2026-10-28T10:00:00Z', 'event_last_checked': {'1': 'old'}}
            (p/'s.json').write_text(json.dumps(previous))
            args = ['capture', '--history', str(p/'h.csv'), '--status', str(p/'s.json'), '--market-inventory', str(p/'m.csv')]
            with patch.object(sys, 'argv', args), patch.object(capture, 'load_env'), patch.dict(os.environ, {'ODDS_API_KEY': 'test'}), patch.object(capture, 'request_json', side_effect=capture.requests.ReadTimeout('apiKey=secret')) as get, patch.object(capture.time, 'sleep'), patch.object(capture, 'capture_and_merge') as direct:
                with self.assertRaises(SystemExit) as raised:
                    capture.main()
            self.assertEqual(get.call_count, 2)
            direct.assert_not_called()
            self.assertEqual((p/'h.csv').read_text(), 'original history\n')
            status = json.loads((p/'s.json').read_text())
            self.assertEqual(status['status'], 'FIXTURE_DISCOVERY_FAILED')
            for field in previous:
                self.assertEqual(status[field], previous[field])
            self.assertNotIn('secret', str(raised.exception))
            self.assertNotIn('secret', (p/'s.json').read_text())
            self.assertFalse((p/'m.csv').exists())


if __name__ == '__main__':
    unittest.main()
