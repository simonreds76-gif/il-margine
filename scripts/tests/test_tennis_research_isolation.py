import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, patch
import argparse
import runpy
import os
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tennis_runtime_health as runtime
import sisal_input_revision as revision
from ops_morning_failures import check_morning_failure, failure_message
from ops_tennis_recovery import props_failure


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_failed_experiment_keeps_prices_usable_and_warning_visible(self):
        token = runtime.begin(self.root, 'Freeze completed tournament evidence before Sisal quotes (paper only)', 'tennis_sisal_5050.py', 120)
        runtime.finish(self.root, token, 1)
        token = runtime.begin(self.root, 'Price capture', 'collector.py', 180)
        runtime.finish(self.root, token, 0)
        health = runtime.summary(self.root)
        self.assertEqual(health['issues'], [])
        self.assertEqual(len(health['research_issues']), 1)
        self.assertEqual(health['state'], 'DEGRADED')
        feed = runtime.overlay_feed_health({'state': 'SHADOW_EVIDENCE_READY', 'structural_error': False}, health)
        self.assertFalse(feed['structural_error'])
        self.assertEqual(feed['state'], 'SHADOW_EVIDENCE_READY')
        self.assertEqual(len(feed['research_issues']), 1)

    def test_real_capture_failure_still_blocks(self):
        token = runtime.begin(self.root, 'Price capture', 'collector.py', 180)
        runtime.finish(self.root, token, 1)
        self.assertEqual(len(runtime.summary(self.root)['issues']), 1)

    def test_wrong_label_or_script_cannot_hide_failure(self):
        for script, label in [('collector.py', 'Freeze completed tournament evidence before Sisal quotes (paper only)'), ('tennis_sisal_5050.py', 'Capture Sisal quotes')]:
            token = runtime.begin(self.root, label, script, 120)
            runtime.finish(self.root, token, 1)
        self.assertEqual(len(runtime.summary(self.root)['issues']), 2)

    def test_same_experiment_success_clears_research_warning(self):
        args = (self.root, 'Freeze completed tournament evidence before Sisal quotes (paper only)', 'tennis_sisal_5050.py', 120)
        runtime.finish(self.root, runtime.begin(*args), 1)
        runtime.finish(self.root, runtime.begin(*args), 0)
        self.assertEqual(runtime.summary(self.root)['research_issues'], [])

    def test_retired_browser_failure_remains_visible_without_blocking_api_feed(self):
        token = runtime.begin(self.root, 'Capture direct Bet365 service-break totals', 'tennis-props-scrape-bet365-direct.py', 120)
        runtime.finish(self.root, token, 2)
        health = runtime.summary(self.root)
        self.assertEqual(health['issues'], [])
        self.assertEqual(len(health['source_issues']), 1)
        self.assertEqual(health['state'], 'DEGRADED')

    def test_automatic_capture_does_not_launch_legacy_browser(self):
        module = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'run-tennis-props-daily.py'))
        fn = module['capture_market_prices']; globals_ = fn.__globals__
        args = argparse.Namespace(skip_odds=False, skip_bet365_direct=False, skip_betsbk=False,
                                  require_odds=False, as_of='2026-11-05', days_ahead=3, max_events=20)
        called = []
        with patch.dict(globals_, {'run': lambda cmd, label, **kw: called.append(cmd) or 0,
                                   'has_odds_key': lambda: True, 'PROPS_DIR': self.root}):
            self.assertEqual(fn(args), 0)
        self.assertTrue(any('tennis-props-scrape-bet365.py' in str(cmd) for cmd in called))
        self.assertFalse(any('tennis-props-scrape-bet365-direct.py' in str(cmd) for cmd in called))

    def derived_refresh(self, failing):
        module = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'run-tennis-props-daily.py'))
        fn = module['refresh_current_most_aces']; globals_ = fn.__globals__
        outputs = {'tennis-props-v3-live.py':'aces-v3-projection-board.csv',
                   'build-tennis-most-aces-board.py':'most-aces-1x2-board.csv',
                   'tennis-most-aces-direct-live.py':'most-aces-direct-1x2-board.csv'}
        shadow = self.root/'shadow'; shadow.mkdir()
        calls = []
        def fake_run(cmd, label, **kw):
            script = Path(cmd[1]).name; calls.append(script)
            if script in outputs:
                target = shadow/outputs[script]; target.write_text('current')
                os.utime(target, (time.time()+1, time.time()+1))
            return int(script == failing)
        with patch.dict(globals_, {'run':fake_run,'ROOT':self.root,'PROPS_DIR':self.root,
                                   'most_aces_suspended':lambda:False,'verify_derived_board':Mock()}), \
                patch('tennis_pairing_consistency.clear_empty_derived_scope',return_value=False):
            result = fn('2026-11-05')
        return result, calls

    def test_direct_failure_does_not_invalidate_count_and_clears_stale_direct(self):
        result, calls = self.derived_refresh('tennis-most-aces-direct-live.py')
        self.assertTrue(result)
        self.assertIn('tennis_most_aces_current.py', calls)
        self.assertEqual((self.root/'shadow/most-aces-direct-1x2-board.csv').read_text(), '')

    def test_count_failure_still_blocks_and_never_registers_stale_prices(self):
        result, calls = self.derived_refresh('build-tennis-most-aces-board.py')
        self.assertFalse(result)
        self.assertNotIn('tennis_most_aces_current.py', calls)


class AlertTests(unittest.TestCase):
    def row(self):
        return dict(run_id='exact-evening-run', status='failed', trigger_kind='manual', started_at='2026-11-04T22:11:04Z', error_type='TennisPropsCaptureFailed', details={})

    def test_evening_manual_failure_has_stage_and_no_morning_label(self):
        text = failure_message(self.row())
        self.assertIn('On-demand tennis refresh incomplete', text)
        self.assertIn('Match pricing completed', text)
        self.assertIn('bookmaker price capture failed', text)
        self.assertNotIn('Morning', text)

    def test_unknown_error_does_not_claim_pricing_succeeded(self):
        text = failure_message({**self.row(), 'error_type': 'RuntimeException'})
        self.assertNotIn('Match pricing completed', text)

    def test_already_notified_incident_never_sends_again(self):
        row = self.row(); row['details'] = {'ops_failure_notified_at': 'saved'}
        transport = Mock(return_value=[row])
        self.assertTrue(check_morning_failure({'NEXT_PUBLIC_SUPABASE_URL': 'https://db.example', 'SUPABASE_SERVICE_ROLE_KEY': 'fake'}, transport))
        self.assertEqual(transport.call_count, 2)  # Also checks for verified recovery.
        self.assertTrue(all(call.args[0] == 'GET' for call in transport.call_args_list))

    def test_legacy_error_requires_exact_diagnosis_before_recovery_check(self):
        row = {**self.row(), 'error_type': 'RuntimeException'}
        self.assertFalse(props_failure(row))
        diagnosis = dict(run_id=row['run_id'], scope='sisal-evidence-capture-gate-only',
                         reason='event_comparison_frozen_policy_or_artifact_changed',
                         run_log_sha256='a'*64, manual_status_sha256='b'*64)
        row['details'] = {'ops_failure_diagnosis': diagnosis}
        self.assertTrue(props_failure(row))
        for field in diagnosis:
            wrong = dict(diagnosis); wrong[field] = 'wrong'
            self.assertFalse(props_failure({**row, 'details': {'ops_failure_diagnosis':wrong}}))


class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.now = datetime.now(timezone.utc)
        self.before = {'scripts/build-tennis-props-board.py': 'old'}
        self.after = {'scripts/build-tennis-props-board.py': 'new'}
        self.proof = {'model_formula_changed': False, 'project_side_ast_identical': True, 'paired_rows': 40, 'paired_prices_identical': True, 'new_board_sha256': 'new'}
        proof = self.folder / 'input-isolation-proof-20261105.json'
        proof.write_text(json.dumps(self.proof))
        prior = {}
        for name in ['source-filter-revision.json','observation-amendment-20261030.json','observation-proof-20261030.json']:
            (self.folder / name).write_text('{}'); prior[name] = hashlib.sha256(b'{}').hexdigest()
        self.data = dict(scope='verified-input-isolation-20261105', pricing_changed=False, effective_at='2026-11-05T00:00:00+00:00', registration_sha256='registration', before=self.before, after=self.after,
                         guard_sha256=hashlib.sha256(Path(revision.__file__).read_bytes()).hexdigest(), prior_evidence=prior, proof_sha256=hashlib.sha256(proof.read_bytes()).hexdigest())
        self.save()

    def save(self):
        (self.folder / revision.NAME).write_text(json.dumps(self.data))

    def check(self, **kw):
        args = dict(root=self.folder, folder=self.folder, registration_hash='registration', before=self.before, after=self.after, now=self.now); args.update(kw)
        return revision.accepted_input_revision(**args)

    def test_exact_verified_revision_accepted(self): self.assertIsNotNone(self.check())
    def test_later_unreviewed_code_change_rejected(self): self.assertIsNone(self.check(after={'scripts/build-tennis-props-board.py':'drift'}))
    def test_registration_change_rejected(self): self.assertIsNone(self.check(registration_hash='other'))
    def test_mutated_parity_proof_rejected(self):
        (self.folder/'input-isolation-proof-20261105.json').write_text('{}'); self.assertIsNone(self.check())
    def test_guard_change_rejected(self):
        self.data['guard_sha256']='other'; self.save(); self.assertIsNone(self.check())
    def test_prior_audit_must_be_retained(self):
        (self.folder/'source-filter-revision.json').write_text('changed'); self.assertIsNone(self.check())
    def test_future_revision_rejected(self):
        self.data['effective_at']='2099-01-01T00:00:00+00:00'; self.save(); self.assertIsNone(self.check())


if __name__ == '__main__':
    unittest.main()
