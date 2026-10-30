from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
import unittest,sys,importlib.util,tempfile,json,csv,hashlib,gzip,copy
W=Path(__file__).resolve().parents[2];R=W;sys.dont_write_bytecode=True
sys.path[:0]=[str(W/'scripts'),str(R/'scripts')]
import tennis_most_df as m
import moviodds_prices as feed
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
cap=load('capture_test',W/'scripts/tennis-most-aces-capture.py');common=cap.load_common()
def writecsv(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
class DfTests(unittest.TestCase):
    def test_distribution_sum_swap_and_zero(self):
        for a,b in [(0,0),(0,2),(1.7,3),(12,20),(100,100)]:
            p=m.probabilities(a,b,.1,.2);q=m.probabilities(b,a,.2,.1)
            self.assertAlmostEqual(sum(p),1,11)
            for x,y in zip(p,q[::-1]):self.assertAlmostEqual(x,y,11)
        self.assertEqual(m.probabilities(0,0,.1,.1),[0,1,0])
    def test_distribution_independent_reference(self):
        from scipy.stats import nbinom
        import numpy as np
        p=m.probabilities(1.719,2.1,.1,.1);a=nbinom.pmf(np.arange(500),10,10/(10+1.719));b=nbinom.pmf(np.arange(500),10,10/(10+2.1));joint=np.outer(a,b)
        expected=[np.tril(joint,-1).sum(),np.trace(joint),np.triu(joint,1).sum()]
        for x,y in zip(p,expected):self.assertAlmostEqual(x,y,10)
    def test_invalid_distribution_rejected(self):
        for mu in [-1,float('nan'),101]:
            with self.assertRaises(ValueError):m.probabilities(mu,2,.1,.1)
    def prices(self,now):
        raw=json.dumps({'name':'Most Double Faults','odds':[{'home':2.5,'draw':6,'away':2.0}]},separators=(',',':'))
        return dict(date=now.date().isoformat(),tour='ATP',tournament='Basel',player1='Player One',player2='Player Two',raw_market_name='Most Double Faults',capture_ts=(now-timedelta(minutes=1)).isoformat(),match_start_utc=(now+timedelta(hours=1)).isoformat(),player1_odds='2.5',draw_odds='6',player2_odds='2.0',bookmaker='Bet365',raw_market_json=raw,evidence_sha256=hashlib.sha256(raw.encode()).hexdigest())
    def pair(self,now):
        a=dict(date=now.date().isoformat(),generation_date=now.date().isoformat(),tour='ATP',tour_id='321',tournament='Basel',player='Player One',opponent='Player Two',player_id='11',opponent_id='22',round='QF',projected_dfs='2.4',df_confidence='MED',player_name_resolution='exact')
        b=dict(a,player='Player Two',opponent='Player One',player_id='22',opponent_id='11',projected_dfs='1.5');return a,b
    def priced(self,r,**changes):
        q=dict(r,**changes);raw=json.loads(q['raw_market_json'])
        raw['odds']=[dict(home=float(q['player1_odds']),draw=float(q['draw_odds']),away=float(q['player2_odds']))]
        q['raw_market_json']=json.dumps(raw,separators=(',',':'));q['evidence_sha256']=hashlib.sha256(q['raw_market_json'].encode()).hexdigest();return q
    def test_price_orientation_best_book_and_stale(self):
        now=datetime.now(timezone.utc);a,b=self.pair(now);r=self.prices(now);q=self.priced(r,bookmaker='Grosvenor',player1_odds='2.6')
        prices,reason=m.current_prices([r,q],a,b,now);self.assertIsNone(reason)
        best,selection=m.select(prices,[.6,.15,.25]);self.assertEqual(selection['bookmaker'],'Grosvenor');self.assertEqual(selection['odds'],2.6)
        p,reason=m.current_prices([r],b,a,now);self.assertEqual(p[0]['prices'],[2,6,2.5])
        self.assertFalse(m.current_prices([dict(r,capture_ts=(now-timedelta(hours=1)).isoformat())],a,b,now)[0])
    def test_conflicting_current_contract_and_wrong_market_rejected(self):
        now=datetime.now(timezone.utc);a,b=self.pair(now);r=self.prices(now)
        self.assertFalse(m.current_prices([r,self.priced(r,player1_odds='2.6')],a,b,now)[0])
        self.assertFalse(m.current_prices([dict(r,player1_odds='2.6')],a,b,now)[0])
        self.assertFalse(m.current_prices([dict(r,raw_market_name='Most Aces')],a,b,now)[0])
        self.assertFalse(m.current_prices([dict(r,evidence_sha256='bad')],a,b,now)[0])
    def test_append_only_capture_and_source_swap_dedup(self):
        now=datetime.now(timezone.utc);a,b=self.pair(now);q=self.prices(now)
        with tempfile.TemporaryDirectory(dir=W) as tmp:
            root=Path(tmp);folder=root/m.REL;folder.mkdir(parents=True);(folder/'registration.json').write_text('{}')
            writecsv(root/'data/tennis-props/player-props-board.csv',[a,b])
            writecsv(root/'data/oncourt/today_atp.csv',[dict(tour_id='321',player1_id='11',player2_id='22',date=a['date'],round_id='7',result='',complete='',live='')])
            writecsv(root/'data/tennis-props/inbox'/f'most-df-1x2-{a["date"]}.csv',[q])
            now=datetime.now(timezone.utc);h=m.capture(root,folder,{},now);self.assertEqual(h['added'],1)
            p=next((folder/'captures').glob('*.json'));before=p.read_bytes()
            writecsv(root/'data/tennis-props/inbox'/f'most-df-1x2-{a["date"]}.csv',[dict(q,bookmaker='Grosvenor',player1_odds='3')])
            self.assertEqual(m.capture(root,folder,{},now)['added'],0);self.assertEqual(p.read_bytes(),before)
    def test_settlement_exact_fixture_and_df_orientation(self):
        now=datetime.now(timezone.utc);r=dict(id='a',tour='ATP',tour_id='321',round_id='7',players=['11','22'],captured_at=(now-timedelta(days=1)).isoformat(),start=(now-timedelta(hours=2)).isoformat())
        g=dict(tour_id='321',round_id='7',winner_id='22',loser_id='11',date=now.date().isoformat(),result='6-4 6-2')
        s=dict(g,w_df='2',l_df='5');out={}
        def read(path):return [g] if path.name.startswith('games') else [s]
        with patch.object(m,'csvrows',side_effect=read):
            m.settle(Path('unused'),[r],out,now)
        self.assertEqual(out['a']['outcome'],0);self.assertEqual(out['a']['counts'],[5,2])
        for changed in [dict(g,round_id='6'),dict(g,result='6-4 1-0 RET')]:
            out={}
            with patch.object(m,'csvrows',side_effect=lambda p:[changed] if p.name.startswith('games') else [s]):
                m.settle(Path('unused'),[r],out,now)
            self.assertEqual(out,{})
    @unittest.skipUnless((W.parent/'tennis-markets-20261030/evidence/moviodds-tennis.json.gz').exists(), 'External frozen real-market replay is verified separately')
    def test_saved_real_markets_separated(self):
        path=W.parent/'tennis-markets-20261030/evidence/moviodds-tennis.json.gz';data=json.load(gzip.open(path,'rt'));now=feed.utc(data['server_time'])
        events,receipt=feed.normalize(data,'tennis',now)
        aces=cap.extract_rows(events,now.isoformat(),common);dfs=cap.extract_rows(events,now.isoformat(),common,market_kind='dfs')
        self.assertGreater(len(dfs),0);self.assertTrue(all(r['raw_market_name']=='Most Double Faults' for r in dfs))
        self.assertTrue(all(r['raw_market_name']=='Most Aces' for r in aces))
        for r in dfs:
            a=dict(date=r['date'],tour=r['tour'],tournament=r['tournament'],player=r['player1']);b=dict(a,player=r['player2'])
            parsed,reason=m.current_prices([r],a,b,now)
            self.assertIsNone(reason,(r['player1'],reason))
            self.assertEqual(len(parsed),1)
        old=load('old_feed',W/'originals/moviodds_prices.py');old_events,_=old.normalize(data,'tennis',now)
        old_aces=cap.extract_rows(old_events,now.isoformat(),common)
        fields=['event_id','player1','player2','player1_odds','draw_odds','player2_odds','capture_ts','match_start_utc']
        self.assertEqual([{k:r[k] for k in fields} for r in aces],[{k:r[k] for k in fields} for r in old_aces])
        (W/'adapter-verification.json').write_text(json.dumps(dict(saved_snapshot=data['server_time'],most_aces=len(aces),most_df=len(dfs),most_aces_prices_unchanged=True,fresh_today=False),indent=2))
    def test_roi_ties_and_unselected_observations(self):
        now=datetime.now(timezone.utc);records=[];out={}
        for i,(selected,side,result,odds) in enumerate([(True,1,1,6),(True,0,2,2.5),(False,0,0,2),(True,2,None,3)]):
            key=str(i);r=dict(id=key,date=now.date().isoformat(),names=['One','Two'],captured_at=now.isoformat(),start=(now-timedelta(hours=49)).isoformat(),probabilities=[.4,.2,.4],selection=dict(selected=selected,outcome=side,odds=odds,bookmaker='Bet365',fair_odds=5 if side==1 else 2.5,ev_pct=20,market_probabilities=[.4,.2,.4]))
            records.append(r)
            if result is not None:out[key]=dict(outcome=result)
        result=m.summary(records,out,{},dict(registered_at=now.isoformat()),now)
        self.assertEqual((result['wins'],result['losses'],result['pending'],result['overdue']),(1,1,1,1))
        self.assertEqual((result['stake_units'],result['pnl_units'],result['roi_pct']),(2,4,200))
        self.assertEqual(result['settled_fixtures'],3)
        self.assertEqual(len(result['selections']),3)
        self.assertTrue(all(r['selection'] and r['stake_units']==1 for r in result['selections']))
        self.assertFalse(result['alerts_enabled'])
    def test_frozen_code_and_model_registration(self):
        with tempfile.TemporaryDirectory(dir=W) as tmp:
            root=Path(tmp);(root/'scripts').mkdir();model=root/'scripts/tennis_props_model.py';model.write_text('frozen fixture')
            first=m.run(root,register=True);self.assertEqual(first['capture']['state'],'AWAITING_FRESH_FORECAST')
            original=(root/m.REL/'registration.json').read_bytes();m.run(root);self.assertEqual((root/m.REL/'registration.json').read_bytes(),original)
            model.write_text('changed fixture')
            with self.assertRaisesRegex(ValueError,'frozen'):m.run(root)
if __name__=='__main__':unittest.main()
