import importlib.util,sys,unittest
from pathlib import Path
from unittest.mock import patch
S=Path(__file__).resolve().parents[1];sys.path.insert(0,str(S))
def load(name,file):
 spec=importlib.util.spec_from_file_location(name,S/file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class FastCommandTests(unittest.TestCase):
 def test_same_pricing_arguments_only_research_work_is_deferred(self):
  m=load('daily_fast_test','run-daily-odds.py')
  def calls(fast):
   with patch.object(sys,'argv',['daily','--skip-strict-report']+(['--on-demand'] if fast else [])),patch.object(m,'run_cmd',return_value=0) as run:
    self.assertEqual(m.main(),0)
   return [(c.args,c.kwargs) for c in run.call_args_list]
  normal=calls(False);fast=calls(True)
  deferred={'refresh-tennis-context-research.py','refresh-tennis-matchup-history.py','tennis-model-market-gap-audit.py'}
  expected=[c for c in normal if Path(c[0][0][1]).name not in deferred]
  self.assertEqual(fast,expected)
  names={Path(c[0][0][1]).name for c in fast}
  self.assertIn('tennis_pricing_context.py',names);self.assertIn('oncourt-compute-recent-activity.py',names)
 def test_props_keeps_comparison_registration_and_strict_health(self):
  m=load('props_fast_test','run-tennis-props-daily.py')
  with patch.object(m,'mark_pipeline_blocked'),patch.object(m,'select_market_file',return_value=Path('current.csv')),patch.object(m,'run_comparison',return_value=True) as compare,patch.object(m,'run',return_value=0) as run,patch.object(m,'write_pipeline_health',return_value=0) as health:
   self.assertEqual(m.run_monitor_only('2026-10-28',selections_only=True),0)
  compare.assert_called_once();health.assert_called_once_with('2026-10-28',Path('current.csv'),strict=True)
  self.assertEqual(len(run.call_args_list),1);self.assertIn('tennis-props-shadow-tracker.py',run.call_args.args[0][1])
 def test_failed_comparison_never_registers_selections(self):
  m=load('props_fail_test','run-tennis-props-daily.py')
  with patch.object(m,'mark_pipeline_blocked'),patch.object(m,'select_market_file',return_value=Path('current.csv')),patch.object(m,'run_comparison',return_value=False),patch.object(m,'run') as run:
   self.assertEqual(m.run_monitor_only('2026-10-28',selections_only=True),1)
  run.assert_not_called()
if __name__=='__main__':unittest.main()
