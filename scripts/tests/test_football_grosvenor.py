import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import football_grosvenor as g

def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1]/(name+'.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

class GrosvenorFootballTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((Path(__file__).parent/'fixtures/grosvenor-football.json').read_text(encoding='utf-8'))
        self.target = dict(id=123, home='AC Milan', away='Bologna', date='2026-10-28T17:30:00Z', league={'slug':'italy-serie-a','name':'Italy - Serie A'})
        self.now = datetime(2026,10,28,12,tzinfo=timezone.utc)
        g._catalog = {}; g._started = None; g._attempted.clear()

    def normalized(self):
        return g.normalize(self.raw,self.target,self.now.isoformat())

    def test_real_contracts_and_thousandths(self):
        markets={m['name']:m for m in self.normalized()['bookmakers']['Grosvenor']}
        self.assertEqual(set(markets),{'ML','Anytime Goalscorer','Anytime Assist','Goalkeeper Saves Away','Total Shots Away','Corners Totals'})
        self.assertEqual(markets['ML']['odds'][0]['home'],1.65)
        self.assertEqual(markets['Total Shots Away']['odds'],[{'hdp':9.5,'over':1.72}])
        self.assertTrue(all(m['source_offer_id'] and m['raw_offer'] and m['source_url'] for m in markets.values()))

    def test_ambiguous_inverted_changed_time_and_other_league_rejected(self):
        for change in ({'home':'Bologna','away':'AC Milan'},{'date':'2026-10-28T18:30:00Z'}, {'league':{'slug':'italy-serie-b'}},{'home':'AC Milan U21'}):
            self.assertIsNone(g.normalize(self.raw,{**self.target,**change},self.now.isoformat()))
        self.raw['events'] *= 2
        self.assertIsNone(self.normalized())

    def test_inplay_suspended_partial_three_way_and_halves_excluded(self):
        for field,value in [('state','STARTED'),('sport','TENNIS')]:
            raw=copy.deepcopy(self.raw); raw['events'][0][field]=value
            self.assertIsNone(g.normalize(raw,self.target,self.now.isoformat()))
        for change in ('suspended','half','missing','decimal'):
            raw=copy.deepcopy(self.raw); offer=next(o for o in raw['betOffers'] if o['criterion']['englishLabel']=='Full Time')
            if change=='suspended':offer['outcomes'][0]['status']='SUSPENDED'
            if change=='half':offer['criterion']['lifetime']='FIRST_HALF'
            if change=='missing':offer['outcomes'].pop()
            if change=='decimal':offer['outcomes'][0]['odds']=1.65
            self.assertNotIn('ML',[m['name'] for m in g.normalize(raw,self.target,self.now.isoformat())['bookmakers']['Grosvenor']])

    def test_second_goal_is_not_anytime_and_combined_is_not_assist(self):
        for o in self.raw['betOffers']:
            if o['criterion']['englishLabel']=='To Score':o['outcomes'][0]['line']=2000
            if o['criterion']['englishLabel'].startswith('To give an assist'):o['criterion']['englishLabel']='To score or give an assist (Settled using Opta data)'
        names={m['name'] for m in self.normalized()['bookmakers']['Grosvenor']}
        self.assertNotIn('Anytime Goalscorer',names);self.assertNotIn('Anytime Assist',names)

    def test_existing_collectors_accept_only_expected_markets(self):
        event=self.normalized();capt=load('goalkeeper-saves-capture')
        rows=capt.extract_rows([event],{},bookmaker_name='Grosvenor',captured_at=self.now.isoformat(),capture_mode='publication')
        self.assertTrue(rows);self.assertEqual({r['player'] for r in rows},{'Away goalkeeper'})
        self.assertTrue(all(':team_goalkeeper_away:' in r['source'] for r in rows))
        shots=load('team-shots-scrape-odds')._extract_odds_api_rows([event],{'competition':'Italy - Serie A'},self.now.isoformat())
        self.assertEqual(len(shots),1);self.assertEqual(shots[0]['team'],'Bologna');self.assertEqual(shots[0]['source'],'grosvenor_direct')
        scorers=load('odds-api-scrape-goalscorer');assists=load('odds-api-scrape-assists')
        self.assertEqual(sum(len(scorers._extract_atgs_rows_for_market('Grosvenor',event,m,'Serie A')) for m in event['bookmakers']['Grosvenor']),1)
        self.assertEqual(sum(len(assists._extract_assist_rows_for_market('Grosvenor',event,m,'Serie A')) for m in event['bookmakers']['Grosvenor']),1)
        for label in ('Player To Score Header','Anytime Goalscorer or Assist','First Half Anytime Goalscorer'):
            self.assertFalse(scorers._market_is_atgs(label))

    def test_failure_preserves_other_book_and_does_not_send_key(self):
        payload=[{**self.target,'bookmakers':{'Paddy Power':[{'name':'ML'}]}}]
        calls=[]
        def bad(url,**kwargs):
            calls.append((url,kwargs));raise g.requests.ConnectionError('unavailable')
        with tempfile.TemporaryDirectory() as d:
            out,report=g.capture_and_merge(payload,[self.target],now=self.now,cache_path=Path(d)/'cache.gz',get=bad,force=True)
        self.assertEqual(out,payload);self.assertEqual(report['requests'],1);self.assertTrue(report['errors'])
        self.assertNotIn('apiKey',calls[0][1]['params'])

    def test_cache_preserves_capture_time_and_same_event_id(self):
        class Response:
            def __init__(self,data):self.data=data
            def raise_for_status(self):pass
            def json(self):return self.data
        def get(url,**kwargs):
            return Response({'events':[{'event':self.raw['events'][0]}]} if 'listView' in url else self.raw)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'cache.gz'
            out,report=g.capture_and_merge([], [self.target],now=self.now,cache_path=path,get=get,force=True)
            self.assertEqual(report['requests'],2);self.assertEqual(out[0]['id'],123)
            later=self.now+timedelta(minutes=1)
            out,report=g.capture_and_merge([], [self.target],now=later,cache_path=path,get=get,force=True)
            self.assertEqual(report['requests'],0)
            self.assertEqual(out[0]['bookmakers']['Grosvenor'][0]['captured_at'],self.now.isoformat())
            out,report=g.capture_and_merge([], [self.target],now=self.now+timedelta(hours=6),cache_path=path,get=get,force=True)
            self.assertEqual(out,[])

    def test_new_book_does_not_duplicate_previous_gk_fixture(self):
        shadow=load('goalkeeper-saves-shadow')
        old=dict(event_id='123',match_date='2026-10-28',home_team='AC Milan',away_team='Bologna',goalkeeper='Away goalkeeper',bookmaker='Kambi',line='3.5',side='over',odds_decimal='2.0',candidate_status='eligible_shadow',strongest_for_fixture='yes',captured_at=self.now.isoformat(),kickoff_at=self.target['date'],contract_scope='team_goalkeeper_away',identity_basis='bookmaker_team_side',blockers='')
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'ledger.csv'
            self.assertEqual(shadow.append_signals(path,[old],self.now.isoformat())[0],1)
            before=path.read_bytes()
            self.assertEqual(shadow.append_signals(path,[dict(old,bookmaker='Grosvenor',odds_decimal='2.1')],self.now.isoformat())[0],0)
            self.assertEqual(path.read_bytes(),before)

if __name__=='__main__':unittest.main()
