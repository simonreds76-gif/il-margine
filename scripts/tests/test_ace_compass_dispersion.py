"""Regression checks for the forward Ace Compass comparison. No external services."""
import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import ace_compass_tail as tail

class DispersionTests(unittest.TestCase):
    def test_prices_and_passes(self):
        rule=dict(a=-1.4238839006256345,b=-.5693712909711733,min_alpha=.005,max_alpha=2,minimum_ev=.08)
        parent=dict(candidate=dict(mean=10,p_win=.6),control=dict(mean=8,p_win=.4))
        arms=tail.forecasts(parent,9.5,2,rule)
        self.assertEqual(arms['adjusted']['mean'],10)
        self.assertTrue(arms['candidate']['selected'])
        self.assertFalse(arms['control']['selected'])
        rows=[dict(id=i,fixture_key='fixture',row=dict(line=9.5,over_odds=2,match_start_utc='2026-11-18T13:00:00Z'),**arms) for i in ['won','lost','void','future']]
        sample=tail.stats(rows,{'won':dict(status='settled',actual=10),'lost':dict(status='settled',actual=9),
                                'void':dict(status='void',actual=None)})
        a,b=sample['arms']['candidate'],sample['arms']['control']
        self.assertEqual((a['roi_pct'],a['stake_units'],a['pending'],a['void']),(0,2,1,1))
        self.assertEqual((b['passes'],b['roi_pct']),(4,None))
        self.assertAlmostEqual(b['brier'],.26)
        self.assertEqual((sample['graded'],sample['settled_fixtures']),(2,1))

    def test_literal_bet365_line_price_and_named_participant(self):
        quote=dict(line='10+',side='Player A',fixture_id='721',group_id='130440',market_id='130440',
                   group_name='Ace Totals',sel_id='987',odds_frac='5/2',odds_dec=3.5,ts='2026-11-01T10:00:00Z')
        market=dict(name='Player Aces',source='moviodds_bet365',source_event_id='721',source_group_id='130440',
                    raw_group_status=dict(polled_at='2026-11-01T10:01:00Z'),odds=[dict(label='Player A',hdp=9.5,over=3.5,raw_quote=quote)])
        row=dict(event_id='bet365:721',bookmaker='Bet365',player='Player A',line=9.5,over_odds=3.5,raw_market_name='Player Aces',
                 capture_ts='2026-11-01T10:02:00Z',match_start_utc='2026-11-01T14:00:00Z')
        def check():return tail.validate_raw(dict(row,raw_market_json=json.dumps(market)))
        self.assertEqual(check()['literal'],'10+')
        for k,bad in [('line','9+'),('side','Player B'),('odds_frac','5/1'),('suspended',True)]:
            with self.subTest(k=k):
                old=quote.copy()
                quote[k]=bad
                with self.assertRaises(ValueError):check()
                quote.clear()
                quote.update(old)

if __name__=='__main__':unittest.main()
