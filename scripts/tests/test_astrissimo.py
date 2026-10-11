import sys,json,tempfile,unittest,runpy
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tennis_astrissimo as a
class Tests(unittest.TestCase):
    def test_symmetry(self):
        x=[.2,-.3,.15,.1];self.assertAlmostEqual(a.probability(x,.61)+a.probability([-v for v in x],.39),1)
    def test_elo_update(self):
        s=a.empty();a.update(s,{'p1':2,'p2':10,'winner':0,'surface':'Hard'})
        self.assertEqual(s['elo'],{'2':1512.,'10':1488.});self.assertGreater(a.features(s,2,10,'hard')[3],0)
        self.assertEqual(a.features(s,2,10,'hard'),[-v for v in a.features(s,10,2,'hard')])
    def test_scope(self):
        row={'player1_id':'10','player2_id':'20','official_category':'Challenger','source_contract':a.INPUT_CONTRACT,'model_policy':'category_corrected','round_id':5,'surface':'Hard'}
        self.assertEqual(a.eligible(row),'outside_ATP_main_draw');row['official_category']='ATP250';self.assertIsNone(a.eligible(row));row['round_id']=3;self.assertEqual(a.eligible(row),'qualifying_excluded')
    def test_selection(self):
        self.assertEqual(a.choose(.6,{'odds1':2.,'odds2':1.8})['side'],0)
        self.assertIsNone(a.choose(.5,{'odds1':1.9,'odds2':1.9}))
        self.assertIsNone(a.choose(.8,{'odds1':1.4,'odds2':6.}))
    def test_settlement_and_alert_dedup(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/a.RELATIVE;(folder/'captures').mkdir(parents=True);(root/'data/oncourt').mkdir(parents=True)
            now=datetime(2026,10,11,12,tzinfo=timezone.utc)
            packet={'fixture_key':'1|4|10|20','registered_at':(now-timedelta(days=1,hours=2)).isoformat(),'players':['10','20'],'names':['A','B'],'tour_id':'1','round_id':'4','category':'ATP250','tournament':'Tokyo','model_hash':a.MODEL_HASH,'actual_stake':0,'probability':.6,'quote':{'kickoff_iso':(now-timedelta(days=1)).isoformat(),'market_p1':.55},'selection':a.choose(.6,{'odds1':2.,'odds2':1.8})}
            a.atomic(folder/'captures/one.json',packet)
            game=root/'data/oncourt/games_atp.csv';game.write_text('winner_id,loser_id,tour_id,round_id,result,date\n10,20,1,4,6-2 6-3,2026-10-10\n')
            r=a.summarize(root,now=now);self.assertEqual((r['wins'],r['roi_pct'],r['stake_units']),(1,100.,1))
            sent=[];a.alerts(root,lambda msg:sent.extend(msg),now=now);a.alerts(root,lambda msg:sent.extend(msg),now=now);self.assertEqual(len(sent),1)
            game.write_text('winner_id,loser_id,tour_id,round_id,result,date\n10,20,1,4,6-2 2-1 RET,2026-10-10\n');r=a.summarize(root,now=now);self.assertEqual((r['void'],r['settled'],r['roi_pct']),(1,0,None))
            game.write_text('winner_id,loser_id,tour_id,round_id,result,date\n10,20,1,5,6-2 6-3,2026-10-10\n');r=a.summarize(root,now=now);self.assertEqual(r['pending'],1)
    def test_relay_failure_not_marked_sent(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with self.assertRaises(RuntimeError):a.alerts(root,lambda _:(_ for _ in ()).throw(RuntimeError('failed')))
            self.assertFalse((root/a.RELATIVE/'telegram-state.json').exists())
    def test_stale_quotes_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);f=r/'data/pinnacle-history';f.mkdir(parents=True)
            now=datetime.now(timezone.utc)
            (f/f'pinnacle-history-{now:%Y%m%d}-000000.csv').write_text(f'captured_at,kickoff_iso,bookmaker\n{(now-timedelta(hours=3)).isoformat()},{(now+timedelta(hours=3)).isoformat()},Pinnacle\n')
            self.assertEqual(a.load_quotes(r,now)[0],[])
    def test_provider_alias_keeps_event_identity(self):
        h=runpy.run_path(str(Path(a.__file__).parent/'tennis-props-pipeline-health.py'))
        row={'event_id':'123','bookmaker':'Bet365','player':'Ekaterina Alexandrova','opponent':'Leylah Fernandez','market':'match_aces','line':'2.5','capture_ts':'2026-10-10T19:22:32Z'}
        canonical=dict(row,opponent='Leylah Annie Fernandez')
        self.assertEqual(h['observation_key'](row),h['observation_key'](canonical))
        self.assertNotEqual(h['observation_key'](row),h['observation_key'](dict(canonical,event_id='456')))
    def test_corrected_cohort_reports_wins_and_losses(self):
        m=runpy.run_path(str(Path(a.__file__).parent/'tennis-props-rate-trend-prospective.py'))
        now=datetime(2026,10,11,12,tzinfo=timezone.utc);records=[]
        for i in range(2):
            records.append({'id':str(i),'fixture_key':str(i),'registered_at':'2026-10-10T12:00:00Z',
                'row':{'market':'aces','tournament':'Shanghai','history_version':'current','line':'5.5','over_odds':'2.5'},
                'control':{'OVER':{'p_conditional':.5}},'candidate':{'OVER':{'p_conditional':.5}},'control_side':'OVER','candidate_side':'OVER'})
        result=m['report'](records,{'0':{'status':'settled','actual':6},'1':{'status':'settled','actual':3}}, {}, {'id':'test','markets':['aces']},now)
        cohort=result['history_versions']['current']['aces']['candidate']
        self.assertEqual((cohort['wins'],cohort['losses'],cohort['stake_units'],cohort['pnl_units']),(1,1,2,.5))
if __name__=='__main__':unittest.main()
