from pathlib import Path
from unittest import TestCase, mock
import ast
import csv
import importlib.util
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from tennis_source_contract import canonical_surface, court_surfaces, service_points, validate_profiles, stat_problem, validated_stat_rows, write_profile_contract, current_profile_rows
from matchup_model import MatchupStats, compute_matchup_point_probs


class SourceContractTests(TestCase):
    def test_live_stats_handicap_venue_and_replay_agree(self):
        for filename in ('oncourt-compute-fair-odds.py', 'oncourt-compute-player-stats.py',
                         'oncourt-compute-player-stats-extended.py', 'compute-handicap-values.py',
                         'oncourt-compute-tournament-avg-games.py', 'backtest-fair-odds.py'):
            tree = ast.parse((SCRIPTS/filename).read_text(encoding='utf-8'))
            node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_court_to_surface')
            namespace = {}
            exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), filename, 'exec'), namespace)
            for source, expected in {'I.hard':'I.hard','Indoor Hard':'I.hard','Grass':'Grass','Carpet':'Carpet','Acrylic':'Hard','unknown':'N/A'}.items():
                with self.subTest(script=filename,source=source):
                    self.assertEqual(namespace['_court_to_surface'](source),expected)

    def test_court_reference_ids_are_not_assumed(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'courts.csv'
            path.write_text('id,name\n3,I.hard\n4,Carpet\n5,Grass\n10,N/A\n',encoding='utf-8')
            self.assertEqual(court_surfaces(path),{'3':'I.hard','4':'Carpet','5':'Grass','10':'N/A'})
            self.assertEqual(court_surfaces(path,combine_hard=True)['3'],'Hard')
            path.write_text('id,name\n3,I.hard\n3,Grass\n',encoding='utf-8')
            with self.assertRaises(ValueError):court_surfaces(path)

    def test_service_points_do_not_add_second_serves(self):
        # Real source example: 52 first serves in plus 19 second opportunities = 71 points.
        row={'w_fsof':'71','w_svpt':'71','w_fs':'52','w_w2sof':'19'}
        self.assertEqual(service_points(row,'w_'),71)
        self.assertEqual(service_points({'w_fsof':'71'},'w_'),71)
        for bad in ({'w_svpt':'90','w_fsof':'71'},{'w_fsof':'-2'},{}):
            with self.assertRaises(ValueError):service_points(bad,'w_')

    def test_old_denominator_profiles_are_rejected(self):
        row=dict(first_serve_pct=.60,first_serve_win_pct=.75,second_serve_win_pct=.5,hold_pct=.65)
        validate_profiles([row])
        with self.assertRaisesRegex(ValueError,'denominators'):
            validate_profiles([{**row,'hold_pct':.65/1.4}])

    def test_double_faults_are_counted_once(self):
        server=MatchupStats(first_serve_pct=.6,first_serve_win_pct=.75,second_serve_win_pct=.5,
                            df_rate=.04,ace_rate=.08,match_count=50,service_pts=3000)
        returner=MatchupStats(return_pct=.36)
        probability,_=compute_matchup_point_probs(server,returner,'Hard')
        self.assertAlmostEqual(probability,.6*.75+.4*.5,places=10)
        # Holding observed win rates fixed, a separate DF marginal must not subtract the same losses again.
        server.df_rate=0
        zero,_=compute_matchup_point_probs(server,returner,'Hard')
        self.assertEqual(probability,zero)

    def test_sparse_player_fallback_uses_points_not_service_games(self):
        server=MatchupStats(hold_pct=.65,return_pct=.36)
        returner=MatchupStats(return_pct=.36)
        p,_=compute_matchup_point_probs(server,returner,'Hard')
        self.assertAlmostEqual(p,.65)

    def test_fatigue_counts_a_match_returned_by_both_queries_once(self):
        from live_model_v2 import LiveModelV2
        from datetime import date
        model=LiveModelV2('https://example.test','test')
        model.tour_to_surface={99:'I.hard'}
        row={'winner_id':1,'loser_id':2,'tour_id':99,'round_id':4,'date':'2026-10-06','result':'6-3 6-4'}
        once=model._build_recent_matches(1,[row,row],date(2026,10,7))
        self.assertEqual(len(once),1)
        self.assertEqual(once[0].total_games,19)
        self.assertEqual(model._build_recent_matches(1,[row,{**row,'date':'2026-10-05'}],date(2026,10,7)),[])

    def test_live_decomposed_profiles_reject_old_denominators(self):
        from live_model_v2 import LiveModelV2
        model=LiveModelV2('https://example.test','test')
        row=dict(player_id=1,surface='Hard',first_serve_pct=.6,
                 first_serve_win_pct=.75,second_serve_win_pct=.5,hold_pct=.46)
        response=mock.Mock(status_code=200)
        response.json.return_value=[row]
        with mock.patch('requests.get',return_value=response), \
             mock.patch('tennis_source_contract.current_profile_rows',side_effect=lambda rows:rows):
            with self.assertRaisesRegex(ValueError,'denominators'):
                model.load_data(set(),set(),{})

    def test_second_serve_probability_matches_count_identity(self):
        points,first_in,first_won,second_won=100,60,45,20
        p=first_in/points*(first_won/first_in)+(1-first_in/points)*(second_won/(points-first_in))
        self.assertAlmostEqual(p,(first_won+second_won)/points)

    @staticmethod
    def source_row():
        row=dict(winner_id='1',loser_id='2',tour_id='99',round_id='4')
        for prefix in ('w_','l_'):
            row.update({prefix+k:str(v) for k,v in dict(fsof=100,svpt=100,fs=60,w1s=45,w2s=20,w2sof=40,rpw=35,rpwof=100).items()})
        return row

    def test_reciprocal_counts_and_duplicates(self):
        row=self.source_row()
        self.assertIsNone(stat_problem(row))
        accepted,reasons=validated_stat_rows([row,row],{(1,2,99,4)})
        self.assertEqual(accepted,[row])
        self.assertEqual(reasons['identical_duplicates_removed'],1)
        bad={**row,'w_rpw':'20'}
        self.assertEqual(stat_problem(bad),'nonreciprocal_point_counts')
        accepted,reasons=validated_stat_rows([row,bad],{(1,2,99,4)})
        self.assertEqual(accepted,[])
        self.assertEqual(reasons['conflicting_duplicate_stat'],2)

    def test_current_contract_excludes_older_rows_without_mutating_them(self):
        rows=[dict(player_id=i,surface='Hard') for i in range(100)]
        old=dict(player_id=100,surface='I.hard',hold_pct=.40)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'contract.json'
            write_profile_contract(rows,path)
            self.assertEqual(current_profile_rows(rows+[old],path),rows)
            self.assertEqual(old['hold_pct'],.40)
            with self.assertRaisesRegex(ValueError,'incomplete'):
                write_profile_contract([],path)

    def test_board_rejects_unknown_court_instead_of_guessing_clay(self):
        spec=importlib.util.spec_from_file_location('source_test_board',SCRIPTS/'build-tennis-props-board.py')
        board=importlib.util.module_from_spec(spec);spec.loader.exec_module(board)
        with mock.patch.object(board,'court_surfaces',return_value={'1':'Hard'}), \
             mock.patch.object(board,'load_oncourt_player_names',return_value={}), \
             mock.patch.object(board,'load_oncourt_tours',return_value={'9':{'id':'9','name':'Shanghai','rank':'3','court_id':'99'}}), \
             mock.patch.object(board,'read_csv',return_value=[{'tour_id':'9','result':''}]):
            with self.assertRaisesRegex(ValueError,'Unknown OnCourt court'):
                board.oncourt_schedule_rows('ATP',False,'2026-10-07')


if __name__=='__main__':unittest.main()
