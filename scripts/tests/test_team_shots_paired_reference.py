import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('paired_test',ROOT/'scripts/team-shots-paired-reference.py')
P=importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
NOW=datetime(2026,9,30,12,tzinfo=timezone.utc)

def record(cid='x',prob=.6):
    return dict(contract_id=cid,registered_at_utc=NOW.isoformat(),kickoff_utc=(NOW+timedelta(hours=2)).isoformat(),
        match_date='2026-09-30',league='epl',home_team='Arsenal',away_team='Chelsea',team='Arsenal',
        line=10.5,bookmaker='Bet365',odds={'over':2.,'under':2.},models={m:dict(p_over=prob,mean=12.,minimum_edge=.05) for m in P.MODELS})

class PairedTests(unittest.TestCase):
    def test_frozen_calibration_is_exact_registered_transform(self):
        pair={s:{'odds':v} for s,v in [('over',1.8),('under',2.1)]}
        raw=dict(raw_p_over=.7,mean=13.,alpha=.1,feature_inputs={'prior_matches':20})
        forecast=P.calibrated_forecast(raw,pair)
        import math
        q=(1/1.8)/(1/1.8+1/2.1)
        z=math.log(q/(1-q))+.07481677660354566+.26634934409525224*(math.log(.7/.3)-math.log(q/(1-q)))
        self.assertAlmostEqual(forecast['p_over'],1/(1+math.exp(-z)))
        self.assertEqual(forecast['minimum_edge'],.03)
        self.assertEqual(forecast['real_stake_units'],0)
        self.assertIn('unavailable',P.calibrated_forecast({},pair))

    def test_new_cohort_keeps_old_bytes_and_duplicate_contract_separate(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'ledger.jsonl'
            old=dict(record(),version='paired-first-quote-20260930')
            P.append_new(path,[old]); before=path.read_bytes()
            fresh=dict(record(),version=P.VERSION)
            rows,added=P.append_new(path,[fresh])
            self.assertEqual(added,1)
            self.assertTrue(path.read_bytes().startswith(before))
            self.assertEqual(P.current_cohort(rows),[fresh])

    def test_unresolved_selection_remains_pending_and_overdue(self):
        row=record();P.select_first_scan([row],[])
        early=P.summarize([row],[],NOW)['models']['shots_market_offset_v1']['hypothetical_selections']
        late=P.summarize([row],[],NOW+timedelta(days=3))['models']['shots_market_offset_v1']['hypothetical_selections']
        self.assertEqual((early['pending'],early['overdue'],early['roi']),(1,0,None))
        self.assertEqual(late['overdue'],1)

    def test_model_changes_require_a_separate_cohort(self):
        P.check_fingerprint([{'model_fingerprint':'old'}],'old')
        with self.assertRaises(ValueError):
            P.check_fingerprint([{'model_fingerprint':'old'}],'changed_weights')

    def test_append_preserves_original_and_retains_no_bet(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'ledger.jsonl'; original=record(prob=.5)
            P.select_first_scan([original],[])
            P.append_new(path,[original]); before=path.read_bytes()
            rows,added=P.append_new(path,[record(prob=.9)])
            self.assertEqual(added,0); self.assertEqual(path.read_bytes(),before)
            self.assertIsNone(rows[0]['models']['ema20_v3']['selected_side'])

    def test_no_later_price_shopping(self):
        earlier=record(prob=.5); later=record('other_line',.9)
        P.select_first_scan([later],[earlier])
        self.assertIsNone(later['models']['ema20_v3']['selected_side'])

    def test_one_pick_per_fixture_and_side_blockers(self):
        a,b=record('a',.7),record('b',.8)
        b['models']['v4']['selection_blockers']={'over':'early_market_gap_cap','under':''}
        P.select_first_scan([a,b],[])
        self.assertEqual(a['models']['v4']['selected_side'],'over')
        self.assertIsNone(b['models']['v4']['selected_side'])
        self.assertIsNone(a['models']['ema20_v3']['selected_side'])
        self.assertEqual(b['models']['ema20_v3']['selected_side'],'over')

    def test_feature_cutoff_excludes_same_day_and_future(self):
        rows=[{'date':d} for d in ['2026-09-29','2026-09-30','2026-10-01']]
        self.assertEqual(P.prior_rows(rows,NOW.date()),rows[:1])

    def test_frozen_inference_known_values(self):
        own={'venue':'home','ema20_matches':20,'ema20_shots_for_home_avg':14}
        opp={'ema20_matches':20,'ema20_shots_against_avg':12}
        self.assertAlmostEqual(P.OLD.canonical_team_shots_ema20_lambda(own,opp),13.1)
        # Exact NB geometric distribution at alpha=1, mean=1.
        self.assertAlmostEqual(P.OLD.negative_binomial_prob_over(.5,1,1),.5)

    def test_end_to_end_fixed_models_on_synthetic_prior_history(self):
        base=[]
        for i in range(65):
            day=(NOW-timedelta(days=i+1)).date().isoformat()
            for team,opp,venue,shots in [('Arsenal','Chelsea','home',14),('Chelsea','Arsenal','away',12)]:
                base.append(dict(date=day,league='epl',season='2026-2027',team=team,opponent=opp,venue=venue,
                    home_team='Arsenal',away_team='Chelsea',shots_for=shots,shots_against=26-shots,
                    corners_for=5,corners_against=5,goals_for=1,goals_against=1,xg_for=1.4,xg_against=1.2))
        odds=[dict(kickoff_at=(NOW+timedelta(hours=2)).isoformat(),captured_at=(NOW-timedelta(minutes=5)).isoformat(),
            competition='epl',home_team='Arsenal',away_team='Chelsea',team='Arsenal',line='12.5',side=side,odds_decimal='2',bookmaker='Bet365') for side in ('over','under')]
        pairs=P.V.paired_rows(P.PUB.latest_team_shots_odds(odds,NOW),P.O.PAIR_FIELDS)
        config=P.V.load_json(P.O.CONFIG); params=P.V.load_json(P.V.TEAM_PARAMS); lock=P.V.load_json(P.V.TEAM_LOCK)
        out=P.score(pairs,odds,base,base,config,params,lock,[],NOW)
        self.assertEqual(len(out),1)
        for model in P.MODELS:
            self.assertIn('p_over',out[0]['models'][model])
        contaminated=base+[dict(base[0],date='2026-10-01',shots_for=9999)]
        other=P.score(pairs,odds,contaminated,contaminated,config,params,lock,[],NOW)
        self.assertEqual(out,other)

    def test_result_conflicts_and_fixture_sample_not_contract_sample(self):
        a,b=record('a'),record('b'); P.select_first_scan([a,b],[])
        base=[dict(date='2026-09-30',league='epl',home_team='Arsenal',away_team='Chelsea',team='Arsenal',shots_for=12)]
        status=P.summarize([a,b],base,NOW+timedelta(days=1))
        self.assertEqual(status['paired_contracts'],2); self.assertEqual(status['paired_fixtures'],1)
        self.assertAlmostEqual(status['models']['ema20_v3']['brier'],.16)
        self.assertEqual(status['models']['ema20_v3']['hypothetical_selections']['settled'],1)
        self.assertEqual(P.summarize([a],base+[dict(base[0],shots_for=13)],NOW+timedelta(days=1))['paired_contracts'],0)
        self.assertEqual(P.summarize([a],base,NOW)['settled_contracts'],0)

if __name__=='__main__': unittest.main()
