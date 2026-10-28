import copy
import unittest
from test_gk_fotmob_identity import settle


class NamedNonstarterTests(unittest.TestCase):
    def setUp(self):
        self.signal = dict(bookmaker='Bet365', venue='home', goalkeeper='Absent Keeper', status='pending')
        starters = [dict(id=i, name=f'Outfielder {i}', positionId=30) for i in range(1, 11)]
        starters.append(dict(id=11, name='Actual Goalie', positionId=11))
        self.page = {'props': {'pageProps': {'general': {'finished': True, 'matchId': '12'},
            'content': {'lineup': {'homeTeam': {'starters': starters,
                'subs': [dict(id=12, name='Absent Keeper')]}},
                'playerStats': {'11': {'stats': [{'stats': {'minutes_played': {'key': 'minutes_played', 'stat': {'value': 90}}}}]}}}}}}

    def test_bench_keeper_missing_position_is_verified_nonstarter(self):
        evidence = settle.fotmob_named_nonstarter(self.page, self.signal)
        self.assertEqual(evidence['actual_starter_id'], 11)
        self.assertEqual(evidence['reason'], 'verified_named_nonstarter')
        self.assertEqual(len(evidence['source_sha256']), 64)

    def test_absent_squad_keeper_requires_same_complete_evidence(self):
        self.page['props']['pageProps']['content']['lineup']['homeTeam']['subs'] = []
        self.assertIsNotNone(settle.fotmob_named_nonstarter(self.page, self.signal))

    def test_partial_lineups_minutes_and_wrong_side_cannot_void(self):
        for change in ('partial_xi', 'duplicate_id', 'missing_minutes', 'substitution', 'not_finished', 'wrong_side'):
            with self.subTest(change=change):
                p = copy.deepcopy(self.page); s = self.signal.copy()
                content = p['props']['pageProps']['content']
                if change == 'partial_xi': content['lineup']['homeTeam']['starters'].pop(0)
                if change == 'duplicate_id': content['lineup']['homeTeam']['starters'][0]['id'] = 11
                if change == 'missing_minutes': content['playerStats'] = {}
                if change == 'substitution': content['playerStats']['11']['stats'][0]['stats']['minutes_played']['stat']['value'] = 60
                if change == 'not_finished': p['props']['pageProps']['general']['finished'] = False
                if change == 'wrong_side': s['venue'] = 'away'
                self.assertIsNone(settle.fotmob_named_nonstarter(p, s))

    def test_starter_name_collision_is_held_even_if_position_missing(self):
        self.page['props']['pageProps']['content']['lineup']['homeTeam']['starters'][0]['name'] = 'Absent Keeper'
        self.assertIsNone(settle.fotmob_named_nonstarter(self.page, self.signal))

    def test_other_team_identity_is_held(self):
        self.page['props']['pageProps']['content']['lineup']['awayTeam'] = {'subs': [{'name': 'Absent Keeper'}]}
        self.assertIsNone(settle.fotmob_named_nonstarter(self.page, self.signal))

    def test_other_operators_and_team_contracts_do_not_inherit_bet365_rules(self):
        for extra in ({'bookmaker': 'Grosvenor'}, {'bookmaker': 'Sisal IT'},
                      {'contract_scope': 'team_goalkeeper_home'}, {'goalkeeper': 'Keeper'}):
            self.assertIsNone(settle.fotmob_named_nonstarter(self.page, {**self.signal, **extra}))

    def test_void_has_no_invented_save_count_profit_or_clv(self):
        s = {**self.signal, 'odds_decimal': '2.625', 'stake_units': '.5', 'model_probability': '.51'}
        settle.void_named_nonstarter(s, '2026-10-28T16:00:00Z')
        self.assertEqual((s['status'], s['actual_saves'], s['pnl_units']), ('void', '', '0.0000'))
        self.assertEqual((s['odds_decimal'], s['stake_units'], s['model_probability']), ('2.625', '.5', '.51'))


if __name__ == '__main__': unittest.main()
