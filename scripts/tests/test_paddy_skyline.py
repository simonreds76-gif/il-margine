import copy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aerial_data import read, save
from aerial_market_capture import quoted_markets
from paddy_headed import normalize, quoted, matches, capture
from skyline_contracts import settle, best_quote, evidence
from skyline_paper import summarize, run
from skyline_alerts import message, eligible
from test_skyline import setup, NOW
from test_skyline_alerts import fixture as alert_fixture


def source(fixture):
    event = dict(eventId=5, eventTypeId=1, competitionId=10932509,
                 name='Home v Away', openDate=fixture['kickoff'])
    market = dict(marketId='1.2', eventId=5, eventTypeId=1, competitionId=10932509,
        marketType='PLAYER_TO_HAVE_1_OR_MORE_HEADED_SHOTS_ON_TARGET', marketStatus='OPEN',
        inPlay=False, marketTime=fixture['kickoff'], runners=[dict(selectionId=88,runnerName='Player 15',
        runnerStatus='ACTIVE',winRunnerOdds={'trueOdds':{'decimalOdds':{'decimalOdds':6.0}}})])
    return event, {'1.2':market}


@patch('paddy_headed.DIRECT_COLLECTION_ENABLED', True)
class PaddySkyline(unittest.TestCase):
    def test_exact_fixture_market_and_identity(self):
        with tempfile.TemporaryDirectory() as d:
            f,*_=setup(Path(d));e,ms=source(f)
            n=normalize(e,f,ms,NOW.isoformat(),'hash');q=n['quotes'][0]
            self.assertEqual((q['player_id'],q['team_id'],q['odds']),('15','1',6))
            self.assertEqual(q['contract'],'paddy_super_sub_v1')
            self.assertIsNone(q['source_price_changed_at'])
            c=dict(player='Player 15',team_id='1',markets_to_check=['1+ headed shot on target'])
            self.assertEqual(quoted(f,c,{'events':[n]},NOW),[q])
            for change in [{'competitionId':2134},{'name':'Away v Home'},{'eventTypeId':2},{'openDate':NOW.isoformat()}]:
                self.assertIsNone(normalize({**e,**change},f,ms,NOW.isoformat(),'hash'))
            for change in [{'inPlay':True},{'marketStatus':'SUSPENDED'},{'marketTime':NOW.isoformat()},
                           {'marketType':'PLAYER_TO_HAVE_1_OR_MORE_SHOTS_ON_TARGET'}]:
                bad={'1.2':{**ms['1.2'],**change}}
                self.assertEqual(normalize(e,f,bad,NOW.isoformat(),'hash')['quotes'],[])
            f['teams'][1]['players'].append({'id':'different','name':'Player 15'})
            n=normalize(e,f,ms,NOW.isoformat(),'hash')
            self.assertIsNone(n['quotes'][0]['player_id'])
            self.assertEqual(quoted(f,c,{'events':[n]},NOW),[])

    def test_best_price_immutable_record_no_duplicate_on_source_change(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);f,h,a,old=setup(root);e,ms=source(f)
            n=normalize(e,f,ms,NOW.isoformat(),'hash')
            save(root/'data/aerial/paddy/prices.json',{'events':[n]})
            r=run(root,NOW,True)
            self.assertEqual(r['forecasts'],1)
            self.assertEqual((r['ledger'][0]['odds'],r['ledger'][0]['bookmaker']),(6,'Paddy Power'))
            old['events'][0]['markets'][0]['odds'][0]['over']=8
            save(root/'data/goalkeeper-saves/aerial-headed-market-prices.json',old)
            r=run(root,NOW+timedelta(minutes=1),True)
            self.assertEqual(r['forecasts'],1)
            self.assertEqual(r['ledger'][0]['odds'],6)
            self.assertEqual(r['board'][0]['odds'],8)
            self.assertEqual(r['board'][0]['bookmaker'],'Bet365')

    def test_stale_ambiguous_and_goals_cannot_be_skyline_bets(self):
        with tempfile.TemporaryDirectory() as d:
            f,*_=setup(Path(d));e,ms=source(f);n=normalize(e,f,ms,NOW.isoformat(),'hash')
            c=dict(player='Player 15',team_id='1',markets_to_check=['1+ headed shot on target'])
            self.assertEqual(quoted(f,c,{'events':[n,n]},NOW),[])
            self.assertEqual(quoted(f,c,{'events':[n]},NOW+timedelta(hours=3)),[])
            n['quotes'].append(copy.deepcopy(n['quotes'][0]));n['quotes'][1]['odds']=7
            self.assertEqual(quoted(f,c,{'events':[n]},NOW),[])
            self.assertIsNone(best_quote([dict(market='headed goal',odds=50,captured_at=NOW.isoformat(),bookmaker='Paddy Power')]))

    def record_match(self):
        r={'player_id':'15','team_id':'1','quote':{'bookmaker':'Paddy Power','contract':'paddy_super_sub_v1'}}
        m={'players':[{'id':'15','team_id':'1','starter':True,'minutes':60,'headed_sot':0,'headed_shots':1},
                      {'id':'99','team_id':'1','starter':False,'minutes':30,'headed_sot':1,'headed_shots':1}],
           'settlement_evidence':{'complete':True,'roster':{},'substitutions':[
               {'player_out':'15','player_in':'99','team_id':'1','time':[60,0]}]}}
        return r,m

    def test_super_sub_win_is_named_player_loss_for_accuracy(self):
        r,m=self.record_match();o=settle(r,m,NOW)
        self.assertEqual((o['status'],o['model_status'],o['headed_sot']),('win','loss',0))
        r.update(key='r',fixture_id='f',kickoff=NOW.isoformat(),odds=6,
                 predictions={'baseline':.2},selections={'baseline':True})
        s=summarize([r],{'r':o},'baseline',NOW)
        self.assertEqual(s['profit'],5);self.assertAlmostEqual(s['brier'],.04)

    def test_missing_chain_unknown_statistics_and_other_team_held(self):
        r,m=self.record_match();m['settlement_evidence']['complete']=False
        self.assertIsNone(settle(r,m,NOW))
        m['players'][0]['headed_sot']=1
        self.assertEqual(settle(r,m,NOW)['status'],'win')
        r,m=self.record_match();m['players'][1]['headed_sot']=None
        self.assertIsNone(settle(r,m,NOW))
        r,m=self.record_match();m['settlement_evidence']['substitutions'][0]['team_id']='2'
        self.assertIsNone(settle(r,m,NOW))

    def test_substitutes_substitute_loss_and_nonparticipation(self):
        r,m=self.record_match();m['players'][1]['headed_sot']=0
        m['players'].append(dict(id='100',team_id='1',starter=False,minutes=10,headed_sot=1,headed_shots=1))
        m['settlement_evidence']['substitutions'].append(dict(player_out='99',player_in='100',team_id='1',time=[80,0]))
        self.assertEqual(settle(r,m,NOW)['substitution_chain'],['15','99','100'])
        m['players'][2]['headed_sot']=0
        self.assertEqual(settle(r,m,NOW)['status'],'loss')
        r['quote']['contract']='paddy_named_player_v1';m['players'][0]['starter']=False
        self.assertEqual(settle(r,m,NOW)['status'],'loss')
        self.assertIsNone(settle(r,m,NOW)['model_status'])
        m['players']=[];m['settlement_evidence']['roster']['15']={'team_id':'1','played':False}
        self.assertEqual(settle(r,m,NOW)['status'],'void')

    @patch.dict('os.environ', {'GITHUB_ACTIONS':'false'})
    def test_capture_error_keeps_old_timestamp_and_empty_success_clears(self):
        import requests
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);f,*_=setup(root)
            old={'generated_at':'2026-10-18T10:00:00Z','events':[{'old':True}]}
            save(root/'data/aerial/paddy/prices.json',old)
            get=Mock(side_effect=requests.HTTPError('403'))
            self.assertEqual(capture(root,{'fixtures':[f]},NOW,get=get)['status'],'FAILED')
            self.assertEqual(read(root/'data/aerial/paddy/prices.json'),old)
            get.assert_called_once()
            self.assertEqual(capture(root,{'fixtures':[]},NOW+timedelta(minutes=6),get=get)['status'],'NO_UPCOMING_SUPPORTED_FIXTURES')
            self.assertEqual(read(root/'data/aerial/paddy/prices.json')['events'],[])

    def test_paddy_alert_and_existing_receipt_dedup(self):
        r,s=alert_fixture();r['quote'].update(bookmaker='Paddy Power',contract='paddy_super_sub_v1')
        now=datetime.fromisoformat(r['captured_at'])
        self.assertTrue(eligible(r,s,now))
        text=message(r,s,now)
        self.assertIn('Paddy Power recorded odds',text)
        self.assertIn('named player only',text)
        self.assertNotIn('Check current Bet365',text)
        s['alerts']={r['key']:{'status':'sent','bookmaker':'Bet365'}}
        self.assertFalse(eligible(r,s,now))

    def test_substitution_evidence_requires_complete_exact_roster(self):
        row={'home_id':'1','away_id':'2'}
        page={'content':{'lineup':{
            'homeTeam':{'starters':[{'id':15}],'subs':[{'id':99,'performance':{'played':True}}]},
            'awayTeam':{'starters':[{'id':25}],'subs':[]}},
            'matchFacts':{'events':{'ongoing':False,'events':[
                {'type':'Substitution','isHome':True,'time':60,'swap':[{'id':99},{'id':15}]}]}}}}
        players=[{'id':'15','starter':True},{'id':'25','starter':True},{'id':'99','starter':False}]
        proof=evidence(page,row,players,True)
        self.assertTrue(proof['complete'])
        self.assertEqual(proof['substitutions'][0]['player_in'],'99')
        self.assertFalse(evidence(page,row,players,False)['complete'])
        page['content']['matchFacts']['events']['events']=[]
        self.assertFalse(evidence(page,row,players,True)['complete'])
        page['content']['matchFacts']['events']['ongoing']=True
        self.assertFalse(evidence(page,row,players,True)['complete'])


if __name__=='__main__':unittest.main()
