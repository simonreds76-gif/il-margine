from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import tennis_props_v4_alerts as A


class V4SelectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.now = datetime(2026, 10, 7, 14, 0, tzinfo=timezone.utc)
        self.today = self.now.astimezone(A.UK).date().isoformat()
        self.write('data/tennis-props/player-history-status.json', dict(state='CURRENT', version=A.VERSION, as_of=self.today))
        self.write('data/tennis-props/pipeline-health.json', dict(as_of=self.today, state='MILESTONE_SHADOW_READY', structural_error=False))
        (self.root/'model.json').write_text('frozen model')
        self.sha = hashlib.sha256((self.root/'model.json').read_bytes()).hexdigest()
        self.write('data/tennis-props/backtest/aces-dfs-v3-all-tour-gate.json', dict(deployment_safe_aces={'ATP': {'model_path': 'model.json'}}))
        verifier = patch.object(A, 'verify_ledger', return_value=(200, 8.0, 6.0))
        self.verifier = verifier.start()
        self.addCleanup(verifier.stop)
        self.sender = Mock()

    def write(self, relative, payload):
        path = self.root/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding='utf-8')

    def row(self, key='first', **extras):
        row = dict(observation_id=key, event_id=key, date=self.today, tour='ATP', tournament='Shanghai',
                   player='Player One', opponent='Player Two', market='aces', bookmaker='Bet365',
                   history_version=A.VERSION, history_fingerprint='verified', history_as_of=self.today,
                   model_sha256=self.sha, phase='WALK_FORWARD', settlement_status='pending', v4_signal='true',
                   match_start_utc=(self.now+timedelta(hours=2)).isoformat(),
                   capture_ts=(self.now-timedelta(minutes=30)).isoformat(),
                   registered_at_utc=(self.now-timedelta(minutes=20)).isoformat(),
                   fit_training_n='200', fit_cutoff='2026-10-01', line='4.5', selected_odds='2.0',
                   p_over_v4='0.6', p_push_v4='0', edge_v4_pct='20', pnl='', result='')
        row.update(extras)
        return row

    def rows(self, rows):
        path = self.root/A.LEDGER
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(dict.fromkeys(key for row in rows for key in row)))
            writer.writeheader()
            writer.writerows(rows)
        self.write(A.REPORT, dict(generated_at=self.now.isoformat(), rows_registered=len(rows),
                                 rows_settled=sum(r.get('settlement_status') == 'settled' for r in rows)))

    def run_alerts(self, **kwargs):
        return A.selection_alerts(self.root, self.today, self.sender, now=self.now, **kwargs)

    def test_milestone_price_time_probability_and_record(self):
        self.rows([self.row()])
        messages, status = A.prepare(self.root, self.now, {})
        self.assertEqual(status['new'], 1)
        text = messages[0][1]
        for expected in ['5+ aces @ 2 (Bet365)', '60.0%', 'fair odds 1.67', 'EV +20.0%',
                         '13:30 UTC', '17:00 BST', 'no settled paper selections', 'no real stake']:
            self.assertIn(expected, text)
        self.assertLess(len(text), 3800)

    def test_missing_stale_or_unqualified_data_never_alerts(self):
        cases = [
            dict(history_version='old'), dict(model_sha256='old'), dict(history_as_of='2026-10-06'),
            dict(phase='PRE_FIT'), dict(fit_training_n='199'), dict(fit_cutoff='2026-10-08'),
            dict(v4_signal='false'), dict(settlement_status='settled'), dict(market='dfs'),
            dict(tour='WTA'), dict(event_id=''), dict(history_fingerprint=''), dict(match_start_utc=''),
            dict(match_start_utc=self.now.isoformat()), dict(match_start_utc='2026-10-11T14:00:00Z'),
            dict(capture_ts='2026-10-07T07:59:00Z'), dict(capture_ts='2026-10-07T15:00:00Z'),
            dict(registered_at_utc='2026-10-07T15:00:00Z'), dict(capture_ts='2026-10-07T13:59:00'),
            dict(line='nan'), dict(line='-1'), dict(line='4.7'), dict(selected_odds='1'),
            dict(p_over_v4='1.2'), dict(p_push_v4='.5'), dict(edge_v4_pct='7'), dict(edge_v4_pct='99'),
        ]
        for change in cases:
            with self.subTest(change=change):
                self.assertIsNotNone(A.selection_problem(self.row(**change), self.now, self.sha, 200, 8, 6))

    def test_tomorrow_match_is_included_with_fresh_price(self):
        self.rows([self.row(match_start_utc='2026-10-08T07:00:00Z', date='2026-10-08')])
        messages, _ = A.prepare(self.root, self.now, {})
        self.assertEqual(len(messages), 1)

    def test_integer_line_accounts_for_push_in_fair_odds(self):
        self.rows([self.row(line='5', p_push_v4='.1', edge_v4_pct='30')])
        messages, _ = A.prepare(self.root, self.now, {})
        self.assertIn('exactly 5 returns the stake', messages[0][1])
        self.assertIn('fair odds 1.50', messages[0][1])

    def test_record_excludes_legacy_and_other_models(self):
        self.rows([self.row(), self.row('win', settlement_status='settled', result='win', pnl='1.5'),
                   self.row('loss', settlement_status='settled', result='loss', pnl='-1'),
                   self.row('old', history_version='old', settlement_status='settled', result='win', pnl='100'),
                   self.row('othermodel', model_sha256='other', settlement_status='settled', result='win', pnl='100')])
        messages, _ = A.prepare(self.root, self.now, {})
        self.assertIn('1W / 1L', messages[0][1])
        self.assertIn('P/L +0.50u | ROI +25.00%', messages[0][1])

    def test_dedup_persists_and_all_selections_use_one_relay_batch(self):
        self.rows([self.row(), self.row('second')])
        self.assertEqual(self.run_alerts(), 'dispatched')
        self.assertEqual(len(self.sender.call_args.args[0]), 2)
        self.assertEqual(self.run_alerts(), 'no_new_selections')
        self.sender.assert_called_once()
        saved = A.read_json(self.root/A.STATE)
        self.assertEqual(set(saved['sent']), {'first', 'second'})
        self.assertNotIn('date', saved)  # IDs do not reset on the next daily run.

    def test_dispatch_failure_is_retryable_preview_does_not_send(self):
        self.rows([self.row()])
        self.sender.side_effect = RuntimeError('relay failed')
        with self.assertRaises(RuntimeError):
            self.run_alerts()
        self.assertFalse((self.root/A.STATE).exists())
        self.assertEqual(self.run_alerts(print_only=True), 'preview')
        self.assertEqual(self.sender.call_count, 1)
        self.sender.side_effect = None
        self.assertEqual(self.run_alerts(), 'dispatched')

    def test_only_new_selections_dispatched_on_admin_rerun(self):
        self.rows([self.row()])
        self.run_alerts()
        self.rows([self.row(), self.row('new')])
        self.run_alerts()
        self.assertEqual(len(self.sender.call_args.args[0]), 1)
        self.assertEqual(self.sender.call_count, 2)

    def test_bad_integrity_blocks_and_saves_reason(self):
        self.rows([self.row()])
        self.verifier.side_effect = RuntimeError('Frozen hash mismatch')
        with self.assertRaises(RuntimeError):
            self.run_alerts()
        self.sender.assert_not_called()
        self.assertEqual(A.read_json(self.root/A.STATUS)['state'], 'BLOCKED_DATA_CHECK')

    def test_stale_report_and_stale_history_fail_closed(self):
        for relative, payload in [
            (A.REPORT, dict(generated_at='2026-10-07T06:00:00Z', rows_registered=1, rows_settled=0)),
            ('data/tennis-props/player-history-status.json', dict(state='CURRENT', version=A.VERSION, as_of='2026-10-06')),
        ]:
            self.rows([self.row()])
            self.write(relative, payload)
            with self.assertRaises(RuntimeError):
                self.run_alerts()
        self.sender.assert_not_called()

    def test_prefit_only_does_not_send_a_fake_tip(self):
        self.rows([self.row(phase='PRE_FIT', v4_signal='false')])
        self.assertEqual(self.run_alerts(), 'no_new_selections')
        self.sender.assert_not_called()
        self.assertIn('INITIAL_CALIBRATION_NOT_READY', A.read_json(self.root/A.STATUS)['excluded'])

    def test_historical_replay_cannot_send(self):
        with self.assertRaises(ValueError):
            A.selection_alerts(self.root, '2026-10-06', self.sender, now=self.now)
        self.sender.assert_not_called()

    def test_hook_does_not_require_ml_ready_and_only_mode_does_not_replay(self):
        spec = importlib.util.spec_from_file_location('v4_digest_hook', SCRIPTS/'tennis-daily-signal-digest.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        with patch.object(sys, 'argv', ['digest', '--paper-signals-only', '--require-ready']), \
             patch.object(A, 'selection_alerts', return_value='no_new_selections') as alerts, \
             patch.object(module, 'signal_generation_is_ready', side_effect=AssertionError('Must not depend on ML')):
            self.assertEqual(module.main(), 0)
            alerts.assert_called_once()

    def test_hook_failure_does_not_block_other_models(self):
        spec = importlib.util.spec_from_file_location('v4_digest_failure', SCRIPTS/'tennis-daily-signal-digest.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        with patch.object(sys, 'argv', ['digest', '--paper-signals', '--require-ready']), \
             patch.object(A, 'selection_alerts', side_effect=RuntimeError('blocked')), \
             patch.object(module, 'signal_generation_is_ready', return_value=False):
            self.assertEqual(module.main(), 0)


if __name__ == '__main__':
    unittest.main()
