import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import moviodds_prices as m
from aerial_market_capture import retain_headed_markets, quoted_markets


class HeadedPrices(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((Path(__file__).parent/'fixtures/moviodds-headed.json').read_text())
        self.now = datetime(2026,10,28,18,30,4,tzinfo=timezone.utc)
        self.target = {'id':71945354,'home':'Monza','away':'Napoli','date':'2026-10-28T19:45:00Z',
                       'league':{'slug':'italy-serie-a'}}
        self.fixture = {'kickoff':self.target['date'],'teams':[
            {'id':'1','name':'Monza','players':[{'name':'Dany Mota'}]},
            {'id':'2','name':'Napoli','players':[{'name':'Scott McTominay'}]}]}
        self.candidate={'team_id':'1','player':'Dany Mota','markets_to_check':['1+ headed shot on target']}

    def norm(self, raw=None):
        return m.normalize(raw or self.raw,'soccer',self.now,targets=[self.target])[0]

    def snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'prices.json'
            retain_headed_markets(path,self.norm(),{},self.now.isoformat())
            return json.loads(path.read_text())

    def test_verified_real_quotes_reach_existing_skyline_parser(self):
        events=self.norm()
        self.assertEqual(len(events),1)
        market=events[0]['bookmakers']['Bet365'][0]
        self.assertEqual(market['name'],'Player Headed Shots on Target')
        self.assertEqual(len(market['odds']),72)
        snapshot=self.snapshot()
        quote=quoted_markets(self.fixture,self.candidate,snapshot,self.now)[0]
        self.assertEqual(quote['odds'],5.5)
        self.assertEqual(quote['captured_at'],'2026-10-28T18:28:02.108753958Z')
        self.assertEqual(quote['source'],'moviodds_bet365')
        self.assertEqual(quote['raw_quote']['n2'],'Monza')
        self.assertEqual(quote['contract'],'bet365_named_nonstarter_void_v1')
        away={'team_id':'2','player':'Scott McTominay','markets_to_check':self.candidate['markets_to_check']}
        self.assertEqual(quoted_markets(self.fixture,away,snapshot,self.now)[0]['odds'],2.75)

    def test_missing_unknown_or_wrong_club_never_guesses_side(self):
        for club in [None,'Unknown']:
            data=copy.deepcopy(self.raw)
            for q in data['matches'][0]['quotes']:q['n2']=club
            self.assertEqual(self.norm(data),[])
        snapshot=self.snapshot()
        self.candidate['team_id']='2'
        self.fixture['teams'][1]['players'].append({'name':'Dany Mota'})
        self.assertEqual(quoted_markets(self.fixture,self.candidate,snapshot,self.now),[])

    def test_stale_market_rejected_despite_fresh_fixture(self):
        for change in [{'stale':True},{'suspended':True},{'polled_at':'2026-10-28T12:40:00Z'}]:
            data=copy.deepcopy(self.raw)
            data['matches'][0]['polled_at']=self.now.isoformat()
            data['matches'][0]['group_status']['177727'].update(change)
            self.assertEqual(self.norm(data),[])

    def test_retention_or_reloading_cannot_rejuvenate_market(self):
        snapshot=self.snapshot();later=self.now+timedelta(minutes=11)
        snapshot['events'][0]['captured_at']=later.isoformat()
        self.assertEqual(quoted_markets(self.fixture,self.candidate,snapshot,later),[])
        for flag in ['stale','removed','suspended']:
            bad=copy.deepcopy(snapshot)
            bad['events'][0]['markets'][0]['raw_group_status'][flag]=True
            self.assertEqual(quoted_markets(self.fixture,self.candidate,bad,self.now),[])

    def test_different_milestone_market_or_conflicting_duplicate_rejected(self):
        data=copy.deepcopy(self.raw);f=data['matches'][0]
        q=next(q for q in f['quotes'] if q.get('line')=='Dany Mota' and q.get('side')=='1+')
        for change in [{'market_id':'50920'},{'side':'Over'},{'handicap':'2.5'},{'suspended':True}]:
            f['quotes']=[{**q,**change}]
            self.assertEqual(self.norm(data),[])
        f['quotes']=[q,{**q,'odds_dec':6,'odds_frac':'5/1'}]
        self.assertEqual(self.norm(data),[])

    def test_new_source_preserves_named_starter_settlement_convention(self):
        from skyline_paper import resolve
        record={'fixture_id':'1','kickoff':'2026-10-27T19:45:00Z','player_id':'10','team_id':'1',
                'quote':{'bookmaker':'Bet365','contract':'bet365_named_nonstarter_void_v1'}}
        player={'id':'10','team_id':'1','starter':True,'minutes':80,'headed_shots':2,'headed_sot':1}
        match={'date':record['kickoff'],'players':[player],'source_sha256':'test'}
        self.assertEqual(resolve(record,{'1':match},self.now)['status'],'win')
        player['headed_sot']=0
        self.assertEqual(resolve(record,{'1':match},self.now)['status'],'loss')
        player['starter']=False
        self.assertEqual(resolve(record,{'1':match},self.now)['status'],'void')

    def test_fresh_direct_quote_wins_without_duplicate_legacy_quote(self):
        snapshot=self.snapshot();old=copy.deepcopy(snapshot)
        old['events'][0]['markets'][0]['odds'][0]['over']=99
        old['moviodds']=snapshot
        quotes=quoted_markets(self.fixture,self.candidate,old,self.now)
        self.assertEqual(len(quotes),1)
        self.assertEqual(quotes[0]['odds'],5.5)

    def test_refresh_uses_existing_lineup_cycle_and_no_request_without_fixture(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(m,'capture') as capture:
            result=m.refresh_headed(Path(directory),{'fixtures':[]},self.now)
            self.assertEqual(result['requests'],0);capture.assert_not_called()
            capture.return_value=(self.norm(),{'status':'OK','requests':1,'errors':[]})
            fixture={**self.fixture,'id':123,'competition':'Serie A','state':'confirmed'}
            result=m.refresh_headed(Path(directory),{'fixtures':[fixture]},self.now)
            self.assertEqual(result['headed_quotes'],72)
            self.assertEqual(capture.call_count,1)
            self.assertEqual(capture.call_args.kwargs['targets'][0]['id'],'aerial:123')
            snapshot=json.loads((Path(directory)/'data/aerial/moviodds/prices.json').read_text())
            self.assertEqual(quoted_markets(self.fixture,self.candidate,{'moviodds':snapshot},self.now)[0]['odds'],5.5)

    def test_alerts_reject_aged_direct_quote_and_keep_deduplication(self):
        from test_skyline_alerts import fixture,NOW
        from skyline_alerts import eligible
        record,state=fixture();record['quote']['source']='moviodds_bet365'
        self.assertTrue(eligible(record,state,NOW))
        self.assertFalse(eligible(record,state,NOW+timedelta(minutes=11)))
        state['alerts']={record['key']:{'status':'sent'}}
        self.assertFalse(eligible(record,state,NOW))


if __name__=='__main__': unittest.main()
