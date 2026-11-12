import copy
import csv
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import corners_candidate_evidence as E

NOW = datetime(2026,11,12,12,tzinfo=timezone.utc)


def write_csv(path, values):
    path.parent.mkdir(parents=True,exist_ok=True)
    fields = list(dict.fromkeys(k for r in values for k in r)) or ['empty']
    with path.open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(values)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.V=E.publisher(ROOT)
        self.params=json.loads((ROOT/'data/corners-ou/corners-v3-params.json').read_text())
        self.lock=json.loads((ROOT/'data/corners-ou/corners-v3-lock.json').read_text())
        self.output=self.root/E.RELATIVE
        E.atomic(self.output/'registration.json',dict(registered_at=(NOW-timedelta(hours=1)).isoformat()))
        for rel in E.INPUTS:write_csv(self.root/rel,[])
        E.atomic(self.root/'config/corners-evidence-rules.json',E.read_json(ROOT/'config/corners-evidence-rules.json'))
        E.atomic(self.root/'data/corners-ou/corners-v3-params.json',self.params)
        E.atomic(self.root/'data/corners-ou/corners-v3-lock.json',self.lock)
        E.atomic(self.root/'data/football-form/count-input-identity-health.json',dict(generated_at=NOW.isoformat()))
        self.form={'ema20_matches':20,'ema20_corners_for_avg':5,'ema20_corners_against_avg':5,
                   'ema20_shots_for_avg':12.5,'league_prior_corners_for_avg':5,'league_prior_shots_for_avg':12.5}
        self.events=[dict(date=f'2026-10-{d:02}',league='epl',home_team='Arsenal',away_team='Chelsea',
                         home_wide_share=.2,away_wide_share=.2,home_blocked_rate=.2,away_blocked_rate=.2) for d in range(1,10)]
        write_csv(self.root/E.INPUTS[1],self.events)
        for p in [patch.object(E,'publisher',return_value=self.V),
                  patch.object(self.V,'CORNERS_PARAMS',self.root/'data/corners-ou/corners-v3-params.json'),
                  patch.object(self.V,'CORNERS_LOCK',self.root/'data/corners-ou/corners-v3-lock.json'),
                  patch.object(self.V.PUB,'live_form_row',return_value=self.form)]:
            p.start();self.addCleanup(p.stop)
        states=self.V.latest_event_states(self.events,self.params,before=NOW.date())
        mean,features=self.V.corners_features(self.form,self.form,states[('epl','arsenal')],states[('epl','chelsea')],self.params)
        mu=self.V.predict_corners_mean(mean,features,self.params)
        prob=self.V.prob_over(10.5,mu,distribution='negative_binomial',alpha=self.params['alpha'])
        self.quotes=[dict(captured_at=NOW.isoformat(),kickoff_iso=(NOW+timedelta(hours=5)).isoformat(),
            league='epl',home_team='Arsenal',away_team='Chelsea',line=10.5,side=s,
            odds_decimal=.99/p,bookmaker='Pinnacle') for s,p in [('over',prob),('under',1-prob)]]

    def board(self, quotes=None):
        quotes=self.quotes if quotes is None else quotes
        write_csv(self.root/E.INPUTS[2],quotes)
        selected,candidates=self.V.score_corners(by_team={},by_league={},odds_rows=quotes,
            event_rows=self.events,params=self.params,lock=self.lock,now=NOW)
        self.V.write_csv(self.root/'data/football-form/football-counts-vnext-candidates.csv',candidates)
        return selected,candidates

    def observations(self):
        return [E.read_json(p) for p in (self.output/'observations').glob('*.json')]

    def test_all_no_bets_and_full_precision_inputs_preserved(self):
        _,candidates=self.board()
        self.assertEqual(len(candidates),2)
        self.assertTrue(all('edge_below_3pct' in r['blocked_reason'] for r in candidates))
        status=E.collect(self.root,NOW,self.output)
        self.assertEqual(status['eligible_pairs_this_scan'],1)
        record=self.observations()[0]
        self.assertEqual(set(record['forecasts']),{'over','under'})
        self.assertTrue(all(r['decision']=='no_bet' for r in record['forecasts'].values()))
        context=E.read_json(self.output/'inputs'/(record['context_id']+'.json'))
        self.assertEqual(len(context['features']),7)
        self.assertEqual(context['home_event_matches'],9)
        self.assertAlmostEqual(sum(r['p'] for r in record['forecasts'].values()),1)
        self.assertEqual(record['pair']['over']['raw']['line'],'10.5')

    def test_repeat_retains_first_seen_and_does_not_touch_issued_files(self):
        self.board(); E.collect(self.root,NOW,self.output)
        before={p:p.read_bytes() for p in (self.output/'observations').glob('*.json')}
        issued=self.root/'data/football-form/football-counts-vnext-candidates.csv'
        original=issued.read_bytes()
        status=E.collect(self.root,NOW+timedelta(seconds=20),self.output)
        self.assertEqual(status['new_observations'],0)
        self.assertEqual(before,{p:p.read_bytes() for p in before})
        self.assertEqual(issued.read_bytes(),original)

    def test_changed_board_blocks_capture_instead_of_retrying(self):
        _,candidates=self.board()
        candidates[0]['model_implied_prob']=.999
        self.V.write_csv(self.root/'data/football-form/football-counts-vnext-candidates.csv',candidates)
        with self.assertRaisesRegex(ValueError,'parity_mismatch'):
            E.refresh(self.root,NOW,self.output)
        self.assertEqual(self.observations(),[])
        self.assertEqual(E.read_json(self.output/'capture-status.json')['state'],'CAPTURE_ERROR')

    def test_entire_ladder_and_books_are_separate(self):
        quotes=self.quotes+[dict(r,line=11.5) for r in self.quotes]+[dict(r,bookmaker='Bet365') for r in self.quotes]
        self.board(quotes);E.collect(self.root,NOW,self.output)
        records=self.observations()
        self.assertEqual(len(records),3)
        self.assertEqual(len({r['contract_id'] for r in records}),3)
        self.assertEqual(sum(r['primary_line'] for r in records),2)

    def test_unpaired_and_integer_quotes_are_retained_not_invented(self):
        self.board([self.quotes[0],dict(self.quotes[1],line=10)])
        E.collect(self.root,NOW,self.output)
        records=self.observations();self.assertEqual(len(records),2)
        self.assertTrue(all(not r['research_eligible'] for r in records))
        self.assertTrue(all(r['forecasts']=={} for r in records))

    def test_mixed_capture_times_are_excluded_without_changing_publisher(self):
        q=copy.deepcopy(self.quotes);q[1]['captured_at']=(NOW-timedelta(seconds=1)).isoformat()
        _,candidates=self.board(q);self.assertEqual(len(candidates),2)
        E.collect(self.root,NOW,self.output)
        self.assertIn('different_pair_observation_times',self.observations()[0]['exclusion_reasons'])

    def test_stale_and_future_prices_are_not_prospective(self):
        for delta in [-601,1]:
            with self.subTest(delta=delta):
                pair={r['side']:dict(raw=r,captured_at=(NOW+timedelta(seconds=delta)).isoformat(),line=10.5,odds=1.9) for r in self.quotes}
                self.assertIn('quote_not_fresh_10m',E.price_reasons(pair,NOW))

    def test_reschedule_dedup_and_reversed_home_away(self):
        row=dict(match_date='2026-11-12',league='epl',home_team='Arsenal',away_team='Chelsea')
        self.assertEqual(E.stable_fixture(row),E.stable_fixture(dict(row,match_date='2026-12-12')))
        self.assertNotEqual(E.stable_fixture(row),E.stable_fixture(dict(row,home_team='Chelsea',away_team='Arsenal')))

    def test_one_missing_history_fixture_does_not_block_other(self):
        q=self.quotes+[dict(r,home_team='Unmapped Club') for r in self.quotes]
        with patch.object(self.V.PUB,'live_form_row',side_effect=lambda **kw: None if kw['team']=='Unmapped Club' else self.form):
            self.board(q);E.collect(self.root,NOW,self.output)
        records=self.observations();self.assertEqual(len(records),2)
        self.assertEqual(sum(r['research_eligible'] for r in records),1)
        self.assertTrue(any('missing_team_history' in r['exclusion_reasons'] for r in records))

    def test_exact_results_append_corrections_and_never_rewrite_predictions(self):
        self.board();E.collect(self.root,NOW,self.output)
        before={p:p.read_bytes() for p in (self.output/'observations').glob('*.json')}
        later=NOW+timedelta(days=1)
        result=dict(home_team='Arsenal',away_team='Chelsea',home_corners=7,away_corners=4,total_corners=11,source='football-data')
        path=self.root/'data/results-snapshot/2026-11-12.json'
        def put(r):E.atomic(path,dict(fetched_at=later.isoformat(),leagues={'epl':{'fixtures':{'2026-11-12|Arsenal|Chelsea':r}}}))
        put(result);self.assertEqual(E.settle(self.root,self.output,later)['new_result_observations'],1)
        self.assertEqual(E.settle(self.root,self.output,later)['new_result_observations'],0)
        put(dict(result,home_corners=6,total_corners=10))
        self.assertEqual(E.settle(self.root,self.output,later)['new_result_observations'],1)
        self.assertEqual(before,{p:p.read_bytes() for p in before})

    def test_unfinished_or_other_date_outcomes_stay_pending(self):
        self.board();E.collect(self.root,NOW,self.output)
        later=NOW+timedelta(days=1)
        result=dict(home_team='Arsenal',away_team='Chelsea',total_corners=11,source='football-data',status='abandoned')
        E.atomic(self.root/'data/results-snapshot/2026-11-12.json',dict(fetched_at=later.isoformat(),
            leagues={'epl':{'fixtures':{'2026-11-12|Arsenal|Chelsea':result}}}))
        self.assertEqual(E.settle(self.root,self.output,later)['pending'],1)
        self.assertFalse(list((self.output/'results').glob('*.json')))

    def test_no_prices_is_explicit_empty_scan_not_operating_claim(self):
        self.board([]);s=E.refresh(self.root,NOW,self.output)
        self.assertEqual(s['available_book_line_pairs'],0)
        self.assertEqual(s['state'],'NO_ELIGIBLE_NEW_OPPORTUNITIES')
        self.assertEqual(s['settlement']['first_eligible_contracts'],0)

    def test_no_bets_join_existing_pending_result_queue_once_per_fixture(self):
        self.board(self.quotes+[dict(r,line=11.5) for r in self.quotes])
        E.collect(self.root,NOW,self.output)
        self.assertEqual(E.pending_result_fixtures(self.root,NOW),[])
        pending=E.pending_result_fixtures(self.root,NOW+timedelta(days=1))
        self.assertEqual(len(pending),1)
        self.assertEqual(pending[0]['home_team'],'Arsenal')

    def test_nonfinite_quotes_are_retained_as_invalid_without_poisoning_other_fixture(self):
        q=self.quotes+[dict(r,line=11.5,odds_decimal='NaN') for r in self.quotes]
        self.board(q);E.collect(self.root,NOW,self.output)
        records=self.observations()
        self.assertEqual(sum(r['research_eligible'] for r in records),1)
        self.assertTrue(any('invalid_decimal_price' in r['exclusion_reasons'] for r in records))

    def test_conflicting_same_time_markets_are_retained_and_quarantined(self):
        q=self.quotes+[dict(self.quotes[0],odds_decimal=3.25,market='MATCH_CORNERS_ALT')]
        self.board(q);E.collect(self.root,NOW,self.output)
        record=self.observations()[0]
        self.assertFalse(record['research_eligible'])
        self.assertIn('ambiguous_same_book_market_snapshot',record['exclusion_reasons'])
        self.assertEqual(len(record['pair']['over']['ambiguous_same_capture']),1)

    def test_cups_and_split_leagues_never_get_home_leg_identity(self):
        for league in ['scotland','fa-cup','championship','bundesliga-playoffs']:
            self.assertIsNone(E.stable_fixture(dict(match_date='2026-11-12',league=league,
                home_team='Arsenal',away_team='Chelsea')))


if __name__=='__main__':unittest.main()
