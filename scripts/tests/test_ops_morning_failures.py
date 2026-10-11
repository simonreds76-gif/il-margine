import sys
import unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ops_morning_failures import check_morning_failure

ENV = {'NEXT_PUBLIC_SUPABASE_URL':'https://db.example', 'SUPABASE_SERVICE_ROLE_KEY':'test-key', 'OPS_ALERT_TELEGRAM_BOT_TOKEN':'test-token', 'OPS_ALERT_TELEGRAM_CHAT_ID':'test-chat'}
ROW = {'run_id':'test-run', 'status':'failed', 'started_at':'2026-09-19T10:05:00Z', 'error_type':'ReturnAtlasRefreshFailed', 'details':{'existing':'kept'}}
class MorningFailureTests(unittest.TestCase):
    def test_healthy_latest_run_does_not_send(self):
        transport=Mock(return_value=[{**ROW,'status':'ok'}])
        self.assertFalse(check_morning_failure(ENV,transport))
        self.assertEqual(transport.call_count,1)
    def test_running_does_not_send(self):
        transport=Mock(return_value=[{**ROW,'status':'running'}])
        self.assertFalse(check_morning_failure(ENV,transport))
        self.assertEqual(transport.call_count,1)
    def test_failed_run_sends_and_preserves_details(self):
        transport=Mock(side_effect=[[ROW],{'ok':True},None])
        self.assertTrue(check_morning_failure(ENV,transport))
        calls=transport.call_args_list
        self.assertIn('Return Atlas',calls[1].args[3]['text'])
        self.assertEqual(calls[2].args[0],'PATCH')
        self.assertEqual(calls[2].args[3]['details']['existing'],'kept')
        self.assertIn('ops_failure_notified_at',calls[2].args[3]['details'])
    def test_acknowledged_run_is_not_sent_again(self):
        transport=Mock(return_value=[{**ROW,'details':{'ops_failure_notified_at':'already'}}])
        self.assertTrue(check_morning_failure(ENV,transport))
        self.assertEqual(transport.call_count,1)
    def test_telegram_failure_never_acknowledges(self):
        transport=Mock(side_effect=[[ROW],{'ok':False}])
        with self.assertRaises(RuntimeError): check_morning_failure(ENV,transport)
        self.assertEqual(transport.call_count,2)
    def test_missing_telegram_credentials_is_an_error(self):
        transport=Mock(return_value=[ROW])
        with self.assertRaises(RuntimeError): check_morning_failure({**ENV,'OPS_ALERT_TELEGRAM_BOT_TOKEN':''},transport)
        self.assertEqual(transport.call_count,1)
    def test_missing_morning_record_is_visible_error(self):
        with self.assertRaises(RuntimeError): check_morning_failure(ENV,Mock(return_value=[]))
class VerifiedRecoveryTests(unittest.TestCase):
    def receipt(self):
        return {'run_id': 'test-run', 'method': 'verified_production_deployment',
                'resolved_at': '2026-09-20T12:00:00Z', 'deployment_id': 'dpl_verified',
                'public_url': 'https://ilmargine.bet', 'expected_commit': 'a' * 40,
                'verified_commit': 'a' * 40, 'expected_data_version': 'v1', 'verified_data_version': 'v1'}
    def check(self, receipt, **changes):
        row = {**ROW, 'finished_at': '2026-09-19T11:00:00Z', **changes,
               'details': {'ops_failure_notified_at': 'already', 'ops_failure_resolution': receipt}}
        transport = Mock(return_value=[row])
        result = check_morning_failure(ENV, transport)
        self.assertEqual(transport.call_count, 1)
        return result
    def test_verified_recovery_clears_alert_without_writing_or_sending(self):
        self.assertFalse(self.check(self.receipt()))
    def test_receipt_for_another_run_does_not_clear_failure(self):
        self.assertTrue(self.check({**self.receipt(), 'run_id': 'older-run'}))
    def test_different_error_is_not_cleared(self):
        self.assertTrue(self.check(self.receipt(), error_type='TennisPropsRefreshFailed'))
    def test_unverified_commit_version_or_host_does_not_clear_failure(self):
        for key in ('verified_commit', 'verified_data_version', 'public_url', 'deployment_id', 'method'):
            with self.subTest(key=key):
                self.assertTrue(self.check({**self.receipt(), key: 'wrong'}))
    def test_missing_or_invalid_resolution_time_does_not_clear_failure(self):
        for value in ('', 'wrong', '2026-09-18T12:00:00Z', '2099-01-01T00:00:00Z', '2026-09-20T12:00:00'):
            self.assertTrue(self.check({**self.receipt(), 'resolved_at': value}))

if __name__=='__main__': unittest.main()
