import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tennis_telegram_delivery as delivery
import tennis_digest_relay as relay


class Connection:
    status = 200
    response = {'ok': True, 'result': {'message_id': 23}}
    connects = 0
    sends = 0
    fail_connect = 0
    fail_response = False
    def __init__(self, *args, **kwargs): pass
    def connect(self):
        Connection.connects += 1
        if Connection.connects <= Connection.fail_connect:
            raise ConnectionResetError('TLS reset')
    def request(self, *args): Connection.sends += 1
    def getresponse(self):
        if Connection.fail_response: raise TimeoutError('lost acknowledgement')
        return self
    def read(self): return json.dumps(self.response).encode()
    def close(self): pass


class Tests(unittest.TestCase):
    def setUp(self):
        Connection.connects = Connection.sends = Connection.fail_connect = 0
        Connection.fail_response = False
        Connection.status = 200
        Connection.response = {'ok': True, 'result': {'message_id': 23}}
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'receipt.json'
    def tearDown(self): self.temp.cleanup()
    def send(self, messages=['summary'], previous=None):
        return delivery.deliver(messages, 'secret', 'chat', self.path, previous, Connection, lambda _: None)
    def test_tls_reset_retries_without_duplicate_send(self):
        Connection.fail_connect = 2
        self.assertEqual(self.send()['status'], 'DELIVERED')
        self.assertEqual((Connection.connects, Connection.sends), (3, 1))
    def test_connection_failure_preserves_safe_retry_receipt(self):
        Connection.fail_connect = 9
        with self.assertRaises(RuntimeError): self.send()
        self.assertEqual(json.loads(self.path.read_text())['status'], 'RETRYABLE_NOT_SENT')
        self.assertEqual(Connection.sends, 0)
    def test_response_timeout_never_retries(self):
        Connection.fail_response = True
        with self.assertRaises(RuntimeError): self.send()
        self.assertEqual(Connection.sends, 1)
        receipt = json.loads(self.path.read_text())
        self.assertEqual(receipt['status'], 'UNKNOWN_DELIVERY')
        with self.assertRaises(RuntimeError): self.send(previous=receipt)
        self.assertEqual(Connection.sends, 1)
    def test_http_error_is_not_success(self):
        Connection.status = 403
        Connection.response = {'ok': False}
        with self.assertRaises(RuntimeError): self.send()
        self.assertEqual(json.loads(self.path.read_text())['status'], 'REJECTED')
    def test_ok_without_message_id_is_not_success(self):
        Connection.response = {'ok': True, 'result': {}}
        with self.assertRaises(RuntimeError): self.send()
    def test_batch_validation_precedes_any_send(self):
        with self.assertRaises(ValueError): self.send(['valid', 'x' * 4097])
        self.assertEqual(Connection.sends, 0)
    def test_resume_skips_acknowledged_chunk(self):
        messages = ['a', 'b']
        receipt = {'payload_sha256': delivery.digest(messages), 'status': 'RETRYABLE_NOT_SENT',
                   'messages': [{'index': 0, 'message_id': 99}]}
        self.assertEqual(len(self.send(messages, receipt)['messages']), 2)
        self.assertEqual(Connection.sends, 1)
    def test_receipt_cannot_be_reused_for_other_payload(self):
        with self.assertRaises(ValueError): self.send(['other'], self.send())
    def test_completed_batch_is_not_resent(self):
        receipt = self.send()
        self.send(previous=receipt)
        self.assertEqual(Connection.sends, 1)
    def test_local_outbox_acknowledges_workflow_completion(self):
        root = Path(self.temp.name)
        def mock_gh(*args, **kwargs):
            if args[:2] == ('workflow', 'run'): return ''
            state = json.loads(next((root/'data/backtest/tennis-telegram-outbox').glob('*.json')).read_text())
            return json.dumps([{'databaseId': 123, 'displayTitle': 'tennis-delivery-'+state['delivery_id'],
                                'status':'completed','conclusion':'success'}])
        with patch.object(relay, 'gh', side_effect=mock_gh) as call:
            kw = dict(root=root,repository='a/b',workflow='digest.yml',ref='test',encoded='x')
            self.assertEqual(relay.confirmed_dispatch(['summary'], **kw)['status'], 'DELIVERED')
            self.assertEqual(relay.confirmed_dispatch(['summary'], **kw)['run_id'], 123)
            self.assertEqual(sum(c.args[:2]==('workflow','run') for c in call.call_args_list),1)
    def test_dispatch_timeout_is_not_repeated(self):
        kw = dict(root=Path(self.temp.name),repository='a/b',workflow='digest.yml',ref='test',encoded='x',wait_seconds=0)
        with patch.object(relay,'gh',side_effect=relay.DeliveryPending('timeout')):
            with self.assertRaises(relay.DeliveryPending): relay.confirmed_dispatch(['summary'], **kw)
        with patch.object(relay,'gh',return_value='[]') as call:
            with self.assertRaises(relay.DeliveryPending): relay.confirmed_dispatch(['summary'], **kw)
            self.assertTrue(all(c.args[0]!='workflow' for c in call.call_args_list))


if __name__ == '__main__': unittest.main()
