import runpy
import sys
import unittest
from pathlib import Path
SCRIPTS=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SCRIPTS))
from daily_goalscorer_rates import allocate_rates
MODEL=runpy.run_path(str(SCRIPTS/'goalscorer-model.py'))

class DailyRatesTests(unittest.TestCase):
    def test_tiny_sample_shrinks_to_position_instead_of_near_zero_raw_share(self):
        candidates=[dict(position='DC',expected_minutes=78,player_recent=dict(npxg_per_90=.001,weighted_minutes=90,n_matches=1),player_long=None),
                    dict(position='FW',expected_minutes=78,player_recent=None,player_long=None,context_only_prior=True)]
        estimates=allocate_rates(candidates,[dict(team_expected_npxg=1.3)]*2,MODEL,None,True)
        self.assertGreater(estimates[0]['probability'],.02)
        self.assertGreater(estimates[1]['probability'],estimates[0]['probability'])
        self.assertTrue(all(e['limited_data'] for e in estimates))
        self.assertAlmostEqual(sum(e['non_pen_lambda'] for e in estimates),1.3*.9)
    def test_zero_minutes_produce_zero_chance_and_no_negative_rates(self):
        row=allocate_rates([dict(position='FW',expected_minutes=0)], [dict(team_expected_npxg=1.3)],MODEL,None,True)[0]
        self.assertEqual(row['probability'],0)

if __name__=='__main__':unittest.main()
