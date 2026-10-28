import copy
import importlib.util
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import moviodds_prices as m


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1]/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MoviOddsTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((Path(__file__).parent/'fixtures/moviodds-prices.json').read_text())
        self.now = datetime(2026, 10, 28, 17, 56, 20, tzinfo=timezone.utc)
        self.target = {'id': 123, 'home': 'Genoa', 'away': 'Juventus',
                       'date': '2026-10-28T19:45:00Z', 'league': {'slug': 'italy-serie-a'}}

    def norm(self, sport='soccer'):
        return m.normalize(self.raw[sport], sport, self.now, targets=[self.target])[0]

    def test_real_gk_named_lines_and_existing_parser(self):
        events = self.norm()
        self.assertEqual(events[0]['id'], 123)
        rows = load('goalkeeper-saves-capture').extract_rows(events, {}, bookmaker_name='Bet365', captured_at='wrong', capture_mode='publication')
        self.assertEqual(len(rows), 11)
        self.assertEqual({r['player'] for r in rows}, {'Justin Bijlow', 'Guglielmo Vicario'})
        self.assertTrue(all(r['source'].startswith('moviodds_bet365:') for r in rows))
        self.assertTrue(all(r['side']=='over' and r['captured_at']!='wrong' for r in rows))

    def test_tennis_exact_named_ladders_and_no_match_total(self):
        events = self.norm('tennis')
        parser = load('tennis-props-scrape-bet365')
        rows = [r for e in events for market in e['bookmakers']['Bet365'] for r in parser.extract_rows(e, 'Bet365', market, captured_at='wrong')]
        self.assertEqual(len(rows), 28)
        self.assertEqual({r['market'] for r in rows}, {'aces','double_faults'})
        self.assertTrue(all(r['under_odds']=='' and r['raw_market_json'] and r['capture_ts']!='wrong' for r in rows))
        self.assertEqual(next(r for r in rows if r['player']=='Ben Shelton' and r['market']=='aces' and r['line']=='9.5')['over_odds'], '1.0400')

    def test_future_start_and_exact_oriented_competition_identity(self):
        for change in ({'home':'Juventus','away':'Genoa'},{'date':'2026-10-28T19:46:00Z'}, {'league':{'slug':'italy-cup'}}):
            with self.subTest(change=change):
                self.assertFalse(m.normalize(self.raw['soccer'],'soccer',self.now,targets=[{**self.target,**change}])[0])
        self.assertFalse(m.normalize(self.raw['soccer'],'soccer',self.now,targets=[self.target,self.target])[0])
        for change in ({'in_play':True},{'kickoff_utc':self.now.isoformat()},{'suspended':True}):
            data=copy.deepcopy(self.raw['tennis']);data['matches'][0].update(change)
            self.assertFalse(m.normalize(data,'tennis',self.now)[0])

    def test_market_poll_not_fixture_poll_or_price_change(self):
        raw=self.raw['soccer'];fixture=raw['matches'][0]
        self.assertTrue(self.norm())  # prices last changed hours ago, market recently checked
        fixture['polled_at']=self.now.isoformat()
        fixture['group_status']['177703']['polled_at']='2026-10-28T17:00:00Z'
        self.assertFalse(self.norm())
        fixture['group_status']['177703']['polled_at']=self.now.isoformat()
        fixture['group_status']['177703']['stale']=True
        self.assertFalse(self.norm())

    def test_provider_wta_label_is_not_proof_of_main_tour_and_existing_id_wins(self):
        self.raw['tennis']['matches'][0]['league']='WTA Curitiba'
        self.assertFalse(self.norm('tennis'))
        self.raw['tennis']['matches'][0]['league']='ATP Basel'
        target={'id':789,'home':'Jerome Kym','away':'Ben Shelton','date':'2026-10-29T12:00:00Z','league':{'name':'ATP - Basel'}}
        events,_=m.normalize(self.raw['tennis'],'tennis',self.now,targets=[target])
        self.assertEqual(events[0]['id'],789)
        self.assertEqual(events[0]['home'],'Jerome Kym')

    def test_missing_poll_warmup_stale_server_fail_closed(self):
        self.raw['soccer']['matches'][0]['group_status']={}
        self.assertFalse(self.norm())
        for change in ({'warming':True},{'server_time':'2026-10-28T16:00:00Z'},{'server_time':None}):
            with self.assertRaises(ValueError):
                m.normalize({**self.raw['tennis'],**change},'tennis',self.now)

    def test_suspension_conflict_wrong_line_and_wrong_fixture(self):
        data=self.raw['soccer'];fixture=data['matches'][0]
        q=next(q for q in fixture['quotes'] if q['group_id']=='177703')
        for change in ({'suspended':True},{'fixture_id':'999'},{'market_id':'half'},{'handicap':'99.5'}, {'odds_dec':float('nan')},{'odds_frac':'999/1'}):
            test=copy.deepcopy(data);test['matches'][0]['quotes']=[{**q,**change}]
            self.assertFalse(m.normalize(test,'soccer',self.now,targets=[self.target])[0])
        test=copy.deepcopy(data);test['matches'][0]['quotes']=[q,{**q,'odds_dec':2.5,'odds_frac':'3/2'}]
        self.assertFalse(m.normalize(test,'soccer',self.now,targets=[self.target])[0])

    def test_headed_and_match_aces_cannot_enter_individual_markets(self):
        self.raw['soccer']['matches'][0]['quotes']=[q for q in self.raw['soccer']['matches'][0]['quotes'] if q['group_id']=='177727']
        self.assertFalse(self.norm())
        self.raw['tennis']['matches'][0]['quotes']=[q for q in self.raw['tennis']['matches'][0]['quotes'] if q.get('side')=='Match']
        self.assertFalse(self.norm('tennis'))

    def test_failure_preserves_other_prices_and_no_credentials(self):
        original=[{**self.target,'bookmakers':{'Grosvenor':[{'name':'ML'}]}}]
        calls=[]
        def fail(url, **kw):
            calls.append((url,kw));raise ValueError('bad source')
        result,receipt=m.merge_football(original,[self.target],force=True,get=fail)
        self.assertEqual(result,original);self.assertEqual(receipt['status'],'SOURCE_FAILED')
        self.assertEqual(len(calls),1);self.assertNotIn('apiKey',str(calls))

    def test_same_book_does_not_duplicate_and_other_book_is_unchanged(self):
        source=self.norm();original=copy.deepcopy(source)
        with patch.object(m,'capture',return_value=(source,{})):
            result,_=m.merge_football(original,[self.target])
        self.assertEqual(result,original)
        original=[{**self.target,'bookmakers':{'Grosvenor':[{'name':'ML','odds':[{'home':2,'draw':3,'away':4}]}]}}]
        with patch.object(m,'capture',return_value=(source,{})):
            result,_=m.merge_football(original,[self.target])
        self.assertNotIn('Bet365',original[0]['bookmakers'])
        self.assertEqual(result[0]['bookmakers']['Grosvenor'],original[0]['bookmakers']['Grosvenor'])
        row=load('goalkeeper-saves-capture').extract_rows(result,{},bookmaker_name='Bet365',captured_at='wrong',capture_mode='publication')[0]
        self.assertEqual(row['home_price'],'2.0000');self.assertIn('reference_1x2_grosvenor',row['source'])


if __name__ == '__main__':
    unittest.main()
