import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
SCRIPTS=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(SCRIPTS))
spec=importlib.util.spec_from_file_location('fast_digest',SCRIPTS/'tennis-daily-signal-digest.py')
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)

class DedupTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.state=self.root/'state.json'; self.receipt=self.root/'receipt.json'
  self.signal=m.Signal('CORE',0,['STRICT'],'A vs B','A ML @2',10,key=('2026-10-29','a','b','a','ML','',''))
 def check(self,day='2026-10-28',signals=None,dispatch=None):
  argv=['digest','--date',day,'--state',str(self.state),'--report',str(self.root/'report.txt'),'--receipt',str(self.receipt)]
  with patch.object(sys,'argv',argv),patch('tennis_astrissimo.alerts'),patch.object(m,'collect_upcoming_signals',return_value=(signals if signals is not None else [self.signal],[])),patch.object(m,'attach_performance'),patch.object(m,'retain_dispatch'),patch.object(m,'dispatch',side_effect=dispatch) as send:
   result=m.main()
  return result,send.call_count
 def test_repeat_repricing_and_next_day_do_not_duplicate(self):
  self.assertEqual(self.check(),(0,1))
  self.assertEqual(self.check(),(0,0))
  self.assertEqual(self.check('2026-10-29'),(0,0))
  self.assertEqual(json.loads(self.receipt.read_text())['dispatched_count'],0)
 def test_zero_selections_still_writes_checked_receipt(self):
  self.assertEqual(self.check(signals=[]),(0,0))
  self.assertEqual(json.loads(self.receipt.read_text())['status'],'checked_no_new')
 def test_new_prop_does_not_replay_match_alert(self):
  self.check()
  prop=m.Signal('PROPS',45,['ACES'],'A vs B','A over7.5',8,key=('2026-10-29','a','b','a','ACES','7.5','over'))
  self.assertEqual(self.check(signals=[self.signal,prop]),(0,1))
  self.assertEqual(self.check(signals=[self.signal,prop]),(0,0))
 def test_uncertain_acknowledgement_never_auto_resends(self):
  with self.assertRaises(RuntimeError): self.check(dispatch=RuntimeError('lost acknowledgement'))
  with self.assertRaisesRegex(RuntimeError,'unresolved'): self.check()
  self.assertEqual(json.loads(self.state.read_text())['pending_signal_ids'],[m.signal_id(self.signal)])
 def test_gh_timeout_has_no_second_transport_attempt(self):
  with patch.object(m.subprocess,'run',side_effect=m.subprocess.TimeoutExpired('gh',20)),patch.object(m,'github_token') as token,self.assertRaises(RuntimeError):
   m.dispatch(['test'],repository='repo',workflow='workflow',ref='ref')
  token.assert_not_called()

if __name__=='__main__':unittest.main()
