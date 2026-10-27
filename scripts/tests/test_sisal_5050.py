import copy
import csv
import json
import math
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tennis_sisal_5050 as T
from sisal_5050_reporting import weekly_text

NOW=datetime(2026,10,28,10,tzinfo=timezone.utc)

def quote(line=4.5,over=1.9,under=1.9):
    return dict(bookmaker='Sisal IT',tour='ATP',market='aces',line=str(line),over_odds=str(over),under_odds=str(under),
        capture_ts=(NOW-timedelta(minutes=1)).isoformat(),match_start_utc=(NOW+timedelta(hours=2)).isoformat(),
        provider_updated_at=(NOW-timedelta(minutes=2)).isoformat(),source_url='https://www.sisal.it/test',
        raw_market_json=json.dumps(dict(name='Team Total (Aces) Home',odds=[dict(hdp=line,over=str(over),under=str(under))])),
        player='Player One',opponent='Player Two',tournament='Basel',date='2026-10-28',event_id='123')

def board():
    return dict(date='2026-10-28',tour='ATP',player='Player One',opponent='Player Two',tournament='Basel',tour_id='77',
        player_id='1',opponent_id='2',round='R32',surface='Hard',history_as_of='2026-10-27',generation_date='2026-10-28',
        history_version='oncourt-current-history-20261007-v1',history_fingerprint=T.hashlib.sha256(b'test baseline').hexdigest(),projected_aces='3',service_points_estimate='65',expected_match_games='22',
        expected_match_games_source='fair_odds',aces_alpha=str(T.ALPHA),v3_eligible='true',v3_model='all_tour_deployment_safe_atp_aces_v1')

def write_csv(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.parity=patch.object(T,'feature_reader',return_value=lambda b:({'best_of':3},{}));self.parity.start()
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.folder=self.root/T.REL;self.folder.mkdir(parents=True)
        self.reg=dict(registered_at=(NOW-timedelta(hours=1)).isoformat(),artifacts={},config=T.CONFIG)
        self.path=self.root/'quotes.csv'
        baseline=self.root/'data/tennis-props/player-props-baseline.csv';baseline.parent.mkdir(parents=True,exist_ok=True);baseline.write_bytes(b'test baseline')
        T.atomic(baseline.parent/'player-history-status.json',dict(state='CURRENT',version='oncourt-current-history-20261007-v1',as_of='2026-10-27',feature_cutoff='Completed results strictly before 2026-10-27',generated_at='2026-10-27T08:00:00+00:00',output_hashes={baseline.name:T.sha(baseline)}))
        write_csv(self.root/T.BOARD,[board()])
        write_csv(self.root/'data/oncourt/today_atp.csv',[dict(tour_id='77',player1_id='1',player2_id='2',round_id='4',date='2026-10-28',result='',complete='',live='')])
        write_csv(self.root/'data/oncourt/tours_atp.csv',[dict(id='77',rank='3',name='Basel')])
    def tearDown(self):self.parity.stop();self.tmp.cleanup()
    def capture(self,qs,rows=None):
        rows=[] if rows is None else rows;write_csv(self.path,qs)
        h=T.capture(self.root,self.folder,rows,self.path,NOW,self.reg,clock=lambda:NOW)
        return rows,h
    def test_same_day_exclusive_cutoff_allowed_only_with_verified_history(self):
        b=board();b['history_as_of']='2026-10-28';write_csv(self.root/T.BOARD,[b])
        path=self.root/'data/tennis-props/player-history-status.json';status=T.read_json(path,{})
        status.update(as_of='2026-10-28',feature_cutoff='Completed results strictly before 2026-10-28',generated_at='2026-10-28T08:00:00+00:00');T.atomic(path,status)
        rows,h=self.capture([quote()]);self.assertEqual(h['added'],1)
        status['generated_at']='2026-10-28T11:00:00+00:00';T.atomic(path,status)
        self.assertFalse(T.verified_history(self.root,b,T.stamp(quote()['capture_ts'])))
        status['generated_at']='2026-10-28T08:00:00+00:00';T.atomic(path,status)
        (path.parent/'player-props-baseline.csv').write_bytes(b'changed')
        self.assertFalse(T.verified_history(self.root,b,T.stamp(quote()['capture_ts'])))
    def test_nb_and_blend(self):
        from scipy.stats import nbinom
        for mean in (1,5,15,40):
            for line in (.5,4.5,12.5,40.5):
                expected=nbinom.sf(math.floor(line),1/T.ALPHA,1/(1+T.ALPHA*mean))
                self.assertAlmostEqual(T.over_probability(mean,line),expected,places=11)
        a=T.arms(5,5.5,1.8,2.0)
        self.assertAlmostEqual(a['blend50']['p_over'],(a['model']['p_over']+a['market']['p_over'])/2)
        self.assertFalse(a['market']['selected'])
    def test_first_price_canonical_and_repeat_lock(self):
        rows,h=self.capture([quote(5.5,1.5,2.5),quote(4.5,1.9,1.9)])
        self.assertEqual(h['added'],1);self.assertEqual(rows[0]['row']['line'],'4.5')
        before=copy.deepcopy(rows)
        q=quote(6.5,2.5,1.5);q['event_id']='changed-provider-id'
        self.capture([q],rows);self.assertEqual(rows,before)
        self.assertEqual(T.ledger(self.folder/'observations.jsonl'),rows)
    def test_reject_backfill_live_stale_incomplete_and_wrong_market(self):
        for changes in [dict(capture_ts=(NOW-timedelta(days=1)).isoformat()),dict(match_start_utc=(NOW+timedelta(minutes=14)).isoformat()),
                        dict(under_odds=''),dict(bookmaker='Bet365'),dict(provider_updated_at=(NOW-timedelta(days=2)).isoformat()),
                        dict(raw_market_json=json.dumps(dict(name='Most Aces',odds=[])))]:
            q=quote();q.update(changes);self.assertIsNotNone(T.quote_reason(q,NOW,T.stamp(self.reg['registered_at'])))
    def test_missing_exact_identity_and_stale_history_fail_closed(self):
        b=board();b['history_as_of']='2026-10-28';write_csv(self.root/T.BOARD,[b]);rows,h=self.capture([quote()]);self.assertFalse(rows)
        write_csv(self.root/T.BOARD,[board()]);write_csv(self.root/'data/oncourt/today_atp.csv',[dict(tour_id='88',player1_id='1',player2_id='2',round_id='4',date='2026-10-28')])
        rows,h=self.capture([quote()]);self.assertFalse(rows)
    def test_conflicting_result_kept_pending(self):
        rows,_=self.capture([quote()]);games=[dict(winner_id='1',loser_id='2',tour_id='77',round_id='4',result=s,date='2026-10-28') for s in ('6-3 6-3','6-4 6-4')]
        write_csv(self.root/'data/oncourt/games_atp.csv',games)
        write_csv(self.root/'data/oncourt/stat_atp.csv',[dict(winner_id='1',loser_id='2',tour_id='77',round_id='4',w_ace='2',w_svpt='50')])
        outcomes={};T.settle(self.root,rows,outcomes,NOW+timedelta(days=1));self.assertFalse(outcomes)
    def test_exact_settlement_orientation_and_loss_retention(self):
        rows,_=self.capture([quote()]);r=rows[0]
        self.assertEqual(r['native']['round'],'4');self.assertEqual(r['arms']['blend50']['side'],'under')
        write_csv(self.root/'data/oncourt/games_atp.csv',[dict(winner_id='2',loser_id='1',tour_id='77',round_id='4',result='6-4 6-3',date='2026-10-28')])
        write_csv(self.root/'data/oncourt/stat_atp.csv',[dict(winner_id='2',loser_id='1',tour_id='77',round_id='4',w_ace='1',l_ace='8',l_svpt='65')])
        out={};T.settle(self.root,rows,out,NOW+timedelta(days=1));self.assertEqual(out[r['id']]['actual'],8)
        report=T.summarize(rows,out,self.reg,{},NOW+timedelta(days=1),{})
        self.assertEqual(report['arms']['blend50']['losses'],1);self.assertEqual(report['arms']['blend50']['roi_pct'],-100)
        self.assertEqual(report['bias'][0]['bias_aces'],-5)
        old=copy.deepcopy(out);T.settle(self.root,rows,out,NOW+timedelta(days=2));self.assertEqual(old,out)
    def test_retirement_sisal_rules_and_missing_counts(self):
        rows,_=self.capture([quote()]);r=rows[0];g=dict(result='6-3 1-0 RET',winner_id='1')
        self.assertEqual(T.outcome(g,dict(w_ace='6',w_svpt='40'),r)['status'],'settled')
        self.assertEqual(T.outcome(g,dict(w_ace='3',w_svpt='40'),r)['status'],'void')
        self.assertIsNone(T.outcome(g,None,r))
        g['result']='W/O';self.assertEqual(T.outcome(g,None,r)['status'],'void')
    def test_disqualification_uses_determined_total_rule(self):
        rows,_=self.capture([quote()]);r=rows[0]
        for marker in ('DEF','DQ','DISQ'):
            g=dict(result='6-3 1-0 '+marker,winner_id='1')
            self.assertEqual(T.outcome(g,{'w_ace':'5','w_svpt':'40'},r)['status'],'settled')
            self.assertEqual(T.outcome(g,{'w_ace':'3','w_svpt':'40'},r)['status'],'void')
            self.assertIsNone(T.outcome(g,None,r))
    def test_retired_determined_bets_not_completed_calibration(self):
        rows,_=self.capture([quote()]);out={rows[0]['id']:dict(status='settled',completed=False,actual=6,actual_points=40)}
        report=T.summarize(rows,out,self.reg,{},NOW,{})
        self.assertEqual(report['arms']['blend50']['settled'],1);self.assertIsNone(report['arms']['blend50']['brier']);self.assertFalse(report['bias'])
    def test_empty_is_not_roi_zero_or_historical_profit(self):
        report=T.summarize([],{},self.reg,dict(state='NO_NEW_ELIGIBLE_QUOTES'),NOW,{})
        self.assertIsNone(report['arms']['blend50']['roi_pct']);self.assertIn('awaiting settlements',weekly_text(report))
    def test_ledger_tampering_rejected(self):
        self.capture([quote()]);p=self.folder/'observations.jsonl';p.write_text(p.read_text().replace('Player One','Altered'))
        with self.assertRaises(ValueError):T.ledger(p)
    def test_writer_lock_releases(self):
        with T.lock(self.folder):
            with self.assertRaises(OSError):
                with T.lock(self.folder):pass
        with T.lock(self.folder):pass

if __name__=='__main__':unittest.main()
