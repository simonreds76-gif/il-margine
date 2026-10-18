import copy
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aerial_data import save,read
from skyline_model import History, FEATURES, height_gap, qualifies
from skyline_paper import run, resolve, summarize

NOW=datetime(2026,10,18,12,tzinfo=timezone.utc)


def setup(root):
    teams=[{'id':t,'name':'Home' if t=='1' else 'Away','players':[
        {'id':f'{t}{i}','name':f'Player {t}{i}','role':'GK' if i==0 else 'DEF' if i<5 else 'ATT'} for i in range(11)]} for t in ('1','2')]
    f={'id':'target','state':'confirmed','competition':'Premier League','kickoff':(NOW+timedelta(hours=1)).isoformat(),
       'observed_at':NOW.isoformat(),'valid_until':(NOW+timedelta(hours=1)).isoformat(),'teams':teams}
    history=[{'id':str(i),'league_id':'47','date':(NOW-timedelta(days=10-i)).isoformat(),'home_id':'1','away_id':'2',
        'players':[{'id':'15','team_id':'1','minutes':90,'starter':True,'headed_shots':3,'headed_sot':1}],
        'delivery':[{'team_id':t,'corners':6,'crosses_attempted':22} for t in ('1','2')]} for i in range(8)]
    heights={p['id']:{'height_cm':190 if p['id']=='15' else 180,'role_group':'defenders' if p['role']=='DEF' else 'forwards'} for t in teams for p in t['players']}
    models={v:{'intercept':0,'weights':[1]+[0]*(len(indices)-1)} for v,indices in FEATURES.items()}
    artifact={'version':'skyline-test','models':models}
    quotes={'generated_at':NOW.isoformat(),'events':[{'event_id':'odds1','home':'Home','away':'Away','kickoff':f['kickoff'],
        'captured_at':NOW.isoformat(),'bookmaker':'Bet365','source':'fixture-test',
        'markets':[{'name':'Player Headed Shots on Target','odds':[{'label':'Player 15 (1)','hdp':.5,'over':'4'}]}]}]}
    save(root/'data/aerial/skyline/model.json',artifact);save(root/'data/aerial/heights.json.gz',heights)
    save(root/'data/aerial/history.json.gz',{'matches':history});save(root/'public/fair-odds-lab/aerial.json',{'generated_at':NOW.isoformat(),'fixtures':[f]})
    save(root/'data/goalkeeper-saves/aerial-headed-market-prices.json',quotes)
    return f,history,artifact,quotes


class Skyline(unittest.TestCase):
    def test_prior_rows_only_and_no_actual_target_minutes(self):
        with tempfile.TemporaryDirectory() as d:
            f,h,_,_=setup(Path(d));state=History()
            for m in h:state.add(m)
            a=state.features('15','1','47',f['kickoff'],10)
            self.assertEqual(a['matches'],8);self.assertEqual(a['expected_minutes'],(8*90+3*75)/11)
            self.assertNotIn('target',a['prior_fixture_ids'])
            self.assertIsNone(state.features('unknown','1','47',f['kickoff'],None))

    def test_first_forecast_immutable_and_no_preview_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);f,h,a,q=setup(root)
            self.assertEqual(run(root,NOW,False)['forecasts'],0)
            r=run(root,NOW,True);self.assertEqual(r['forecasts'],1);self.assertEqual(r['stats']['baseline']['pending'],1)
            q['events'][0]['markets'][0]['odds'][0]['over']='8'
            save(root/'data/goalkeeper-saves/aerial-headed-market-prices.json',q)
            r=run(root,NOW+timedelta(minutes=1),True);self.assertEqual(r['forecasts'],1);self.assertEqual(r['ledger'][0]['odds'],4)
            self.assertEqual(r['board'][0]['odds'],8)
            a['models']['baseline']['intercept']=1;save(root/'data/aerial/skyline/model.json',a)
            with self.assertRaisesRegex(ValueError,'Frozen'):run(root,NOW,True)

    def test_expected_stale_and_started_never_captured(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);f,h,a,q=setup(root);f['state']='expected'
            save(root/'public/fair-odds-lab/aerial.json',{'generated_at':NOW.isoformat(),'fixtures':[f]})
            r=run(root,NOW,True);self.assertEqual(r['forecasts'],0);self.assertEqual(len(r['board']),1)
            self.assertEqual(run(root,NOW+timedelta(hours=2),True)['forecasts'],0)
            q['events'][0]['captured_at']=(NOW-timedelta(hours=3)).isoformat();save(root/'data/goalkeeper-saves/aerial-headed-market-prices.json',q)
            self.assertEqual(run(root,NOW,True)['board'],[])

    def test_exact_settlement_roi_missing_counts_and_void(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);f,h,a,q=setup(root);run(root,NOW,True)
            target={'id':'target','date':f['kickoff'],'source_sha256':'result-hash','players':[{'id':'15','team_id':'1','starter':True,'minutes':70,'headed_shots':2,'headed_sot':None}],'delivery':[],'league_id':'47'}
            record=read(next((root/'data/aerial/skyline/forecasts').glob('*.json')))
            self.assertIsNone(resolve(record,{'target':target},NOW+timedelta(hours=5)))
            target['players'][0]['headed_sot']=1;save(root/'data/aerial/history.json.gz',{'matches':h+[target]})
            r=run(root,NOW+timedelta(hours=5),True);s=r['stats']['baseline']
            self.assertEqual((s['wins'],s['settled_stake'],s['profit'],s['roi']),(1,1,3,300))
            target['players'][0]['headed_sot']=0
            self.assertEqual(resolve(record,{'target':target},NOW+timedelta(hours=5))['status'],'loss')
            target['players'][0]['starter']=False
            self.assertEqual(resolve(record,{'target':target},NOW+timedelta(hours=5))['status'],'void')
            target['date']=(NOW+timedelta(days=1)).isoformat()
            self.assertIsNone(resolve(record,{'target':target},NOW+timedelta(days=2)))

    def test_future_results_do_not_change_current_forecast(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);f,h,a,q=setup(root);before=run(root,NOW,False)['board'][0]['predictions']
            future=copy.deepcopy(h[0]);future['id']='future';future['date']=(NOW+timedelta(days=3)).isoformat()
            future['players'][0]['headed_shots']=100;future['players'][0]['headed_sot']=90
            save(root/'data/aerial/history.json.gz',{'matches':h+[future]})
            self.assertEqual(run(root,NOW,False)['board'][0]['predictions'],before)

    def test_unknown_height_no_invention_and_fixed_selection_rule(self):
        self.assertIsNone(height_gap('1',['2','3','4'],{}))
        self.assertFalse(qualifies(.2,4,80));self.assertTrue(qualifies(.3,4,80))
        self.assertFalse(qualifies(.3,4,45))


if __name__=='__main__':unittest.main()
