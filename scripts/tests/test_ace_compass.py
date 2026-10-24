import copy
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import tennis_ace_compass as T
import ace_compass_engine as E
from ace_compass_reporting import weekly_text

class AceCompassTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,24,12,tzinfo=timezone.utc)
        self.q=dict(tour='ATP',market='aces',line='4.5',over_odds='2.0',capture_ts=(self.now-timedelta(minutes=2)).isoformat(),match_start_utc=(self.now+timedelta(hours=2)).isoformat(),matched_board='yes',match_source='exact',bookmaker='Bet365',player='A',opponent='B',tournament='Test')
        f=dict(average_points=75,player_rate=.08,b=.07,opp_current=.07,opp_faced=.06,theta_ace=0)
        self.r=dict(id='x',player_key='f:p',fixture_key='f',registered_at=self.now.isoformat(),row=self.q,stratum='ATP main draw',**E.predict(f,4.5,2))
        self.r['candidate']['selected']=self.r['control']['selected']=True
    def report(self,rows,outcomes):return T.summarize(rows,outcomes,dict(registered_at=self.now.isoformat()),dict(state='CAPTURED'),self.now)
    def test_requires_fresh_prematch_halfpoint_quote(self):
        self.assertIsNone(T.eligible(self.q,self.now))
        for changes in [dict(capture_ts=(self.now-timedelta(hours=7)).isoformat()),dict(match_start_utc=self.now.isoformat()),dict(line='5'),dict(over_odds='nan'),dict(match_source='fuzzy')]:
            self.assertIsNotNone(T.eligible(dict(self.q,**changes),self.now))
    def test_losses_retained_voids_excluded_from_stake(self):
        lost=self.report([self.r],{'x':dict(status='settled',actual=3)})['arms']['candidate']
        self.assertEqual((lost['losses'],lost['pnl_units'],lost['roi_pct']),(1,-1,-100))
        void=self.report([self.r],{'x':dict(status='void',actual=None)})['arms']['candidate']
        self.assertEqual(void['stake_units'],0);self.assertIsNone(void['roi_pct'])
    def test_bias_counts_player_match_once(self):
        second=copy.deepcopy(self.r);second['id']='y'
        result=self.report([self.r,second],{'x':dict(status='settled',actual=6),'y':dict(status='settled',actual=6)})
        self.assertEqual(result['bias'][0]['actual'],6);self.assertEqual(result['bias'][0]['player_matches'],1)
        self.assertEqual(result['arms']['candidate']['settled'],2)
    def test_tampered_ledger_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'observations.jsonl';rows=[];T.append(p,rows,self.r);self.assertEqual(T.ledger(p),rows)
            p.write_text(p.read_text().replace('ATP main draw','Challenger main draw'))
            with self.assertRaises(ValueError):T.ledger(p)
    def test_expiry_and_current_edition_exclusion(self):
        state=E.FacedState();r=dict(pid='1',opp='2',surface='Hard',tid='10',rank='2',best_of=3,day=1000,v=[5,2,40,60,3,1,20,60])
        f=state.feature('1','2','Hard','10','2',3);state.add(r,f)
        current=state.feature('1','2','Hard','10','2',3)
        self.assertEqual(current['player_points'],0);self.assertEqual(current['expected_conceded'],0)
        self.assertGreater(state.feature('1','2','Hard','11','2',3)['expected_conceded'],0)
        state.expire(1731);self.assertEqual(state.feature('1','2','Hard','11','2',3)['expected_conceded'],0)
    def test_format_rules_preserved(self):
        self.assertEqual(E.match_best_of('ATP','Wimbledon',3,slam=True),5)
        self.assertEqual(E.match_best_of('ATP','Wimbledon',2,slam=True),3)
        self.assertIsNone(E.match_best_of('ATP','Laver Cup',4))
        self.assertFalse(E.event_condition_eligible('United Cup'))
    def test_weekly_reports_absence_and_real_sample(self):
        self.assertIn('unavailable',weekly_text({}))
        text=weekly_text(self.report([self.r],{'x':dict(status='settled',actual=3)}))
        self.assertIn('0W/1L',text);self.assertIn('ROI -100.00%',text);self.assertIn('bias',text);self.assertIn('Historical',text)
    def test_capture_locks_first_price_and_reuses_private_cache(self):
        now=datetime.now(timezone.utc);q=dict(self.q,date=now.date().isoformat(),capture_ts=(now-timedelta(minutes=1)).isoformat(),match_start_utc=(now+timedelta(hours=3)).isoformat())
        board=dict(q,generation_date=now.date().isoformat(),tour_id='10',round='4',player_id='1',opponent_id='2')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);file=root/'quotes.csv';file.touch();folder=root/'paper';folder.mkdir();rows=[]
            def read(p):return [q] if p.name=='quotes.csv' else [board]
            with patch.object(E,'read',side_effect=read),patch.object(T,'source_manifest',return_value={}),patch.object(E,'history',return_value=([],{'10':dict(name='Test',rank='2',court_id='1')},{})) as history:
                reg=dict(implementation={});T.capture(root,root,folder,rows,file,now,reg);self.assertEqual(len(rows),1)
                q['over_odds']='3.0';T.capture(root,root,folder,rows,file,now,reg);self.assertEqual(len(rows),1)
                # Read the persisted ledger, since input dictionaries in this test are mutable.
                self.assertEqual(T.ledger(folder/'observations.jsonl')[0]['row']['over_odds'],'2.0')
                q['line']='6.5';T.capture(root,root,folder,rows,file,now,reg);self.assertEqual(len(rows),2);self.assertEqual(history.call_count,1)
    def test_settlement_requires_exact_native_fixture(self):
        r=copy.deepcopy(self.r);r['native']=dict(tid='10',round='4',pid='1',opp='2');r['row']['match_start_utc']=(self.now-timedelta(hours=1)).isoformat();r['registered_at']=(self.now-timedelta(hours=3)).isoformat()
        game=dict(tour_id='10',round_id='4',winner_id='1',loser_id='2',date='2026-10-24',result='6-3 6-4');stat=dict(game,w_ace='6',l_ace='3')
        with patch.object(E,'read',side_effect=lambda p:[game] if p.name.startswith('games') else [stat]),patch.object(E,'adapt',return_value=({},None)):
            outcomes={};T.settle(Path('.'),[r],outcomes,self.now);self.assertEqual(outcomes['x']['actual'],6)
            r['native']['opp']='9';outcomes={};T.settle(Path('.'),[r],outcomes,self.now);self.assertEqual(outcomes,{})
    def test_conflicting_result_not_settled(self):
        r=copy.deepcopy(self.r);r['native']=dict(tid='10',round='4',pid='1',opp='2');r['row']['match_start_utc']=(self.now-timedelta(hours=1)).isoformat()
        g=dict(tour_id='10',round_id='4',winner_id='1',loser_id='2',date='2026-10-24',result='6-3 6-4')
        with patch.object(E,'read',side_effect=lambda p:[g,dict(g,result='6-2 6-4')] if p.name.startswith('games') else []):
            outcomes={};T.settle(Path('.'),[r],outcomes,self.now);self.assertEqual(outcomes,{})

if __name__=='__main__':unittest.main()
