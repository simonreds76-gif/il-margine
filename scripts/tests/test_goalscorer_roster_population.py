import contextlib
import csv
import importlib.util
import io
import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('live_roster_test', SCRIPTS/'goalscorer-live-compare.py')
LIVE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(LIVE)


class RosterIntegrationTests(unittest.TestCase):
    def run_model(self, selected, *, missing=False, predicted=False, duplicate=False, reserve_role=None, new_starter=False):
        names = ['Alden', 'Barton', 'Corbett', 'Dawson', 'Elwood', 'Fenton', 'Granger',
                 'Hawthorne', 'Irvine', 'Jarvis', 'Kendall', 'Linton']
        players = {side:[side+' '+name for name in names] for side in ('Home', 'Away')}
        logs=[]
        for day in range(1,9):
            for side, team, opponent in [('Home','Arsenal','Chelsea'),('Away','Chelsea','Arsenal')]:
                for i,name in enumerate(players[side]):
                    logs.append(dict(season='2026-2027',match_date=f'2026-08-{day:02d}',
                        player_id=f'{side}{i}',player_name=name,team=team,opponent=opponent,
                        is_home=int(side=='Home'),position='GK' if i==0 else 'FW',started=int(i<11),
                        minutes=90 if i<11 else 20,goals=0,shots=i/3,xg=i/50,npxg=i/50,
                        penalties_scored=0,penalties_attempted=0,team_xg=1.5,team_xga=1.5))
        fixture=dict(match_date='2026-08-10',home_team='Arsenal',away_team='Chelsea',
                     lineup_type='predicted' if predicted else 'standard')
        for side in ('home','away'):
            squad=players[side.title()]
            fixture[side+'_players']=squad[:11]
            fixture[side+'_subs']=squad[11:]
            fixture[side+'_starters']=[dict(name=squad[0],role_group='GK')]
        if missing: fixture['home_subs']=['Unresolved New Signing']
        if reserve_role:
            fixture['home_substitute_entries']=[dict(name='Unresolved New Signing',player_id='999999',role_group=reserve_role)]
        if duplicate: fixture['home_players'][-1]=fixture['home_players'][1]
        if new_starter:
            fixture['home_players'][-1]='Unresolved New Signing'
            fixture['home_starters'].append(dict(name='Unresolved New Signing',player_id='999998',role_group='FW'))
        odds=[dict(captured_at='2026-08-10T12:00:00Z',match_date='2026-08-10',
                   bookmaker='Bet365',competition='Premier League',home_team='Arsenal',away_team='Chelsea',
                   player_name=players['Home'][i],player_team='Arsenal',odds_decimal=4,implied_prob=.25)
              for i in selected]
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            for filename,rows in [('logs.csv',logs),('odds.csv',odds)]:
                with (folder/filename).open('w',newline='') as handle:
                    writer=csv.DictWriter(handle,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
            (folder/'lineups.json').write_text(json.dumps({'fixtures':[fixture]}))
            (folder/'empty.json').write_text('{}')
            argv=['live','--league','epl','--data',str(folder/'logs.csv'),'--odds',str(folder/'odds.csv'),
                  '--lineups',str(folder/'lineups.json'),'--skip-roster-fetch','--out-dir',str(folder/'output'),
                  '--penalty-hierarchy',str(folder/'empty.json'),
                  '--penalty-baseline-evidence',str(folder/'empty.json'),
                  '--penalty-baseline-overrides',str(folder/'empty.json')]
            with patch.object(sys,'argv',argv),patch.object(LIVE,'write_outputs') as write,contextlib.redirect_stdout(io.StringIO()):
                LIVE.main()
            self.last_forecasts=json.loads((folder/'output/fair-odds-player-forecasts.json').read_text())['players']
            return write.call_args.args[0]

    def test_removing_quotes_cannot_inflate_probability_or_emit_unquoted_players(self):
        full=self.run_model(range(1,12))
        sparse=self.run_model([10])
        target=next(r for r in full if r['player_id']=='Home10')
        self.assertEqual(len(sparse),1)
        self.assertEqual(len(self.last_forecasts),20)
        self.assertTrue(all(r['allocation_status']=='confirmed_roster' for r in self.last_forecasts))
        for field in ('model_p_atgs','model_lambda','non_pen_lambda','team_share','model_version'):
            self.assertEqual(target[field],sparse[0][field],field)
        self.assertEqual(sparse[0]['allocation_status'],'confirmed_roster')
        self.assertGreater(sparse[0]['model_p_atgs'],0)
        self.assertLessEqual(sum(r['team_share'] for r in full),1)

    def test_reordering_market_and_adding_keeper_cannot_change_outfield_price(self):
        a=self.run_model([10,3])[0:]
        b=self.run_model([0,3,10])
        by_id={r['player_id']:r for r in b}
        for row in a:
            self.assertEqual(row['model_p_atgs'],by_id[row['player_id']]['model_p_atgs'])
        # The existing pipeline omits goalkeeper selections entirely.
        self.assertNotIn('Home0',by_id)

    def test_unresolved_roster_is_not_publishable(self):
        for change in ({'missing':True},{'duplicate':True}):
            with self.subTest(change=change):
                row=self.run_model([10],**change)[0]
                self.assertEqual(row['allocation_status'],'incomplete_roster')
                self.assertNotEqual(row['public_action'],'surface')
                self.assertEqual(row['recommended_stake_units'],0)

    def test_expected_roster_remains_provisional_and_quote_independent(self):
        full=self.run_model(range(1,11),predicted=True)
        sparse=self.run_model([10],predicted=True)
        self.assertEqual(sparse[0]['allocation_status'],'expected_roster')
        self.assertEqual(sparse[0]['model_p_atgs'],next(r['model_p_atgs'] for r in full if r['player_id']=='Home10'))
        self.assertNotEqual(sparse[0]['public_action'],'surface')
    def test_identified_new_starter_does_not_hide_the_entire_team(self):
        rows=self.run_model([9],predicted=True,new_starter=True)
        self.assertEqual(len(self.last_forecasts),20)
        newcomer=next(r for r in self.last_forecasts if r['player_name']=='Unresolved New Signing')
        self.assertTrue(newcomer['limited_data'])
        self.assertEqual(newcomer['allocation_status'],'estimated_roster')
        self.assertGreater(newcomer['probability'],0.02)
        self.assertNotEqual(rows[0]['public_action'],'surface')
        self.assertEqual(rows[0]['recommended_stake_units'],0)
    def test_daily_rates_conserve_team_budget_and_are_quote_independent(self):
        self.run_model([10])
        sparse={r['player_name']:r for r in self.last_forecasts}
        self.run_model(range(1,11))
        for row in self.last_forecasts:
            self.assertAlmostEqual(row['probability'],sparse[row['player_name']]['probability'])
        self.assertLessEqual(sum(r['non_pen_lambda'] for r in self.last_forecasts if r['player_team']=='Arsenal'),1.5)

    def test_lineup_without_any_market_still_gets_forecasts_but_no_bets(self):
        with patch.object(LIVE,'load_odds_rows',return_value=[]):
            self.assertEqual(self.run_model([10]),[])
        self.assertEqual(len(self.last_forecasts),20)
        self.assertTrue(all(0<r['probability']<1 for r in self.last_forecasts))

    def test_named_reserve_uses_existing_position_prior_without_emitting_a_quote(self):
        full=self.run_model(range(1,11),missing=True,reserve_role='FW')
        sparse=self.run_model([10],missing=True,reserve_role='FW')
        target=next(r for r in full if r['player_id']=='Home10')
        self.assertEqual(target['allocation_status'],'confirmed_roster')
        self.assertEqual(target['roster_prior_players'],1)
        self.assertEqual(target['model_p_atgs'],sparse[0]['model_p_atgs'])
        self.assertEqual(len(sparse),1)
        self.assertFalse(any(r['player_id'].startswith('fotmob:') for r in full))

    def test_explicit_reserve_keeper_is_excluded_without_blocking_the_squad(self):
        row=self.run_model([10],missing=True,reserve_role='GK')[0]
        self.assertEqual(row['allocation_status'],'confirmed_roster')
        self.assertEqual(row['roster_prior_players'],0)

    def test_lab_blocks_incomplete_roster_before_other_publication_filters(self):
        lab=runpy.run_path(str(SCRIPTS/'generate-fair-odds-lab.py'),run_name='lab_roster_quality_test')
        reason=lab['public_quality_exclusion_reason'](SimpleNamespace(row={'allocation_status':'incomplete_roster'}),
            min_model_prob_pct=20,max_market_odds=6,official_lineup_window_minutes=75,allow_projected_lineups=False)
        self.assertEqual(reason,'incomplete_prediction_roster')

    def test_fetched_reserve_roles_do_not_turn_missing_positions_into_goalkeepers(self):
        fetch=runpy.run_path(str(SCRIPTS/'fotmob-fetch-lineups.py'),run_name='fetch_roster_quality_test')
        entries=fetch['_substitute_entries']([dict(id=1,name='Known Keeper',usualPlayingPositionId=0),
            dict(id=2,name='Unknown'),dict(id=3,name='Malformed',usualPlayingPositionId=False)])
        self.assertEqual([e['role_group'] for e in entries],['GK','',''])


if __name__=='__main__': unittest.main()
