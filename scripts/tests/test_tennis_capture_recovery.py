import importlib.util
import sys
import unittest
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
                       {'match_start_utc': '2026-09-28T14:00:00Z'}, {'capture_ts': ''}, {'over_odds': ''}):
            self.assertEqual(guard.fresh_rows([dict(row, **change)], self.now), [])


if __name__ == '__main__':
    unittest.main()
