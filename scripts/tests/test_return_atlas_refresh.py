import importlib.util
from pathlib import Path
import unittest
from copy import deepcopy

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


if __name__ == '__main__': unittest.main()
