"""Regression cases for incomplete provider responses and count identity."""
import importlib.util
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import api_football_match_stats as api

spec = importlib.util.spec_from_file_location('gk_contract_settlement', SCRIPTS / 'goalkeeper-saves-settle.py')
settle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(settle)


class TeamIdentityTests(unittest.TestCase):
    def fixture(self):
        return {'fixture': {'id': 99}, 'teams': {
            'home': {'id': 1, 'name': 'Home'}, 'away': {'id': 2, 'name': 'Away'}}}

    def stats(self, team_id, count):
        return {'team': {'id': team_id}, 'statistics': [{'type': 'Total Shots', 'value': count}]}

    def test_missing_home_does_not_copy_away_count(self):
        row = api.parse_fixture_statistics(self.fixture(), [self.stats(2, 17)])
        self.assertIsNone(row['home_shots'])
        self.assertEqual(row['away_shots'], 17)

    def test_unknown_ids_do_not_use_response_order(self):
        self.assertIsNone(api.parse_fixture_statistics(self.fixture(), [self.stats(3, 8), self.stats(4, 11)]))

    def test_duplicate_team_ids_are_ambiguous(self):
        row = api.parse_fixture_statistics(self.fixture(), [self.stats(1, 8), self.stats(1, 9), self.stats(2, 11)])
        self.assertIsNone(row['home_shots'])
        self.assertEqual(row['away_shots'], 11)

    def test_missing_fixture_identity_stays_missing(self):
        fixture = self.fixture()
        del fixture['teams']['home']['id']
        row = api.parse_fixture_statistics(fixture, [self.stats(1, 8), self.stats(2, 11)])
        self.assertIsNone(row['home_shots'])

    def test_reversed_complete_response_maps_correctly(self):
        row = api.parse_fixture_statistics(self.fixture(), [self.stats(2, 17), self.stats(1, 0)])
        self.assertEqual((row['home_shots'], row['away_shots']), (0, 17))

    def test_invalid_counts_remain_unavailable(self):
        for value in ('3.9', '-1', 'NaN', 'inf', '', None, True):
            with self.subTest(value=value):
                self.assertIsNone(api._safe_int(value))
        self.assertEqual(api._safe_int('0'), 0)
        self.assertEqual(api._safe_int('3.0'), 3)


class KeeperEvidenceTests(unittest.TestCase):
    def payload(self):
        return {'props': {'pageProps': {'content': {
            'lineup': {'homeTeam': {'starters': [{'id': 10, 'name': 'David Raya', 'positionId': 11}]}},
            'shotmap': {'shots': [{'id': 1, 'eventType': 'Goal', 'keeperId': 10}]},
        }}}}

    def content(self, payload):
        return payload['props']['pageProps']['content']

    def test_missing_shotmap_is_not_zero_saves(self):
        payload = self.payload()
        del self.content(payload)['shotmap']
        actual, meta = settle.fotmob_player_saves(payload, 'D. Raya')
        self.assertIsNone(actual)
        self.assertEqual(meta['error'], 'fotmob_shotmap_unavailable')

    def test_absent_or_empty_shots_are_not_zero_saves(self):
        for shotmap in (None, {}, {'shots': None}, {'shots': []}, {'shots': 'unavailable'}):
            payload = self.payload()
            self.content(payload)['shotmap'] = shotmap
            self.assertIsNone(settle.fotmob_player_saves(payload, 'D. Raya')[0])

    def test_malformed_event_is_not_a_zero(self):
        for shots in ([None], [{}]):
            payload = self.payload()
            self.content(payload)['shotmap']['shots'] = shots
            self.assertIsNone(settle.fotmob_player_saves(payload, 'D. Raya')[0])

    def test_unattributed_save_is_not_a_zero(self):
        payload = self.payload()
        self.content(payload)['shotmap']['shots'] = [{'id': 1, 'eventType': 'AttemptSaved'}]
        self.assertIsNone(settle.fotmob_player_saves(payload, 'D. Raya')[0])

    def test_complete_map_can_show_zero_named_keeper_saves(self):
        self.assertEqual(settle.fotmob_player_saves(self.payload(), 'D. Raya')[0], 0)

    def test_goal_line_clearance_and_block_are_not_keeper_saves(self):
        payload = self.payload()
        self.content(payload)['shotmap']['shots'] = [
            {'id': 1, 'eventType': 'AttemptSaved', 'keeperId': 10},
            {'id': 1, 'eventType': 'AttemptSaved', 'keeperId': 10},
            {'id': 2, 'eventType': 'AttemptSaved', 'isBlocked': True},
            {'id': 3, 'eventType': 'AttemptSaved', 'isSavedOffLine': True},
            {'id': 4, 'eventType': 'AttemptSaved', 'keeperId': 20},
        ]
        self.assertEqual(settle.fotmob_player_saves(payload, 'D. Raya')[0], 1)

    def test_api_named_keeper_valid_zero_and_invalid_counts(self):
        payload = {'response': [{'players': [{'player': {'id': 10, 'name': 'David Raya'},
            'statistics': [{'games': {'position': 'G', 'minutes': 90}, 'goals': {'saves': 0}}]}]}]}
        self.assertEqual(settle.player_saves(payload, 'D. Raya')[0], 0)
        stats = payload['response'][0]['players'][0]['statistics'][0]
        for value in ('3.9', '-1', 'NaN', 'inf', None, True):
            stats['goals']['saves'] = value
            self.assertIsNone(settle.player_saves(payload, 'D. Raya')[0])
        stats['goals']['saves'] = 3
        stats['games']['position'] = 'D'
        self.assertIsNone(settle.player_saves(payload, 'D. Raya')[0])


if __name__ == '__main__':
    unittest.main()
