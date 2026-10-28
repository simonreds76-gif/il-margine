import copy
import json
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import headed_goal_quotes as q
import football_grosvenor as g
from aerial_market_capture import quoted_markets


class HeadedGoalQuotesTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((Path(__file__).parent/'fixtures/grosvenor-headed-goals.json').read_text(encoding='utf-8'))
        self.at = self.raw['captured_at']
        self.now = q.utc(self.at)
        self.target = dict(id=71945352, home='AC Milan', away='Bologna',
                           date='2026-10-28T17:30:00Z', league={'slug':'italy-serie-a'})

    def capture(self, raw=None, at=None):
        return dict(raw=raw or self.raw, target=self.target, captured_at=at or self.at)

    def test_real_eighteen_named_contracts_with_unverified_rules(self):
        rows, issues = q.extract(self.raw, self.target, self.at)
        self.assertEqual(issues, [])
        self.assertEqual(len(rows), 18)
        prices = {r['player']:r['odds'] for r in rows}
        self.assertEqual(prices['Strahinja Pavlovic'], 11)
        self.assertEqual(prices['Fikayo Tomori'], 14)
        self.assertTrue(all(r['settlement_rules']=='unverified' and r['raw_offer'] and r['source_participant_id'] for r in rows))

    def test_same_generic_type_is_not_the_same_contract(self):
        raw=copy.deepcopy(self.raw)
        for o in raw['betOffers']:
            o['criterion'].update(id=222, englishLabel='Player Shots on Target')
        self.assertEqual(q.extract(raw,self.target,self.at), ([],[]))

    def test_contract_drift_and_wrong_scope_are_rejected_with_evidence(self):
        for change in ('criterion','label','half','type','line','no','offerid','future','odds'):
            raw=copy.deepcopy(self.raw);raw['betOffers']=raw['betOffers'][:1]
            o=raw['betOffers'][0];out=o['outcomes'][0]
            if change=='criterion':o['criterion']['id']=999
            if change=='label':o['criterion']['englishLabel']='To score'
            if change=='half':o['criterion']['lifetime']='FIRST_HALF'
            if change=='type':o['betOfferType']['id']=6
            if change=='line':out['line']=2000
            if change=='no':out['type']='OT_NO'
            if change=='offerid':out['betOfferId']=7
            if change=='future':out['changedDate']='2027-01-01T00:00:00Z'
            if change=='odds':out['odds']=14.0
            rows,issues=q.extract(raw,self.target,self.at)
            self.assertTrue(issues,change)
            self.assertEqual(rows[0]['status'],'REJECTED',change)
            self.assertIsNone(rows[0]['odds'],change)

    def test_live_wrong_fixture_and_incomplete_payload_do_not_clear_state(self):
        for change in ('live','kickoff','teams','after','missing'):
            raw=copy.deepcopy(self.raw);at=self.at
            if change=='live':raw['events'][0]['state']='STARTED'
            if change=='kickoff':raw['events'][0]['start']='2026-10-28T18:30:00Z'
            if change=='teams':raw['events'][0]['homeName']='Bologna'
            if change=='after':at='2026-10-28T17:31:00Z'
            if change=='missing':raw.pop('betOffers')
            self.assertIsNone(q.extract(raw,self.target,at)[0],change)

    def test_price_status_history_dedup_withdrawal_and_expiry(self):
        with tempfile.TemporaryDirectory() as directory:
            d=Path(directory);path=d/'headed-goal-quotes.json'
            first=q.retain(d,[self.capture()],now=self.now)
            self.assertEqual(first['current_quotes'],18)
            self.assertEqual(first['price_or_status_changes'],18)
            before=path.read_bytes()
            self.assertEqual(q.retain(d,[self.capture()],now=self.now)['price_or_status_changes'],0)
            self.assertEqual(path.read_bytes(),before)
            later=self.now+timedelta(minutes=1)
            self.assertEqual(q.retain(d,[self.capture(at=later.isoformat())],now=later)['price_or_status_changes'],0)
            raw=copy.deepcopy(self.raw);raw['betOffers'][0]['outcomes'][0]['odds']+=1000
            later+=timedelta(minutes=1)
            self.assertEqual(q.retain(d,[self.capture(raw,later.isoformat())],now=later)['price_or_status_changes'],1)
            for status in ('SUSPENDED','OPEN'):
                later+=timedelta(minutes=1);raw['betOffers'][0]['outcomes'][0]['status']=status
                r=q.retain(d,[self.capture(raw,later.isoformat())],now=later)
                self.assertEqual(r['price_or_status_changes'],1)
                self.assertEqual(r['current_quotes'],17 if status=='SUSPENDED' else 18)
            last=q.read(path,{})
            raw['betOffers']=[];later+=timedelta(minutes=1)
            r=q.retain(d,[self.capture(raw,later.isoformat())],now=later)
            self.assertEqual(r['current_quotes'],0);self.assertEqual(r['price_or_status_changes'],0)
            state=q.read(path,{})
            self.assertTrue(all(v['status']=='NOT_OBSERVED' for v in state['quotes'].values()))
            self.assertEqual([v['last_seen_at'] for v in state['quotes'].values()],[v['last_seen_at'] for v in last['quotes'].values()])
            self.assertEqual(len(next((d/'headed-goal-quote-history').glob('*.jsonl')).read_text(encoding='utf-8').splitlines()),21)
            self.assertEqual(q.current_quotes(last,later+timedelta(hours=3)),[])

    def test_recreated_offer_ids_remain_separate_and_duplicate_ids_rejected(self):
        raw=copy.deepcopy(self.raw);raw['betOffers']=raw['betOffers'][:1]
        with tempfile.TemporaryDirectory() as d:
            q.retain(d,[self.capture(raw)],now=self.now)
            raw['betOffers'][0]['id']=777
            raw['betOffers'][0]['outcomes'][0]['betOfferId']=777
            later=self.now+timedelta(minutes=1)
            r=q.retain(d,[self.capture(raw,later.isoformat())],now=later)
            self.assertEqual(r['price_or_status_changes'],1)
            self.assertEqual(len(q.read(Path(d)/'headed-goal-quotes.json',{})['quotes']),2)
        raw['betOffers']*=2
        self.assertIsNone(q.extract(raw,self.target,self.at)[0])

    def test_exact_player_mapping_and_conflict_no_surname_guess(self):
        f=dict(kickoff=self.target['date'],state='expected',observed_at=self.at,teams=[
            dict(id=1,name='AC Milan',players=[dict(id=8,name='Strahinja Pavlović')]),
            dict(id=2,name='Bologna',players=[])])
        aerial={'fixtures':[f]};registry={}
        m=q.player_mapping(self.target,'Strahinja Pavlovic','123',aerial,registry)
        self.assertEqual((m['mapping_status'],m['player_id'],m['team_id']),('matched','8','1'))
        self.assertEqual(q.player_mapping(self.target,'Pavlovic','123',aerial,registry)['mapping_status'],'unmatched')
        f['teams'][1]['players']=[dict(id=9,name='Strahinja Pavlovic')]
        self.assertEqual(q.player_mapping(self.target,'Strahinja Pavlovic','123',aerial,registry)['mapping_status'],'ambiguous_player')
        f['teams'][1]['players']=[];f['teams'][0]['players'][0]['id']=20
        self.assertEqual(q.player_mapping(self.target,'Strahinja Pavlovic','123',aerial,registry)['mapping_status'],'identity_conflict')
        f['teams'][0]['players'][0]['id']=8
        self.assertEqual(q.player_mapping(self.target,'Strahinja Pavlovic','123',aerial,registry)['mapping_status'],'identity_conflict')

    def test_other_market_outputs_and_skyline_are_unchanged(self):
        base=json.loads((Path(__file__).parent/'fixtures/grosvenor-football.json').read_text(encoding='utf-8'))
        before=g.normalize(base,self.target,self.at)
        base['betOffers']+=self.raw['betOffers']
        self.assertEqual(g.normalize(base,self.target,self.at),before)
        f={'kickoff':self.target['date'],'teams':[{'id':1,'name':'AC Milan','players':[{'name':'Fikayo Tomori'}]}, {'id':2,'name':'Bologna','players':[]}]}
        candidate={'player':'Fikayo Tomori','team_id':1,'markets_to_check':['1+ headed shot on target']}
        snapshot={'events':[{'bookmaker':'Grosvenor','captured_at':self.at,'kickoff':self.target['date'],'home':'AC Milan','away':'Bologna','markets':[{'name':'Player Headed Goal','odds':[{'label':'Fikayo Tomori (1)','over':14,'hdp':0.5}]}]}]}
        self.assertEqual(quoted_markets(f,candidate,snapshot,self.now),[])

    def test_capture_integration_adds_no_requests_and_preserves_other_outputs(self):
        raw=copy.deepcopy(self.raw)
        base=json.loads((Path(__file__).parent/'fixtures/grosvenor-football.json').read_text(encoding='utf-8'))
        raw['betOffers']+=base['betOffers']
        class Response:
            def __init__(self,data):self.data=data
            def raise_for_status(self):pass
            def json(self):return self.data
        calls=[]
        def get(url,**kwargs):
            calls.append(url)
            return Response({'events':[{'event':raw['events'][0]}]} if 'listView' in url else raw)
        g._catalog={};g._started=None;g._attempted.clear()
        with tempfile.TemporaryDirectory() as d:
            out,health=g.capture_and_merge([], [self.target],now=self.now,cache_path=Path(d)/'raw.gz',get=get,force=True)
            self.assertEqual(len(calls),2)
            self.assertEqual(health['headed_goal_research']['current_quotes'],18)
            self.assertEqual(out,[g.normalize(base,self.target,self.at)])
            data=q.read(Path(d)/'headed-goal-quotes.json',{})
            self.assertEqual(len(data['quotes']),18)
            later=self.now+timedelta(minutes=1)
            out,health=g.capture_and_merge([], [self.target],now=later,cache_path=Path(d)/'raw.gz',get=get,force=True)
            self.assertEqual(len(calls),2)
            self.assertEqual(health['headed_goal_research']['price_or_status_changes'],0)
            self.assertEqual(q.read(Path(d)/'headed-goal-quotes.json',{}),data)

if __name__=='__main__':unittest.main()
