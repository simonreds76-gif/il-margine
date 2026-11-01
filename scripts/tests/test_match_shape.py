import copy
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import tennis_match_shape as M
from tennis_match_shape_kernel import joint,tilt,marginal,contract,complete_score,TP

NOW=datetime(2026,11,2,8,tzinfo=timezone.utc)


def receipt(market='total_games'):
    total=market=='total_games'
    event=dict(id=123,homeName='A Player',awayName='B Player',start=(NOW+timedelta(hours=2)).isoformat(),group='Paris',sport='TENNIS',state='NOT_STARTED',path=[{'termKey':'atp'}])
    outcomes=[dict(type=t,status='OPEN',odds=o,line=l,betOfferId=456,changedDate=NOW.isoformat(),participant=p)
              for t,o,l,p in zip(('OT_OVER','OT_UNDER') if total else ('OT_ONE','OT_TWO'),(2000,1900),(22500,22500) if total else (-2500,2500),('A Player','B Player'))]
    offer=dict(id=456,eventId=123,criterion={'englishLabel':'Total Games' if total else 'Game Handicap'},betOfferType={'id':6 if total else 1},tags=['OFFERED_PREMATCH','MAIN_LINE'],outcomes=outcomes)
    return {'events':[dict(requested_id=123,captured_at=NOW.isoformat(),payload={'events':[event],'betOffers':[offer]})]}


class KernelTests(unittest.TestCase):
    def test_joint_and_winner_invariant_and_swap(self):
        for a,b,p in [(.64,.64,.5),(.7,.58,.82),(.43,.77,.03)]:
            q=joint(a,b);t=tilt(q,p);rev=joint(b,a)
            self.assertAlmostEqual(sum(q.values()),1,12)
            self.assertAlmostEqual(sum(v for k,v in t.items() if k[0]),p,12)
            self.assertLess(max(abs(v-rev[(not k[0],-k[1],k[2])]) for k,v in q.items()),1e-11)
            expected=TP.match_games_pmf(a,b,3)
            self.assertLess(max(abs(v-expected[k]) for k,v in marginal(q,2).items()),1e-10)
            self.assertTrue(all(12<=k[2]<=39 and (k[2]-k[1])%2==0 and v>=0 for k,v in t.items()))
    def test_tilt_shrinks_without_actual_winner(self):
        q=joint(.64,.64);t=tilt(q,.5)
        self.assertLess(sum(k[2]*v for k,v in t.items()),sum(k[2]*v for k,v in q.items()))
        # Winning a match can have a negative games margin; never use sign for winner.
        self.assertTrue(any(k[0] and k[1]<0 for k in q))
    def test_push_fair_and_roi_selection(self):
        q={'odds1':2.2,'odds2':1.8};p={'minimum_ev':.1,'minimum_probability_edge':.05}
        d=M.decision((.55,.1,.35),q,p)
        self.assertAlmostEqual(d['fair_odds'],.9/.55)
        self.assertAlmostEqual(d['ev_pct'],31)
        self.assertEqual(contract({20:.2,22:.3,24:.5},'total_games',22),(.5,.3,.2))
        self.assertTrue(d['selected'])
    def test_completed_score(self):
        self.assertEqual(complete_score('7-6(5) 6-4'),(3,23))
        self.assertEqual(complete_score('0-6 7-6 7-6'),(-4,32))
        for score in ('6-4 2-1 RET','6-4','6-4 6-4 6-0','6-5 6-4','7-4 6-0','W/O','4-6 4-6'):
            self.assertIsNone(complete_score(score))


class QuoteTests(unittest.TestCase):
    def test_signed_handicap(self):
        q=M.parse_receipt(receipt('game_handicap'),NOW)
        self.assertEqual(q[0]['line'],-2.5);self.assertEqual(q[0]['odds1'],2)
    def test_fresh_open_prematch_exact_contract(self):
        base=receipt();self.assertEqual(len(M.parse_receipt(base,NOW)),1)
        for mutation in ('suspended','set_total','live','stale','future','badpair'):
            r=copy.deepcopy(base);i=r['events'][0];o=i['payload']['betOffers'][0]
            if mutation=='suspended':o['outcomes'][0]['status']='SUSPENDED'
            if mutation=='set_total':o['criterion']['englishLabel']='Total Games - Set 1'
            if mutation=='live':i['payload']['events'][0]['state']='STARTED'
            if mutation=='stale':i['captured_at']=(NOW-timedelta(hours=1)).isoformat()
            if mutation=='future':i['captured_at']=(NOW+timedelta(minutes=1)).isoformat()
            if mutation=='badpair':o['outcomes'][1]['line']=23500
            self.assertEqual(M.parse_receipt(r,NOW),[],mutation)
    def test_changed_date_can_be_old_when_freshly_observed(self):
        r=receipt()
        for o in r['events'][0]['payload']['betOffers'][0]['outcomes']:o['changedDate']=(NOW-timedelta(days=1)).isoformat()
        self.assertEqual(len(M.parse_receipt(r,NOW)),1)


class SettlementTests(unittest.TestCase):
    def setUp(self):
        self.r=dict(registration_sha256='hash',captured_at=(NOW-timedelta(hours=3)).isoformat(),actual_stake=0,
                    quote={'scheduled_start':(NOW-timedelta(hours=2)).isoformat(),'line':22.5},market='total_games',components={'player1_id':10})
        self.g=dict(winner_id='10',loser_id='20',date='2026-11-02',result='7-6(4) 6-4')
    def test_total_handicap_and_push(self):
        o=M.outcome(self.r,[self.g],NOW,'hash');self.assertEqual(o['side1_outcome'],1)
        self.r['quote']['line']=23;self.assertEqual(M.outcome(self.r,[self.g],NOW,'hash')['side1_outcome'],0)
        self.r['market']='game_handicap';self.r['quote']['line']=-3
        self.assertEqual(M.outcome(self.r,[self.g],NOW,'hash')['side1_outcome'],0)
        self.r['components']['player1_id']=20
        self.assertEqual(M.outcome(self.r,[self.g],NOW,'hash')['side1_outcome'],-1)
    def test_ambiguous_and_unfinished_not_wins(self):
        bad={**self.g,'result':'6-0 6-0'}
        self.assertEqual(M.outcome(self.r,[self.g,bad],NOW,'hash')['status'],'quarantined')
        self.assertEqual(M.outcome(self.r,[{**bad,'result':'6-0 1-0 RET'}],NOW,'hash')['status'],'excluded')
        self.assertEqual(M.outcome(self.r,[],NOW,'hash')['status'],'pending')
    def test_integrity_and_result_time(self):
        self.assertEqual(M.outcome(self.r,[self.g],NOW,'wrong')['status'],'quarantined')
        self.assertEqual(M.outcome(self.r,[{**self.g,'date':'2026-10-01'}],NOW,'hash')['status'],'quarantined')


class CaptureLifecycleTests(unittest.TestCase):
    def test_first_capture_deduplicates_and_results_do_not_rewrite_forecasts(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'outputs') as tmp:
            root=Path(tmp)
            assert root.resolve().is_relative_to((ROOT/'outputs').resolve())
            out=root/M.RELATIVE
            (root/'config').mkdir();(root/M.PROTOCOL).write_bytes((ROOT/M.PROTOCOL).read_bytes())
            row=dict(tour_id=123,round_id=5,player1_id=10,player2_id=20,player1='A Player',player2='B Player',
                     best_of=3,model_policy='category_corrected',official_category='Masters 1000',surface='I.hard',tour_name='Paris',p1_win_prob=.5,p_a=.64,p_b=.64,
                     opportunity_diagnostics=dict(p_a_unrounded=.64,p_b_unrounded=.64,ou_shift=2.4,tournament_residual_adjustment=0,final_expected_games_unrounded=22.2))
            packet={'rows':[row],'payload_sha256':M.digest([row])}
            h=SimpleNamespace()
            config={}
            with patch.object(M,'fingerprints',return_value={'f':'fixed'}),patch.object(M,'settings',return_value=(h,None,config)),patch.object(M,'identity_index',return_value=None),patch.object(M,'map_quote',return_value={'edition_id':123,'round_id':5,'p1_id':10,'p2_id':20}),patch.object(M,'fresh_components',return_value=(NOW,packet)),patch.object(M,'game_index',return_value=defaultdict(list)),patch.object(M,'probabilities',return_value=({a:(.7,0,.3) for a in M.ARMS},{a:24 for a in M.ARMS},0)):
                M.register(root,NOW-timedelta(minutes=1))
                first=M.refresh(root,NOW,receipt())
                self.assertEqual(first['contracts'],1)
                self.assertEqual(first['arms']['T1']['total_games']['pending'],1)
                files=list((out/'captures').glob('*.json'));saved=files[0].read_bytes()
                again=M.refresh(root,NOW+timedelta(minutes=1),receipt())
                self.assertEqual(again['capture']['captured'],0)
                self.assertEqual(saved,files[0].read_bytes())
            games={'123|5|10|20':[dict(winner_id='10',loser_id='20',date='2026-11-02',result='7-6 6-4')]}
            with patch.object(M,'game_index',return_value=games):
                report=M.summarize(root,NOW+timedelta(hours=5))
            self.assertEqual(report['settled_fixtures'],1)
            self.assertEqual(report['arms']['T1']['total_games']['wins'],1)
            self.assertEqual(report['arms']['T1']['total_games']['roi_pct'],100)
            self.assertEqual(saved,files[0].read_bytes())
            self.assertEqual(report['actual_stake'],0)
            with patch.object(M,'fingerprints',return_value={'f':'changed'}):
                blocked=M.refresh(root,NOW+timedelta(hours=6),receipt())
                self.assertEqual(blocked['capture']['state'],'BLOCKED')


if __name__=='__main__':unittest.main()
