import importlib.util
import sys
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compare = load('tennis-props-compare-bet365')
guard = load('ensure-tennis-props-capture')


class UndatedPairTests(unittest.TestCase):
    def setUp(self):
        self.line = dict(date='2026-09-30', tour='ATP', tournament='Beijing',
                         player='Juan Manuel Cerundolo', opponent='Yunchaokete Bu')
        self.row = dict(self.line, date='2026-09-28', generation_date='2026-09-28',
                        opponent='Bu Yunchaokete', schedule_status='tbd',
                        scheduled_date='', schedule_source='oncourt_draw_undated')

    def test_full_pair_two_days_ahead_matches(self):
        self.assertEqual(compare.undated_pair_candidates(self.line, [self.row]), [self.row])

    def test_confirmed_dates_do_not_get_extended(self):
        for changes in ({'schedule_status': 'confirmed'}, {'scheduled_date': '2026-09-28'}):
            self.assertEqual(compare.undated_pair_candidates(self.line, [dict(self.row, **changes)]), [])

    def test_other_event_and_unknown_source_rejected(self):
        for changes in ({'tournament': 'Tokyo'}, {'tour': 'WTA'}, {'opponent': 'Yu Wu'},
                        {'schedule_source': 'manual'}, {'generation_date': '2026-09-26'},
                        {'generation_date': '2026-10-01'}):
            self.assertEqual(compare.undated_pair_candidates(self.line, [dict(self.row, **changes)]), [])

    def test_ambiguous_pair_is_not_unique(self):
        candidates = compare.undated_pair_candidates(self.line, [self.row, dict(self.row)])
        self.assertIsNone(compare.unique_row(candidates))

    def test_surname_or_placeholder_not_enough(self):
        for opponent in ('Bu', '', 'Total'):
            self.assertEqual(compare.undated_pair_candidates(dict(self.line, opponent=opponent), [self.row]), [])


class RecoveryTests(unittest.TestCase):
    now = datetime(2026, 9, 28, 15, 0, tzinfo=timezone.utc)

    def test_dispatch_only_when_no_recent_or_active_attempt(self):
        self.assertEqual(guard.recovery_decision(self.now, [], {}), 'dispatch')
        self.assertEqual(guard.recovery_decision(self.now, [{'status': 'queued'}], {}), 'wait')
        self.assertEqual(guard.recovery_decision(self.now, [], {'attempt_day': '2026-09-28'}), 'already_attempted')
        self.assertEqual(guard.recovery_decision(self.now, [{'status': 'completed',
                         'createdAt': '2026-09-28T14:55:00Z'}], {}), 'recent_attempt')

    def test_only_fresh_upcoming_prices_count(self):
        row = dict(capture_ts='2026-09-28T14:00:00Z', match_start_utc='2026-09-30T02:00:00Z',
                   over_odds='1.9', player='One Player', opponent='Two Player')
        self.assertEqual(len(guard.fresh_rows([row], self.now)), 1)
        for change in ({'capture_ts': '2026-09-28T07:00:00Z'}, {'capture_ts': '2026-09-28T16:00:00Z'},
                       {'match_start_utc': '2026-09-28T14:00:00Z'}, {'capture_ts': ''}, {'over_odds': ''},
                       {'over_odds': 'nan'}, {'over_odds': 'bad'}, {'over_odds': '1'}):
            self.assertEqual(guard.fresh_rows([dict(row, **change)], self.now), [])

    def test_current_refresh_rejects_earlier_same_day_quotes(self):
        row = dict(capture_ts='2026-09-28T14:00:00Z', match_start_utc='2026-09-30T02:00:00Z',
                   over_odds='1.9', player='One Player', opponent='Two Player', bookmaker='Grosvenor')
        start = guard.timestamp('2026-09-28T14:30:00Z')
        self.assertEqual(guard.fresh_rows([row], self.now, start), [])
        self.assertEqual(len(guard.fresh_rows([dict(row, capture_ts='2026-09-28T14:45:00Z')],
                                             self.now, start)), 1)

    def test_local_recovery_cannot_be_blocked_or_overwritten_by_cloud(self):
        # Reproduces Nov 6: cloud already attempted, but the subsequent local
        # capture is fresh. No cloud operation may run on this success path.
        with patch.object(guard, 'local_fresh', return_value=3) as fresh, \
             patch.object(guard, 'sync', side_effect=RuntimeError('cloud unavailable')) as sync, \
             patch.object(guard, 'runs', side_effect=AssertionError('must not query')):
            self.assertEqual(guard.main(['--not-before', '2026-09-28T14:30:00Z']), 0)
            self.assertEqual(fresh.call_args.args[1], guard.timestamp('2026-09-28T14:30:00Z'))
            sync.assert_not_called()

    def test_absent_fresh_prices_are_still_a_failure_during_cooldown(self):
        with TemporaryDirectory() as directory, \
             patch.object(guard, 'STATE', Path(directory) / 'state.json'), \
             patch.object(guard, 'local_fresh', return_value=0), \
             patch.object(guard, 'sync'), patch.object(guard, 'runs', return_value=[]), \
             patch.object(guard, 'recovery_decision', return_value='already_attempted'):
            self.assertEqual(guard.main([]), 2)

    def test_check_only_does_not_dispatch_when_empty(self):
        with patch.object(guard, 'local_fresh', return_value=0), \
             patch.object(guard, 'sync', side_effect=AssertionError('read only')):
            self.assertEqual(guard.main(['--check-only']), 2)

    def test_invalid_start_cannot_silently_use_old_prices(self):
        with self.assertRaises(ValueError):
            guard.main(['--not-before', '2026-09-28'])

    def test_midnight_refresh_reads_previous_days_prices(self):
        import csv
        now = datetime(2026, 9, 29, 0, 2, tzinfo=timezone.utc)
        row = dict(capture_ts='2026-09-28T23:59:00Z', match_start_utc='2026-09-29T06:00:00Z',
                   over_odds='1.9', player='One Player', opponent='Two Player')
        with TemporaryDirectory() as directory, patch.object(guard, 'ROOT', Path(directory)):
            path = Path(directory) / 'data/tennis-props/inbox/bet365-lines-2026-09-28.csv'
            path.parent.mkdir(parents=True)
            with path.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=list(row))
                writer.writeheader()
                writer.writerow(row)
            self.assertEqual(guard.local_fresh(now, guard.timestamp('2026-09-28T23:58:00Z')), 1)

    def test_orchestrator_checks_recovery_after_capture_before_comparison(self):
        text = (SCRIPTS / 'oncourt-am-refresh.ps1').read_text(encoding='utf-8-sig')
        capture = text.index('$tennisPropsCaptureExit = Invoke-LoggedProcess')
        recovery = text.index('$hostedCaptureExit = Invoke-LoggedProcess')
        board = text.index('$tennisPropsBoardExit = Invoke-LoggedProcess')
        self.assertLess(capture, recovery)
        self.assertLess(recovery, board)
        self.assertIn('"--not-before", $refreshStartedAt', text[recovery:board])


if __name__ == '__main__':
    unittest.main()
