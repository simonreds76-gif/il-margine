import importlib.util, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'poll-automation-commands.py'
spec = importlib.util.spec_from_file_location('priority_poller', SCRIPT)
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)

class PollerTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name)
  for key,name in [('PRIORITY_REQUEST','priority.json'),('MANUAL_STATUS','status.json')]:
   mock=patch.object(p,key,self.root/name); mock.start(); self.addCleanup(mock.stop)
  self.command={'request_id':'request-1','state':'pending','requested_at':'2026-10-28T20:00:00Z'}
 def test_manual_starts_without_waiting_for_background_tasks(self):
  with patch.object(p,'task_snapshot',return_value={'exists':True,'running':False,'last_result':0}) as snapshot, patch.object(p,'start_task') as start, patch.object(p,'write_command'):
   result=p.process_command(self.command)
  self.assertEqual(result['state'],'started'); start.assert_called_once_with(p.MANUAL_TASK)
  snapshot.assert_called_once_with(p.MANUAL_TASK)
  self.assertEqual(p.read_json_file(p.PRIORITY_REQUEST)['request_id'],'request-1')
 def test_failed_launch_releases_priority(self):
  with patch.object(p,'task_snapshot',return_value={'exists':True,'running':False}),patch.object(p,'start_task',side_effect=RuntimeError('failed')),patch.object(p,'write_command'):
   result=p.process_command(self.command)
  self.assertEqual(result['state'],'failed'); self.assertFalse(p.PRIORITY_REQUEST.exists())
 def receipt(self):
  return {**self.command,'state':'completed','refresh_id':'fresh','started_at':'2026-10-28T20:01:00Z','oncourt_extracted_at':'2026-10-28T20:02:00Z','odds_not_before':'2026-10-28T20:01:00Z','completed_at':'2026-10-28T20:10:00Z','telegram_status':'checked_no_new','telegram_new_signals':0}
 def test_no_new_selections_is_success_without_forcing_resend(self):
  p.write_priority(self.command); p.MANUAL_STATUS.write_text(json.dumps(self.receipt()))
  with patch.object(p,'task_snapshot',return_value={'exists':True,'running':False,'last_result':0}),patch.object(p.subprocess,'run') as run:
   result=p.process_command({**self.command,'state':'started','task':p.MANUAL_TASK,'local_started_at':'2026-10-28T20:01:00Z'})
  self.assertEqual(result['state'],'completed'); self.assertEqual(result['telegram_new_signals'],0)
  self.assertFalse(p.PRIORITY_REQUEST.exists()); run.assert_not_called()
 def test_wrong_request_stale_inputs_or_disabled_alerts_cannot_pass(self):
  for change in [{'request_id':'other'},{'oncourt_extracted_at':'2026-10-27T20:02:00Z'},{'telegram_status':'disabled_for_validation'}]:
   with self.subTest(change=change),self.assertRaises(RuntimeError): p.manual_details(self.command,{**self.receipt(),**change})
 def test_progress_keeps_request_active_until_task_stops(self):
  p.MANUAL_STATUS.write_text(json.dumps({**self.command,'state':'started','phase':'props','progress_message':'Capturing current prices'}))
  with patch.object(p,'task_snapshot',return_value={'exists':True,'running':True}):
   result=p.process_command({**self.command,'state':'started','task':p.MANUAL_TASK})
  self.assertEqual(result['state'],'started'); self.assertEqual(result['phase'],'props')
 def test_scheduler_failure_releases_priority(self):
  p.write_priority(self.command)
  with patch.object(p,'task_snapshot',return_value={'exists':True,'running':False,'last_result':1}):
   result=p.process_command({**self.command,'state':'started','task':p.MANUAL_TASK})
  self.assertEqual(result['state'],'failed'); self.assertFalse(p.PRIORITY_REQUEST.exists())
 def test_never_clears_another_requests_priority(self):
  p.write_priority({**self.command,'request_id':'other'}); p.clear_priority(self.command)
  self.assertTrue(p.PRIORITY_REQUEST.exists())

if __name__=='__main__': unittest.main()
