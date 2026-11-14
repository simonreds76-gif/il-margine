import importlib.util,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
S=Path(__file__).resolve().parents[1];sys.path.insert(0,str(S))
spec=importlib.util.spec_from_file_location('test_independent_prices_runner',S/'run-tennis-props-daily.py')
runner=importlib.util.module_from_spec(spec);sys.modules[spec.name]=runner;spec.loader.exec_module(runner)
class Sources(unittest.TestCase):
 def args(self):return SimpleNamespace(skip_odds=False,as_of='2026-11-14',days_ahead=2,max_events=6,skip_bet365_direct=True,enable_bet365_browser=False,skip_betsbk=True,require_odds=False)
 def test_no_api_key_still_calls_independent_shared_collector(self):
  with patch.object(runner,'has_odds_key',return_value=False),patch.object(runner,'run',return_value=0) as run:
   self.assertEqual(runner.capture_market_prices(self.args()),0)
   commands=[str(c.args[0]) for c in run.call_args_list]
   self.assertTrue(any('tennis-props-scrape-bet365.py' in x for x in commands))
 def test_explicit_skip_remains_no_network(self):
  args=self.args();args.skip_odds=True
  with patch.object(runner,'run') as run:
   self.assertEqual(runner.capture_market_prices(args),0);run.assert_not_called()
if __name__=='__main__':unittest.main()
