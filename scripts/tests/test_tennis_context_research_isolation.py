import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import tennis_runtime_health as runtime
from tennis_step_scope import research_only

SPEC = importlib.util.spec_from_file_location('context_isolation_daily', SCRIPTS / 'run-daily-odds.py')
daily = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(daily)

HISTORY = {
    'refresh-tennis-context-research.py': '0/6 Player context history (research only; live inputs unchanged)',
    'refresh-tennis-matchup-history.py': '0/6 Big-server and matchup histories (research only)',
}


class ContextIsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def run_main(self, args=(), fail=None):
        calls = []
        def observed(cmd, **kw):
            script = Path(cmd[1]).name
            calls.append((script, kw['label'], kw['timeout']))
            token = runtime.begin(self.root, kw['label'], script, kw['timeout'])
            code = 124 if script == fail else 0
            runtime.finish(self.root, token, code)
            if code:
                raise subprocess.TimeoutExpired(cmd, kw['timeout'])
            return subprocess.CompletedProcess(cmd, 0)
        with patch.object(daily, 'ROOT', self.root), patch.object(daily, 'observed_run', side_effect=observed), \
                patch.object(sys, 'argv', ['run-daily-odds.py', *args]), \
                patch.dict(os.environ, {'STRICT_CPI_SPEED_SHADOW_ENABLED': '0'}), contextlib.redirect_stdout(io.StringIO()):
            code = daily.main()
        return code, calls

    def test_historical_timeout_does_not_skip_current_prices_or_signals(self):
        code, calls = self.run_main(fail='refresh-tennis-context-research.py')
        names = [row[0] for row in calls]
        self.assertEqual(code, 0)
        for required in ('pinnacle-scrape-odds.py', 'oncourt-compute-fair-odds.py', 'compute-handicap-values.py', 'strict-policy-report.py'):
            self.assertLess(names.index(required), names.index('refresh-tennis-context-research.py'))
        self.assertIn('refresh-tennis-matchup-history.py', names)
        health = runtime.summary(self.root)
        self.assertEqual(health['issues'], [])
        self.assertEqual(health['research_issues'][0]['issue'], 'TIMED_OUT')
        self.assertEqual(health['state'], 'DEGRADED')

    def test_scheduled_pricing_defers_both_histories(self):
        _, calls = self.run_main(['--defer-context-research', '--skip-strict-report'])
        self.assertFalse(set(HISTORY) & {c[0] for c in calls})
        self.assertIn('oncourt-compute-fair-odds.py', [c[0] for c in calls])

    def test_on_demand_does_not_refresh_histories(self):
        _, calls = self.run_main(['--on-demand'])
        self.assertFalse(set(HISTORY) & {c[0] for c in calls})

    def test_required_live_context_timeout_still_stops_prices(self):
        # Runtime may use its verified serial adapter; neither is research-only.
        name = 'refresh-tennis-context-serial.py' if 'refresh-tennis-context-serial.py' in (SCRIPTS/'run-daily-odds.py').read_text() else 'tennis_pricing_context.py'
        with self.assertRaises(SystemExit) as error:
            self.run_main(fail=name)
        self.assertEqual(error.exception.code, 124)
        self.assertEqual(len(runtime.summary(self.root)['issues']), 1)

    def test_handicap_failure_still_fails_final_health(self):
        self.run_main(['--defer-context-research'], fail='compute-handicap-values.py')
        self.assertTrue(runtime.summary(self.root)['issues'])

    def test_exact_scope_only_and_success_recovery(self):
        for script, label in HISTORY.items():
            self.assertTrue(research_only({'script':script, 'label':label}))
            self.assertFalse(research_only({'script':'live.py', 'label':label}))
            self.assertFalse(research_only({'script':script, 'label':'Current price capture'}))
            token = runtime.begin(self.root, label, script, 420)
            runtime.finish(self.root, token, 124)
        self.assertEqual(len(runtime.summary(self.root)['research_issues']), 2)
        for script, label in HISTORY.items():
            runtime.finish(self.root, runtime.begin(self.root, label, script, 420), 0)
        self.assertEqual(runtime.summary(self.root)['research_issues'], [])

    def test_scheduled_order_and_timeout_parity(self):
        ps = (SCRIPTS / 'oncourt-am-refresh.ps1').read_text()
        self.assertIn('"--skip-strict-report", "--defer-context-research"', ps)
        self.assertLess(ps.index('Log "On-demand refresh complete;'), ps.index('$contextResearchSteps ='))
        self.assertLess(ps.index('-Label "tennis props hosted-price comparison"') if '-Label "tennis props hosted-price comparison"' in ps else ps.index('$propsCompareArguments ='), ps.index('$contextResearchSteps ='))
        _, calls = self.run_main(['--skip-strict-report'])
        self.assertEqual([c[2] for c in calls if c[0] in HISTORY], [420, 420])
        self.assertIn('-Label $researchStep.Label -TimeoutSeconds 420', ps)

    @unittest.skipUnless(os.name == 'nt', 'PowerShell Windows scheduler contract')
    def test_scheduled_timeout_yields_lock_and_continues_other_history(self):
        ps = (SCRIPTS / 'oncourt-am-refresh.ps1').read_text()
        block = ps[ps.index('    $contextResearchSteps ='):ps.index('    # Isolated published Elo snapshots;')]
        harness = '''$ErrorActionPreference='Stop'; $root='D:/test'; $script:events=@();
function Enter-TennisPriorityLock { param($RootPath); $script:events+='lock'; return 'handle' }
function Exit-TaskLock { param($Handle); if($Handle){$script:events+='unlock'} }
function Log { param($Message); $script:events+='warning' }
function Invoke-LoggedProcess { param($FilePath,$ArgumentList,$Label,$TimeoutSeconds); $script:events+=$Label; if($Label -like '*Player context*'){return 124}; return 0 }
'''
        for injected in (harness, harness.replace('return 124', 'throw "injected process error"')):
            result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', injected + block + '; ConvertTo-Json -Compress -InputObject $script:events'], capture_output=True, text=True, check=True, timeout=20)
            events = json.loads(result.stdout)
            self.assertEqual(events, ['lock', HISTORY['refresh-tennis-context-research.py'], 'warning', 'unlock', 'lock', HISTORY['refresh-tennis-matchup-history.py'], 'unlock'])


if __name__ == '__main__':
    unittest.main()
