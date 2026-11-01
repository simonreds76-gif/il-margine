import importlib.util
from pathlib import Path
import sys,tempfile,unittest,subprocess,json,os
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
S=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(S))
import tennis_runtime_health as M

class RuntimeHealthTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.now=datetime(2026,11,2,tzinfo=timezone.utc)
 def begin(self,label='Current board',**kw):return M.begin(self.root,label,'board.py',10,now=self.now,**kw)
 def test_success_records_last_success_and_duration(self):
  t=self.begin();M.finish(self.root,t,0,now=self.now+timedelta(seconds=4))
  s=M.summary(self.root,now=self.now+timedelta(seconds=5));self.assertEqual(s['state'],'OK')
  self.assertEqual(s['steps'][0]['duration_seconds'],4);self.assertIsNotNone(s['steps'][0]['last_success_at'])
 def test_timeout_remains_visible_after_unrelated_success(self):
  t=self.begin();M.finish(self.root,t,124,now=self.now+timedelta(seconds=10))
  other=self.begin('Weekly report');M.finish(self.root,other,0,now=self.now+timedelta(seconds=11))
  s=M.summary(self.root);self.assertEqual(s['state'],'DEGRADED');self.assertEqual(s['issues'][0]['issue'],'TIMED_OUT')
 def test_recovery_requires_same_step_success(self):
  t=self.begin();M.finish(self.root,t,0,now=self.now)
  t=self.begin();M.finish(self.root,t,124,now=self.now)
  t=self.begin();s=M.summary(self.root,now=self.now);self.assertEqual(s['issues'][0]['issue'],'RETRYING_AFTER_FAILURE')
  self.assertEqual(s['issues'][0]['last_success_at'],self.now.isoformat())
  M.finish(self.root,t,0,now=self.now);self.assertEqual(M.summary(self.root)['issues'],[])
 def test_killed_parent_is_detected_without_final_receipt(self):
  self.begin();s=M.summary(self.root,now=self.now+timedelta(seconds=41))
  self.assertEqual(s['issues'][0]['issue'],'DEADLINE_EXCEEDED')
 def test_running_within_budget_is_not_failure(self):
  self.begin();s=M.summary(self.root,now=self.now+timedelta(seconds=5))
  self.assertEqual(s['state'],'RUNNING');self.assertEqual(s['issues'],[])
 def test_corrupt_health_does_not_look_healthy(self):
  t=self.begin();(self.root/M.REL/(t['step_id']+'.json')).write_text('broken')
  self.assertEqual(M.summary(self.root)['issues'][0]['issue'],'HEALTH_READ_FAILED')
 def test_old_attempt_cannot_overwrite_newer_run(self):
  old=self.begin();new=self.begin()
  with self.assertRaises(RuntimeError):M.finish(self.root,old,0)
  M.finish(self.root,new,0)
 def test_run_check_does_not_blame_previous_unrelated_research(self):
  t=self.begin('History',run_id='old');M.finish(self.root,t,124)
  t=self.begin(run_id='new');M.finish(self.root,t,0)
  self.assertEqual(M.summary(self.root,run_id='new')['issues'],[])
  self.assertEqual(len(M.summary(self.root)['issues']),1)
 def test_no_qualifying_selections_is_valid_success(self):
  result=M.observed_run([sys.executable,'-c','print("NO_QUALIFYING_SELECTIONS")'],root=self.root,label='Paper scan',timeout=5,capture_output=True)
  self.assertEqual(result.returncode,0);self.assertEqual(M.summary(self.root)['issues'],[])
 def test_real_timeout_has_durable_failure(self):
  with self.assertRaises(subprocess.TimeoutExpired):
   M.observed_run([sys.executable,'-c','import time;time.sleep(10)'],root=self.root,label='Injected timeout',timeout=.1,capture_output=True)
  self.assertEqual(M.summary(self.root)['issues'][0]['issue'],'TIMED_OUT')
 def test_launch_failure_recorded(self):
  with self.assertRaises(OSError):M.observed_run(['nonexistent-tennis-test-command'],root=self.root,label='Launch',timeout=1)
  self.assertEqual(M.summary(self.root)['issues'][0]['issue'],'FAILED')
 def test_exit_zero_cannot_erase_other_stage_failure(self):
  M.observed_run([sys.executable,'-c','raise SystemExit(9)'],root=self.root,label='Broken child',timeout=3)
  M.observed_run([sys.executable,'-c','pass'],root=self.root,label='Other child',timeout=3)
  self.assertEqual(len(M.summary(self.root)['issues']),1)
 def test_command_secrets_not_written(self):
  M.observed_run([sys.executable,'-c','pass','private-token-value'],root=self.root,label='Safe label',timeout=5)
  self.assertNotIn('private-token-value',''.join(p.read_text() for p in (self.root/M.REL).glob('*.json')))
 def test_snapshot_exposes_failure_without_changing_feed_counts(self):
  t=self.begin();M.finish(self.root,t,124)
  out=M.overlay_feed_health({'state':'READY','matched_rows':87},M.summary(self.root))
  self.assertEqual(out['matched_rows'],87);self.assertEqual(out['state'],'RUNTIME_STEP_FAILED')
 def test_close_to_budget_is_visible_but_not_an_outage(self):
  t=self.begin();M.finish(self.root,t,0,now=self.now+timedelta(seconds=9))
  s=M.summary(self.root);self.assertEqual(len(s['near_budget']),1);self.assertEqual(s['state'],'OK')

if __name__=='__main__':unittest.main()
