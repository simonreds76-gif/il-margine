import importlib.util
from pathlib import Path
import unittest
from copy import deepcopy
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('refresh', Path(__file__).parents[1] / 'refresh-return-atlas.py')
refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh)


class PublicationGateTests(unittest.TestCase):
    def setUp(self):
        self.old = {'players': [{'id': 'a'}, {'id': 'b'}], 'matches': [['m1', '2026-09-13', 0, 1, 1.7, 2.4, 0, 0, 0]]}

    def test_unchanged_history_does_not_deploy(self):
        self.assertFalse(refresh.validate_transition(self.old, deepcopy(self.old), '2026-09-19'))

    def test_new_completed_match_can_publish(self):
        new = deepcopy(self.old)
        new['matches'].append(['m2', '2026-09-19', 1, 0, 2.1, 1.8, 1, 1, 0])
        self.assertTrue(refresh.validate_transition(self.old, new, '2026-09-19'))

    def test_price_edit_and_missing_history_are_blocked(self):
        for operation in ['price', 'missing', 'winner']:
            with self.subTest(operation=operation):
                new = deepcopy(self.old)
                if operation == 'missing': new['matches'] = []
                elif operation == 'price': new['matches'][0][4] = 1.9
                else: new['matches'][0][6] = 1
                with self.assertRaises(ValueError):
                    refresh.validate_transition(self.old, new, '2026-09-19')

    def test_player_order_can_change_without_changing_records(self):
        new = deepcopy(self.old)
        new['players'].reverse()
        new['matches'][0][2:4] = [1, 0]
        self.assertFalse(refresh.validate_transition(self.old, new, '2026-09-19'))

    def test_future_and_invalid_odds_block_publication(self):
        for value in [['m2', '2026-09-20', 0, 1, 1.7, 2.4, 0, 0, 0], ['m2', '2026-09-19', 0, 1, 1, 2.4, 0, 0, 0]]:
            new = deepcopy(self.old)
            new['matches'].append(value)
            with self.assertRaises(ValueError):
                refresh.validate_transition(self.old, new, '2026-09-19')

    def test_html_response_is_not_accepted_as_csv(self):
        with self.assertRaises(ValueError): refresh.source_csv(b'<html>Unavailable</html>', 2026)

    def test_retention_keeps_candidate_previous_and_live(self):
        versions = [f'202609{day:02d}-aaaaaaaaaaaa' for day in range(13, 20)]
        obsolete = refresh.obsolete_versions(versions, versions[-1], versions[-2], versions[0])
        self.assertEqual(obsolete, versions[1:-2])
        self.assertNotIn('other-folder', refresh.obsolete_versions(['other-folder'], *versions[:3]))


class PublicPropagationTests(unittest.TestCase):
    expected = {'return-atlas': '20261025-0f30bd9964e7',
                'tennis-matchup': '20261026-eb98a6b72549'}

    def test_current_versions_pass_without_sleep(self):
        sleep = Mock()
        result = refresh.wait_for_live_versions(self.expected,
                    read_version=self.expected.__getitem__, sleep=sleep)
        self.assertEqual(result['attempts'], 1)
        self.assertEqual(result['observed'], self.expected)
        sleep.assert_not_called()

    def test_stale_page_is_retried_and_both_routes_are_checked_again(self):
        reader = Mock(side_effect=['older-atlas', self.expected['tennis-matchup'],
                                  *self.expected.values()])
        sleep = Mock()
        result = refresh.wait_for_live_versions(self.expected, read_version=reader, sleep=sleep)
        self.assertEqual(result['attempts'], 2)
        self.assertEqual([c.args[0] for c in reader.call_args_list], list(self.expected) * 2)
        sleep.assert_called_once_with(10)

    def test_routes_must_match_on_the_same_attempt(self):
        reader = Mock(side_effect=[self.expected['return-atlas'], 'old-matchup',
                                  'old-atlas', self.expected['tennis-matchup']])
        with self.assertRaisesRegex(RuntimeError, 'after 2 attempts'):
            refresh.wait_for_live_versions(self.expected, attempts=2,
                                          read_version=reader, sleep=Mock())

    def test_transient_timeout_recovers(self):
        reader = Mock(side_effect=[TimeoutError('private URL'), self.expected['tennis-matchup'],
                                  *self.expected.values()])
        result = refresh.wait_for_live_versions(self.expected, read_version=reader, sleep=Mock())
        self.assertEqual(result['attempts'], 2)

    def test_permanent_mismatch_still_fails_with_bounded_retries(self):
        reader, sleep = Mock(return_value='old'), Mock()
        with self.assertRaisesRegex(RuntimeError, 'expected.*observed'):
            refresh.wait_for_live_versions(self.expected, attempts=3,
                                          read_version=reader, sleep=sleep)
        self.assertEqual(reader.call_count, 6)
        self.assertEqual(sleep.call_count, 2)

    def test_missing_page_versions_do_not_become_success(self):
        reader = Mock(side_effect=RuntimeError('private URL'))
        with self.assertRaises(RuntimeError) as error:
            refresh.wait_for_live_versions(self.expected, attempts=1,
                                          read_version=reader, sleep=Mock())
        self.assertNotIn('private URL', str(error.exception))
        self.assertIn('unavailable:RuntimeError', str(error.exception))

    def test_default_probe_timeout_is_bounded(self):
        with patch.object(refresh, 'live_version', side_effect=self.expected.values()) as reader:
            refresh.wait_for_live_versions(self.expected, sleep=Mock())
        self.assertTrue(all(c.kwargs == {'timeout': 10} for c in reader.call_args_list))


if __name__ == '__main__': unittest.main()

