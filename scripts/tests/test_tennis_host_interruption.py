from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tennis_host_interruption as M
import tennis_runtime_health as R
from ops_morning_failures import failure_message


class RestartTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.now=datetime(2026,11,5,11,tzinfo=timezone.utc)
        self.boot=self.now-timedelta(minutes=40)
        self.start=self.now-timedelta(minutes=55)
        self.row={'run_id':'linked-run','pipeline':'oncourt-am-refresh','host':'laptop-win',
                  'status':'running','started_at':self.start.isoformat(),'details':{'retained':'yes'}}
        R.begin(self.root,'price capture','prices.py',540,now=self.start,run_id='linked-run')
        self.calls=[]
        self.env={'NEXT_PUBLIC_SUPABASE_URL':'https://example.invalid','SUPABASE_SERVICE_ROLE_KEY':'never-log'}
    def transport(self, method, url, headers, payload=None):
        self.calls.append((method,url,payload))
        return [self.row] if method=='GET' else [payload]
    def run_reconcile(self):
        return M.reconcile(self.root,self.env,self.transport,boot=self.boot,now=self.now)
    def test_reboot_classified_before_deadline_expiry(self):
        with patch.object(M,'boot_time',return_value=self.start+timedelta(seconds=40)):
            result=R.summary(self.root,now=self.start+timedelta(seconds=60))
        self.assertEqual(result['issues'][0]['issue'],'HOST_RESTART_INTERRUPTED')
    def test_current_boot_running_or_timeout_keeps_meaning(self):
        with patch.object(M,'boot_time',return_value=self.start-timedelta(hours=1)):
            self.assertEqual(R.summary(self.root,now=self.start+timedelta(seconds=5))['state'],'RUNNING')
            self.assertEqual(R.summary(self.root,now=self.now)['issues'][0]['issue'],'DEADLINE_EXCEEDED')
    def test_completed_attempt_never_relabelled(self):
        token=R.read(next((self.root/R.REL).glob('*.json')))
        R.finish(self.root,token,0,now=self.start+timedelta(seconds=10))
        with patch.object(M,'boot_time',return_value=self.boot):
            self.assertEqual(R.summary(self.root,now=self.now)['state'],'OK')
        self.assertEqual(self.run_reconcile(),[])
        self.assertEqual(self.calls,[])
    def test_missing_or_future_boot_does_not_assert_reboot(self):
        for boot in (None,self.now+timedelta(seconds=1)):
            self.assertFalse(M.interrupted({'status':'RUNNING','started_at':self.start.isoformat()},boot,self.now))
    def test_bad_or_naive_times_fail_closed(self):
        for start in ('broken','2026-11-05T10:00:00',None):
            self.assertFalse(M.interrupted({'status':'RUNNING','started_at':start},self.boot,self.now))
    def test_exact_correlation_and_compare_swap(self):
        receipt=self.run_reconcile()[0]
        self.assertEqual(receipt['run_id'],'linked-run')
        method,url,payload=self.calls[1]
        self.assertEqual(method,'PATCH')
        self.assertIn('status=eq.running',url)
        self.assertIn('details=',url)
        self.assertEqual(payload['status'],'aborted')
        self.assertEqual(payload['error_type'],'HostRestartInterrupted')
        self.assertEqual(payload['details']['retained'],'yes')
        self.assertNotIn('never-log',json.dumps(payload))
        self.assertNotIn('ops_failure_resolution',payload['details'])
    def test_unlinked_other_host_completed_or_new_run_not_changed(self):
        for delta in ({'run_id':'other'}, {'host':'github-actions'}, {'status':'ok'},
                      {'status':'timeout'}, {'pipeline':'other'}, {'started_at':self.now.isoformat()}):
            old=self.row;self.row={**old,**delta};self.calls=[]
            self.assertEqual(self.run_reconcile(),[])
            self.assertEqual(len(self.calls),1)
            self.row=old
    def test_concurrent_completion_not_overwritten(self):
        def transport(method,url,headers,payload=None):
            return [self.row] if method=='GET' else []
        self.assertEqual(M.reconcile(self.root,self.env,transport,boot=self.boot,now=self.now),[])
    def test_alert_names_restart_without_asserting_recovery(self):
        text=failure_message({**self.row,'error_type':'HostRestartInterrupted'})
        self.assertIn('Windows restarted',text)
        self.assertIn('need recovery',text)


if __name__=='__main__':unittest.main()
