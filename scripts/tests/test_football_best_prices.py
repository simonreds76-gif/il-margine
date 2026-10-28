import copy
import importlib.util
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPTS=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SCRIPTS))
import football_best_prices as prices

def load(name):
    spec=importlib.util.spec_from_file_location(name,SCRIPTS/(name+'.py'))
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod)
    return mod

shadow=load('publish-football-vnext-shadow')
digest=load('football-daily-signal-digest')
clv=load('corners-v0-clv-monitor')
settlement=load('settle-football-research-lanes')

NOW=datetime(2026,10,28,18,45,tzinfo=timezone.utc)

def candidate(book='Bet365',odds=2.5,**changes):
    return dict(pick_id='corners_v3|f1|over|8.5',match_id='f1',model='corners_v3',
        match_date='2026-10-28',kickoff_utc='2026-10-28T19:45:00Z',match='Genoa vs Juventus',
        bookmaker=book,book_odds=odds,price_captured_at_utc='2026-10-28T18:44:00Z',
        model_fair_odds=2,selection='over 8.5',edge=.25,blocked_reason='',**changes)

class BestPriceTests(unittest.TestCase):
    def test_higher_price_wins_even_when_other_book_has_higher_estimated_edge(self):
        rows=[candidate(),{**candidate('Grosvenor',2.2),'edge':.4},candidate('Pinnacle',2.3)]
        winner=prices.best_candidates(rows,NOW)
        self.assertEqual([r['bookmaker'] for r in winner],['Bet365'])
        self.assertEqual(len(json.loads(winner[0]['compared_prices'])),3)
        self.assertTrue(all('better_fresh_price_available' in r['blocked_reason'] for r in rows[1:]))

    def test_stale_better_quote_does_not_displace_fresh_book(self):
        rows=[{**candidate(),'price_captured_at_utc':'2026-10-28T18:34:59Z'},candidate('Pinnacle',2.3)]
        self.assertEqual(prices.best_candidates(rows,NOW)[0]['bookmaker'],'Pinnacle')
        self.assertIn('price_not_fresh_10m',rows[0]['blocked_reason'])

    def test_compare_before_eligibility_no_lower_price_cherry_pick(self):
        rows=[{**candidate(),'blocked_reason':'model_market_gap'},candidate('Pinnacle',2.3)]
        self.assertEqual(prices.best_candidates(rows,NOW),[])

    def test_different_line_or_kickoff_never_compared(self):
        rows=[candidate(),{**candidate('Pinnacle',2.2),'pick_id':'corners_v3|f1|over|9.5'},
              {**candidate('Grosvenor',2.1),'kickoff_utc':'2026-10-28T20:00:00Z'}]
        self.assertEqual(len(prices.best_candidates(rows,NOW)),3)

    def test_corners_keeps_each_book_pair_and_actual_price(self):
        base=dict(kickoff_at='2026-10-28T19:45:00Z',captured_at='2026-10-28T18:44:00Z',
                  competition='Serie A',home_team='Genoa',away_team='Juventus',line='8.5',market='MATCH_CORNERS')
        rows=[dict(base,bookmaker=b,side=s,odds_decimal=o) for b,o in [('Bet365',2.5),('Grosvenor',2.2)] for s in ['over','under']]
        latest=prices.latest_corners(rows,NOW,shadow.PUB)
        self.assertEqual(len(latest),4)
        pairs=shadow.paired_rows(latest,('league_slug','home_team','away_team','kickoff','line_label','bookmaker'))
        self.assertEqual(len(pairs),2)
        self.assertTrue(all(p['over']['bookmaker']==p['under']['bookmaker'] for p in pairs))

    def test_frozen_ledger_and_book_independent_notifications(self):
        original=candidate('Grosvenor',2.2)
        new=candidate()
        self.assertEqual(shadow.merge_shadow_ledger([original],[new]),[original])
        rows=prices.best_candidates([new,candidate('Grosvenor',2.2)],NOW)
        outgoing=digest.count_candidates(rows,'2026-10-28','corners_v3',now=NOW,tracked_rows=[original])
        self.assertEqual(len(outgoing),1)
        self.assertEqual(outgoing[0]['odds'],2.5)
        self.assertEqual(outgoing[0]['original']['book_odds'],2.2)
        groups={'CORNERS V3':outgoing}
        for status in ['sent','sending','uncertain']:
            self.assertEqual(digest.unseen_candidates(groups,{'sent':{original['pick_id']:{'status':status}}})['CORNERS V3'],[])
        changed={**new,'pick_id':'different-line'}
        self.assertEqual(digest.count_candidates([changed],'2026-10-28','corners_v3',now=NOW,tracked_rows=[original]),[])
        self.assertEqual(digest.count_candidates([new],'2026-10-28','corners_v3',now=NOW.replace(hour=20),tracked_rows=[original]),[])

    def test_roi_uses_actual_book_price_not_pinnacle_benchmark_and_keeps_history(self):
        pick={**candidate(), 'published_at_utc':'2026-10-28T18:45:00Z','league':'serie-a',
              'home_team':'Genoa','away_team':'Juventus','line':'8.5','side':'over'}
        index=clv.build_pinnacle_index([dict(home_team='Genoa',away_team='Juventus',match_date='2026-10-28',
            kickoff_iso=pick['kickoff_utc'],line='8.5',side='over',odds_decimal='2.0',captured_at='2026-10-28T18:44:00Z')])
        record=clv.build_pick_row(pick,index,allowed_leagues={'serie-a'},allow_canonical_only=True,config_valid=True,config_error='')
        self.assertEqual(record['bookmaker'],'Bet365')
        self.assertEqual(record['book_price_at_publication'],2.5)
        self.assertEqual(record['pinnacle_price_at_publication'],2.0)
        rows=[dict(record,result='pending'),dict(record,pick_id='loss',result='pending')]
        previous=dict(record,pick_id='old',result='won',pnl_units=1.2);before=copy.deepcopy(previous)
        rows.append(previous)
        with patch.object(settlement,'result_for_fixture',side_effect=[{'total_corners':10},{'total_corners':7}]):
            self.assertEqual(settlement.settle_corners(rows,{}),2)
        self.assertEqual([r['pnl_units'] for r in rows[:2]],[1.5,-1])
        self.assertEqual(sum(r['pnl_units'] for r in rows[:2])/2*100,25)
        self.assertEqual(previous,before)
        push=dict(record,result='pending',line='9')
        with patch.object(settlement,'result_for_fixture',return_value={'total_corners':9}):settlement.settle_corners([push],{})
        self.assertEqual(push['pnl_units'],0)

if __name__=='__main__':unittest.main()
