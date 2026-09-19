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
if __name__=='__main__': unittest.main()
