import copy,json,math,sys,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import frozen_paper_common as C
import tennis_match_shape_j1 as J
import tennis_j1_rates as R
import team_shots_strength_paper as S
import tennis_match_shape_quotes as Q
from tennis_match_winner_quotes import bind_winner
from test_match_shape import receipt,NOW

def full_receipt():
    r=receipt();p=r['events'][0]['payload']
    offer=dict(id=789,eventId=123,criterion={'englishLabel':'Match Odds'},betOfferType={'id':2},tags=['OFFERED_PREMATCH'],
        outcomes=[dict(type=t,status='OPEN',odds=o,betOfferId=789,changedDate=NOW.isoformat(),participant=n)
                  for t,o,n in [('OT_ONE',1800,'A Player'),('OT_TWO',2100,'B Player')]])
    p['betOffers'].append(offer);return r

class WinnerBinding(unittest.TestCase):
    def test_exact_pair_and_cloud_retention(self):
        r=full_receipt();q=Q.parse_receipt(r,NOW)[0];v=bind_winner(r,q)
        self.assertAlmostEqual(v['probability'],2.1/3.9)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);Q.capture_quotes(root,r,clock=NOW)
            p=next((root/Q.RELATIVE/'cloud-quotes').glob('*/*.json'));saved=C.read(p)
            self.assertEqual(bind_winner(saved,Q.parse_receipt(saved,NOW)[0]),v)
    def test_wrong_time_event_player_or_suspension_rejected(self):
        for kind in ('time','event','player','suspended','draw','duplicate'):
            r=full_receipt();q=Q.parse_receipt(r,NOW)[0];item=r['events'][0];o=item['payload']['betOffers'][1]
            if kind=='time':item['captured_at']=(NOW+timedelta(seconds=1)).isoformat()
            if kind=='event':o['eventId']=999
            if kind=='player':o['outcomes'][0]['participant']='Different Player'
            if kind=='suspended':o['outcomes'][0]['status']='SUSPENDED'
            if kind=='draw':o['outcomes'][1]['type']='OT_CROSS'
            if kind=='duplicate':item['payload']['betOffers'].append(copy.deepcopy(o))
            with self.assertRaises(ValueError,msg=kind):bind_winner(r,q)
    def test_winner_mass_unchanged_and_tilt_shortens(self):
        q=dict(market='total_games',line=22.5)
        p,means,solved=J.candidate_probabilities([.64,.61],.62,q,.07653680377710538)
        self.assertLess(means['MJ1_S'],means['MJ1'])
        for vals in p.values():self.assertAlmostEqual(sum(vals),1,12)
        self.assertLess(abs(J.M.joint(*solved) and J.M.handicap_module(ROOT).prob_match_best_of_3(*solved)-.62),.0005)

class FrozenRates(unittest.TestCase):
    def test_causal_window_and_no_missing_player_fallback(self):
        row=['2026-11-01',1,4,'Hard',2,1.,10,20,40,28,20,10,3,40,27,20,9,2]
        history=[{0:None}]*0+[row[:1]+row[1:] for _ in range(10)]
        a=R.fit(history,'Hard','2026-11-02')
        b=R.fit(history+[['2026-11-02']+row[1:]],'Hard','2026-11-02')
        self.assertEqual(a,b)
        cfg=C.read(ROOT/J.PROTOCOL)['point_calibration']
        self.assertEqual(len(R.rates(a,10,20,cfg)['calibrated']),2)
        with self.assertRaisesRegex(ValueError,'detailed'):R.rates(a,10,999,cfg)
        with self.assertRaises(ValueError):R.fit(history,'Clay','2026-11-02')

def shot_record():
    return dict(contract_id='contract',registered_at_utc=NOW.isoformat(),match_date='2026-11-02',kickoff_utc=(NOW+timedelta(hours=4)).isoformat(),
        league='epl',home_team='Arsenal',away_team='Chelsea',team='Arsenal',bookmaker='Bet365',line=12.5,
        odds={'over':2.1,'under':1.8},captured_at_utc={'over':NOW.isoformat(),'under':NOW.isoformat()},
        models={'opponent':dict(mean=13.5,alpha=.04942424,p_over=.55,selection_blockers={'over':'','under':''})})

def source_quotes(row):
    common=dict(event_id='123',kickoff_at=row['kickoff_utc'],match_date=row['match_date'],competition='Premier League',
        home_team='Arsenal',away_team='Chelsea',bookmaker='Bet365',source='moviodds_bet365',captured_at=NOW.isoformat())
    shots=[dict(common,team='Arsenal',market='TEAM_SHOTS',line='12.5',side=s,odds_decimal=str(row['odds'][s])) for s in ('over','under')]
    winners=[dict(common,market='MATCH_ODDS',side=s,odds_decimal=str(o)) for s,o in [('home',1.8),('draw',3.5),('away',4.2)]]
    return shots,winners

class ShotsBinding(unittest.TestCase):
    P=SimpleNamespace(PUB=SimpleNamespace(league_slug=lambda x:'epl' if x=='Premier League' else x))
    def test_strength_independent_of_v4(self):
        row=shot_record();a,b=source_quotes(row);strength=S.bind_strength(row,a,b,self.P)
        pred=S.predictions(row,strength,C.read(ROOT/S.PROTOCOL))
        self.assertGreater(pred['opponent_strength']['mean'],pred['opponent']['mean'])
    def test_future_different_event_and_changed_line_rejected(self):
        for kind in ('future','event','line','partial','price','stale'):
            row=shot_record();a,b=source_quotes(row)
            if kind=='future':
                for r in b:r['captured_at']=(NOW+timedelta(seconds=1)).isoformat()
            if kind=='event':
                for r in b:r['event_id']='999'
            if kind=='line':a[0]['line']='13.5'
            if kind=='partial':b.pop()
            if kind=='price':a[0]['odds_decimal']='2.4'
            if kind=='stale':
                for r in b:r['captured_at']=(NOW-timedelta(hours=3,seconds=1)).isoformat()
            with self.assertRaises(ValueError,msg=kind):S.bind_strength(row,a,b,self.P)
    def test_frozen_strength_side_and_original_blockers(self):
        row=shot_record();cfg=C.read(ROOT/S.PROTOCOL)
        home=S.predictions(row,dict(p_home=.6,p_away=.2),cfg)
        row['team']='Chelsea';away=S.predictions(row,dict(p_home=.6,p_away=.2),cfg)
        self.assertLess(away['opponent_strength']['mean'],home['opponent_strength']['mean'])
        row['models']['opponent']['selection_blockers']={'over':'injury;edge_below_3pct','under':'injury'}
        r=dict(source_record=row,forecasts=home,selections={})
        S.select_batch([r],cfg)
        self.assertFalse(any(s['selected'] for s in r['selections'].values()))
    def test_one_selection_first_batch_and_no_bet_retained(self):
        cfg=C.read(ROOT/S.PROTOCOL);base=shot_record();records=[]
        for i in range(3):
            r={**base,'contract_id':str(i)}
            records.append(dict(source_record=r,forecasts={a:dict(p_over=.7) for a in S.ARMS},selections={}))
        S.select_batch(records,cfg)
        self.assertEqual([sum(r['selections'][a]['selected'] for r in records) for a in S.ARMS],[1,1])
        for r in records:
            for a in S.ARMS:r['forecasts'][a]['p_over']=.5
            r['source_record']['odds']={'over':1.9,'under':1.9}
        S.select_batch(records,cfg)
        self.assertFalse(any(s['selected'] for r in records for s in r['selections'].values()))
    def test_reschedule_identity_and_exact_settlement(self):
        row=shot_record();fx=S.stable_key(row);moved={**row,'match_date':'2026-11-04'}
        self.assertEqual(fx,S.stable_key(moved))
        self.assertNotEqual(fx,S.stable_key({**row,'home_team':'Chelsea','away_team':'Arsenal'}))
        r=dict(source_record=row,fixture_key=fx,captured_at=NOW.isoformat())
        now=NOW+timedelta(days=3);ident=('2026-11-04','epl',S.team_key('Arsenal'),S.team_key('Chelsea'))
        res={ident:dict(home_shots=14,away_shots=8,observed_at=now.isoformat(),evidence_path='verified.json',source='verified')}
        self.assertEqual(S.settle(r,res,now)['side1_outcome'],1)
        self.assertEqual(S.settle(r,res,now)['result_date'],'2026-11-04')
        res[ident]['conflicting_counts']=['home_shots'];self.assertEqual(S.settle(r,res,now)['status'],'quarantined')

class Records(unittest.TestCase):
    def test_final_outcome_immutable_and_repeat_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);old={'x':dict(status='settled',side1_outcome=-1,actual=8)}
            C.preserve_outcomes(folder,old,NOW);before=(folder/'outcomes.json').read_bytes()
            C.preserve_outcomes(folder,{'x':dict(status='settled',side1_outcome=1,actual=15)},NOW)
            self.assertEqual(before,(folder/'outcomes.json').read_bytes())
            self.assertEqual(len(list((folder/'conflicts').glob('*.json'))),1)
    def test_paired_scores_include_no_bets_and_profit_only_selected(self):
        sel=dict(side=1,odds=2.,probability=.6,selected=True)
        records=[dict(id=str(i),fixture_key='same',captured_at=NOW.isoformat(),selections={'a':{**sel,'selected':i==0},'b':{**sel,'probability':.7,'selected':False}},
            display=dict(market='total_games',start=NOW.isoformat(),odds=[2.,2.])) for i in range(3)]
        outcomes={str(i):dict(status='settled',side1_outcome=1) for i in range(3)}
        result=C.summary(records,outcomes,('a','b'),NOW)
        self.assertEqual(result['arms']['a']['all']['stake'],1)
        self.assertEqual(result['arms']['b']['all']['stake'],0)
        self.assertEqual(result['arms']['a']['all']['calibration']['n'],1)
        self.assertEqual(result['arms']['a']['all']['calibration']['contracts'],3)
        self.assertAlmostEqual(result['arms']['a']['all']['calibration']['brier'],.16)

class CaptureLifecycle(unittest.TestCase):
    def test_atp_first_batch_rates_cutoff_settlement_and_missing_lock(self):
        import tennis_match_shape_prepare as prep
        from contextlib import ExitStack
        row=dict(tour_id=123,round_id=5,player1_id=10,player2_id=20,player1='A Player',player2='B Player',best_of=3,
            model_policy='category_corrected',official_category='Masters 1000',surface='I.hard',tour_name='Paris')
        packet=dict(rows=[row],payload_sha256='frozen')
        fit=dict(cutoff_exclusive=NOW.date().isoformat(),source_sha256={'native':'hash'})
        factory=SimpleNamespace(source={},get=lambda _:fit)
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root=Path(tmp);folder=root/J.RELATIVE
            reg=dict(registered_at=(NOW-timedelta(minutes=1)).isoformat(),fingerprints={},current_handicap_settings={},protocol=C.read(ROOT/J.PROTOCOL))
            C.immutable(folder/'registration.json',reg)
            stack.enter_context(patch.object(J.M,'fresh_components',return_value=(NOW,packet)))
            stack.enter_context(patch.object(prep,'readiness',return_value={'ready':True,'reason':'current'}))
            stack.enter_context(patch.object(J.M,'identity_index',return_value=None))
            stack.enter_context(patch.object(J,'resolve_quote',return_value=dict(edition_id=123,round_id=5,p1_id=10,p2_id=20)))
            games=stack.enter_context(patch.object(J.M,'game_index',return_value={}))
            stack.enter_context(patch.object(J.M,'settings',return_value=(None,None,{})))
            stack.enter_context(patch.object(J.M,'probabilities',return_value=({'current':(.7,0,.3)},{'current':24},0)))
            daily=stack.enter_context(patch.object(R,'DailyRates',return_value=factory))
            stack.enter_context(patch.object(R,'signature',return_value={}))
            stack.enter_context(patch.object(R,'rates',return_value={'calibrated':[.64,.62]}))
            result=J.capture(root,folder,reg,NOW,full_receipt())
            self.assertEqual(result['captured'],1)
            self.assertEqual(daily.call_args.args[2],NOW.date().isoformat())
            path=next((folder/'captures').glob('*.json'));before=path.read_bytes()
            self.assertEqual(J.capture(root,folder,reg,NOW,full_receipt())['captured'],0)
            self.assertEqual(before,path.read_bytes())
            record=C.read(path);grade=J.M.outcome(record,[dict(winner_id='10',loser_id='20',date='2026-11-02',result='7-6(4) 6-4')],NOW+timedelta(hours=5),J.M.file_sha(folder/'registration.json'))
            self.assertEqual(grade['status'],'settled')
            C.preserve_outcomes(folder,{record['id']:grade},NOW+timedelta(hours=5))
            stats=C.summary([record],{record['id']:grade},J.ARMS,NOW+timedelta(hours=5))
            self.assertEqual(stats['settled_fixtures'],1)
            self.assertEqual(stats['arms']['MJ1_S']['all']['calibration']['n'],1)
            other=Path(tmp)/'missing';C.immutable(other/'registration.json',reg)
            self.assertEqual(J.capture(root,other,reg,NOW,receipt())['captured'],0)
            self.assertEqual(len(list((other/'decisions').glob('*.json'))),1)
            self.assertEqual(J.capture(root,other,reg,NOW,full_receipt())['captured'],0)

    def test_shots_first_batch_capture_missing_lock_and_retained_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/S.RELATIVE;row=shot_record();row['model_fingerprint']='fixed'
            reg=dict(registered_at=(NOW-timedelta(minutes=1)).isoformat(),paired_model_fingerprint='fixed',protocol=C.read(ROOT/S.PROTOCOL))
            path=root/'data/football-form/team-shots-paired-reference.jsonl';path.parent.mkdir(parents=True)
            path.write_text(json.dumps(row)+'\n',encoding='utf-8');shots,winners=source_quotes(row)
            with patch.object(S,'csv_rows',side_effect=lambda p:shots if 'team-shots-odds' in p.name else winners):
                self.assertEqual(S.capture(root,folder,reg,NOW,ShotsBinding.P)['captured'],1)
                self.assertEqual(S.capture(root,folder,reg,NOW,ShotsBinding.P)['captured'],0)
                saved=next((folder/'captures').glob('*.json'));before=saved.read_bytes()
                record=C.read(saved);later=NOW+timedelta(hours=8)
                result={('2026-11-02','epl',S.team_key('Arsenal'),S.team_key('Chelsea')):dict(home_shots=14,away_shots=8,observed_at=later.isoformat(),evidence_path='verified.json',source='verified')}
                grade=S.settle(record,result,later);self.assertEqual(grade['status'],'settled')
                C.preserve_outcomes(folder,{record['id']:grade},later)
                report=C.summary([record],{record['id']:grade},S.ARMS,later)
                self.assertEqual(report['settled_fixtures'],1);self.assertEqual(saved.read_bytes(),before)
                missing=Path(tmp)/'missing'
                winners.clear();self.assertEqual(S.capture(root,missing,reg,NOW,ShotsBinding.P)['captured'],0)
                winners.extend(source_quotes(row)[1]);self.assertEqual(S.capture(root,missing,reg,NOW,ShotsBinding.P)['captured'],0)

if __name__=='__main__':unittest.main()
