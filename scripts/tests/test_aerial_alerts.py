import copy
from datetime import datetime, timezone, timedelta
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aerial_alerts import evaluate, run, settle, VERSION
from aerial_data import save, read
from aerial_source import extract

NOW=datetime(2026,10,11,17,0,tzinfo=timezone.utc)

def fixture():
    teams=[]
    for tid in ('1','2'):
        players=[dict(id=f'{tid}{i:02}',name=f'Player {tid}{i}',role='GK' if i==0 else 'DEF' if i<=4 else 'ATT',
                      height_cm=196 if tid=='1' and i==5 else 180) for i in range(11)]
        teams.append(dict(id=tid,name=f'Team {tid}',players=players))
    return dict(id='999',state='expected',kickoff=(NOW+timedelta(hours=2)).isoformat(),
                observed_at=NOW.isoformat(),valid_until=(NOW+timedelta(hours=2)).isoformat(),teams=teams)

def history():
    return [dict(id=str(i),date=(NOW-timedelta(days=i+1)).isoformat(),home_id='1',away_id='2',
        players=[dict(id=f'{tid}{n:02}',team_id=tid,minutes=90,aerials_won=5,aerials_attempted=10,
                      headed_shots=1 if tid=='1' and n==5 else 0,
                      headed_sot=1 if tid=='1' and n==5 and i%2==0 else 0,
                      headed_goals=1 if tid=='1' and n==5 and i%5==0 else 0,
                      set_piece_headers=0) for tid in ('1','2') for n in range(11)],
        delivery=[dict(team_id=t,corners=5,crosses_attempted=18,headed_shots_against=2) for t in ('1','2')]) for i in range(10)]

def packet(f=None):
    return dict(version='verified-test-only',generated_at=NOW.isoformat(),fixtures=[f or fixture()])

class Alerts(unittest.TestCase):
    def test_real_evidence_filters_and_no_invented_ev(self):
        rows,_=evaluate(packet(),history(),NOW)
        self.assertEqual([c['player_id'] for c in rows[0]['candidates']],['105'])
        c=rows[0]['candidates'][0]
        self.assertEqual(c['height_gap_cm'],16)
        self.assertEqual(c['history']['headers'],10)
        self.assertIsNone(c['ev']);self.assertIsNone(c['fair_odds'])
        self.assertIn('1+ headed shot on target',c['markets_to_check'])

    def test_no_heading_no_alert_even_if_tall(self):
        h=history()
        for m in h:
            for p in m['players']:p['headed_shots']=0
        self.assertEqual(evaluate(packet(),h,NOW)[0],[])

    def test_started_stale_incomplete_and_insufficient_samples(self):
        f=fixture();f['kickoff']=NOW.isoformat()
        self.assertEqual(evaluate(packet(f),history(),NOW)[0],[])
        p=packet();p['generated_at']=(NOW-timedelta(hours=4)).isoformat()
        self.assertEqual(evaluate(p,history(),NOW)[0],[])
        f=fixture();f['teams'][1]['players'].pop()
        self.assertEqual(evaluate(packet(f),history(),NOW)[0],[])
        self.assertEqual(evaluate(packet(),history()[:2],NOW)[0],[])

    def test_target_and_future_outcomes_cannot_affect_screen(self):
        h=history();expected=evaluate(packet(),h,NOW)[0]
        target=copy.deepcopy(h[0]);target.update(id='999',date=(NOW+timedelta(hours=2)).isoformat())
        target['players'][5]['headed_shots']=99
        self.assertEqual(evaluate(packet(),h+[target],NOW)[0],expected)

    def test_missing_fields_remain_unknown(self):
        h=history()
        for m in h:
            for p in m['players']:p.pop('headed_sot');p.pop('headed_goals')
        row=evaluate(packet(),h,NOW)[0][0]['candidates'][0]
        self.assertEqual(row['history']['headed_sot']['matches'],0)
        self.assertEqual(row['markets_to_check'],['1+ headed shot'])

    def test_delivery_dedup_confirmation_and_preview_not_prospective(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{'OPS_ALERT_TELEGRAM_BOT_TOKEN':'test','OPS_ALERT_TELEGRAM_CHAT_ID':'private'}):
            root=Path(d);save(root/'public/fair-odds-lab/aerial.json',packet());save(root/'data/aerial/history.json.gz',{'matches':history()})
            self.assertEqual(run(root,NOW)['prospective_captures'],0)
            calls=[]
            def sender(text,token,chat):calls.append(text);return len(calls)
            self.assertEqual(run(root,NOW,True,sender)['status'],'sent')
            self.assertEqual(run(root,NOW,True,sender)['status'],'no_new_qualifiers')
            f=fixture();f['state']='confirmed';save(root/'public/fair-odds-lab/aerial.json',packet(f))
            self.assertEqual(run(root,NOW,True,sender)['status'],'sent')
            self.assertEqual(len(calls),2)
            ledger=read(root/'data/aerial/alerts/ledger.json');self.assertEqual(len(ledger),2)
            self.assertTrue(all(r['version']==VERSION for r in ledger))

    def test_failure_does_not_mark_delivered_and_withdrawal_is_sent(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{'OPS_ALERT_TELEGRAM_BOT_TOKEN':'test','OPS_ALERT_TELEGRAM_CHAT_ID':'private'}):
            root=Path(d);save(root/'public/fair-odds-lab/aerial.json',packet());save(root/'data/aerial/history.json.gz',{'matches':history()})
            self.assertEqual(run(root,NOW,True,lambda *args:None)['status'],'delivery_failed')
            run(root,NOW,True,lambda *args:1)
            f=fixture();f['state']='confirmed';f['teams'][0]['players'][5]['id']='888'
            save(root/'public/fair-odds-lab/aerial.json',packet(f));calls=[]
            def sender(text,*args):calls.append(text);return 2
            run(root,NOW,True,sender)
            self.assertEqual(len(calls),1);self.assertIn('withdrawn: Player 15',calls[0])

    def test_exact_settlement_and_no_zero_for_missing_sot(self):
        ledger=[dict(fixture_id='999',captured_at=NOW.isoformat(),candidates=[{'player_id':'105'}])]
        outcome=copy.deepcopy(history()[0]);outcome.update(id='999',date=(NOW+timedelta(hours=2)).isoformat());outcome['players'][5].pop('headed_sot')
        settle(ledger,[outcome]);c=ledger[0]['candidates'][0]
        self.assertEqual(c['outcomes']['headed_shots'],1);self.assertIsNone(c['outcomes']['headed_sot'])

    def test_shotmap_goal_saved_blocked_and_own_goal_are_distinct(self):
        row=dict(id='10',league_id='55',date='2026-01-01T12:00:00Z',home_id='1',away_id='2',season='2025/2026')
        shots=[dict(playerId=105,teamId=1,shotType='Header',eventType=e,isOnTarget=t,isBlocked=b,isOwnGoal=o,situation='FromCorner')
               for e,t,b,o in [('Goal',True,False,False),('AttemptSaved',True,False,False),('AttemptSaved',False,True,False),('Goal',True,False,True)]]
        page=dict(general=dict(matchId=10,leagueId=55,finished=True,matchTimeUTCDate=row['date'],homeTeam={'id':1},awayTeam={'id':2}),
                  content=dict(shotmap={'shots':shots},playerStats={'105':dict(id=105,teamId=1,name='Target',stats=[{'stats':{'minutes':{'key':'minutes_played','stat':{'value':90}}}}])}))
        p=extract(page,row)['players'][0]
        self.assertEqual(p['headed_shots'],3);self.assertEqual(p['headed_sot'],2);self.assertEqual(p['headed_goals'],1)

if __name__=='__main__':unittest.main()
