import importlib.util
from pathlib import Path
import unittest

P = Path(__file__).resolve().parents[1]/'understat-download-shots.py'
S = importlib.util.spec_from_file_location('understat_coverage', P)
M = importlib.util.module_from_spec(S); S.loader.exec_module(M)

class CoverageTests(unittest.TestCase):
    def rows(self):
        return [dict(date='2026-09-06', home_team='Hamburg', away_team='Mainz',
                     _norm_home=M._normalise_team('Hamburg'), _norm_away=M._normalise_team('Mainz'),
                     home_goals='0', away_goals='5')]

    def test_verified_hamburg_alias_joins_exact_fixture(self):
        rows=self.rows()
        lookup={'2026-09-06:hamburgersv:mainz05':dict(home_goals='0',away_goals='5',home_xg=.257239,away_xg=3.27983)}
        self.assertEqual(M.merge_xg(rows, lookup), (1,1))
        self.assertEqual(rows[0]['away_xg'],3.27983)
        self.assertEqual(M.xg_join_health(rows,lookup)['missing'],0)

    def test_wrong_score_is_rejected_and_named_in_health(self):
        rows=self.rows()
        lookup={'2026-09-06:hamburgersv:mainz05':dict(home_goals='2',away_goals='1',home_xg=2,away_xg=1)}
        self.assertEqual(M.merge_xg(rows,lookup),(0,1))
        report=M.xg_join_health(rows,lookup)
        self.assertEqual(report['fixtures'][0]['reason'],'score_mismatch')
        self.assertIn('Hamburg',report['affected_clubs'])

    def test_verified_parma_alias_joins_exact_fixture(self):
        rows=[dict(date='2026-10-28', home_team='Parma', away_team='Udinese',
                   _norm_home=M._normalise_team('Parma'), _norm_away=M._normalise_team('Udinese'),
                   home_goals='0', away_goals='0')]
        lookup={'2026-10-28:parmacalcio1913:udinese':dict(home_goals='0',away_goals='0',home_xg=1.1002,away_xg=1.62069)}
        self.assertEqual(M.merge_xg(rows,lookup),(1,1))
        self.assertEqual(rows[0]['home_xg'],1.1002)

    def test_unmatched_is_not_fuzzily_assigned_and_prior_verified_pair_survives(self):
        rows=self.rows(); self.assertEqual(M.merge_xg(rows,{}),(0,1))
        self.assertEqual(M.xg_join_health(rows,{})['fixtures'][0]['reason'],'no_exact_fixture')
        prior=dict(rows[0],league='bundesliga',home_xg=.25,away_xg=3.28,source='football-data+understat-xg')
        recovered=M.merge_existing_rows([prior],[dict(rows[0],league='bundesliga')])[0]
        self.assertEqual(recovered['away_xg'],3.28)

if __name__=='__main__':unittest.main()
