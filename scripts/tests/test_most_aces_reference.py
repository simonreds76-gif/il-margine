import copy,csv,json,sys,tempfile,unittest,runpy
from pathlib import Path
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tennis_most_aces_reference as M

NOW=datetime(2026,11,14,11,0,tzinfo=timezone.utc)
MODEL=next(iter(M.MODELS))

def csvwrite(path, rs):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)

def fixture():
    p=[.359558,.058411,.582031];quotes=[];prices=[]
    for book,odds in [('Bet365',[1.727272727,13,2.25]),('Grosvenor',[1.68,10.5,2.55]),('Sisal IT',[1.65,16,2.25])]:
        q=dict(bookmaker=book,player1='Taylor Fritz',player2='Thiago Agustin Tirante',date='2026-11-14',tour='ATP',tournament='Stockholm',
               capture_ts=(NOW-timedelta(seconds=10)).isoformat(),match_start_utc=(NOW+timedelta(hours=2)).isoformat(),
               player1_odds=str(odds[0]),draw_odds=str(odds[1]),player2_odds=str(odds[2]))
        r=dict(q,model=MODEL,registered_at_utc=NOW.isoformat(),price_captured_at=q['capture_ts'],forecast_generated_at=(NOW-timedelta(minutes=5)).isoformat(),
               p_player1=str(p[0]),p_draw=str(p[1]),p_player2=str(p[2]),eligibility_reason='ELIGIBLE_SHADOW',recommended_side='P2',selected_odds=str(odds[2]))
        quotes.append(q);prices.append(dict(candidate=r))
    match=dict(model=MODEL,player1='Taylor Fritz',player2='Thiago Agustin Tirante',date='2026-11-14',tour='ATP',tournament='Stockholm',round='F',
               p_player1=str(p[0]),p_draw=str(p[1]),p_player2=str(p[2]),generated_at_utc=(NOW-timedelta(minutes=5)).isoformat(),prices=prices,
               tournament_players=[dict(player='Taylor Fritz',player_id='1',tour_id='99'),dict(player='Thiago Agustin Tirante',player_id='2',tour_id='99')])
    ident=dict(player_names=[M.norm(match['player1']),M.norm(match['player2'])],player_ids=['1','2'],tour_id='99',round_id='12',edition_date='2026-11-08')
    return match,ident,quotes,{q['bookmaker']:{'status':'QUOTES_CAPTURED'} for q in quotes}

class Tests(unittest.TestCase):
    def setUp(self): self.m,self.ident,self.q,self.sources=fixture()
    def decide(self):return M.decide(self.m,self.ident,self.q,self.sources,NOW)
    def test_better_price_fixed_reference(self):
        d=self.decide();self.assertEqual(d['execution']['bookmaker'],'Grosvenor');self.assertEqual(float(d['execution']['selected_odds']),2.55)
        self.assertFalse(d['baseline']['selected']);self.assertTrue(d['fixed_reference']['selected']);self.assertAlmostEqual(d['reference_gap_pp'],18.813,places=2)
    def test_one_book_not_paired(self):
        self.m['prices']=self.m['prices'][:1]
        with self.assertRaisesRegex(ValueError,'fewer_than_two'):self.decide()
    def test_future_quote(self):
        for item in self.m['prices'][:2]:item['candidate']['price_captured_at']=(NOW+timedelta(seconds=1)).isoformat()
        with self.assertRaisesRegex(ValueError,'fewer_than_two'):self.decide()
    def test_late_observation(self):
        for item in self.m['prices'][:2]:item['candidate']['registered_at_utc']=(NOW+timedelta(seconds=1)).isoformat()
        with self.assertRaisesRegex(ValueError,'fewer_than_two'):self.decide()
    def test_missing_forecast(self):
        for item in self.m['prices']:item['candidate']['forecast_generated_at']=''
        with self.assertRaisesRegex(ValueError,'fewer_than_two'):self.decide()
    def test_stale_and_started(self):
        for item in self.m['prices']:item['candidate']['match_start_utc']=(NOW-timedelta(seconds=1)).isoformat()
        with self.assertRaisesRegex(ValueError,'fewer_than_two'):self.decide()
    def test_kickoff_conflict_blocks_fixture(self):
        self.q[0]['match_start_utc']=(NOW+timedelta(hours=3)).isoformat()
        with self.assertRaisesRegex(ValueError,'conflicting_current_kickoff'):self.decide()
    def test_no_resurrect_removed_quote(self):
        for q in self.q[:2]:q['capture_ts']=NOW.isoformat()
        with self.assertRaisesRegex(ValueError,'fewer_than_two'):self.decide()
    def test_different_p_not_paired(self):
        for item in self.m['prices'][:2]:item['candidate'].update(p_player1='.4',p_player2='.541589')
        with self.assertRaisesRegex(ValueError,'fewer_than_two'):self.decide()
    def test_confidence_preserved(self):
        self.m['prices'][1]['candidate']['eligibility_reason']='LOW_COUNT_CONFIDENCE'
        d=self.decide();self.assertFalse(d['baseline']['selected']);self.assertFalse(d['fixed_reference']['selected']);self.assertEqual(len(d['reference_books']),3)
    def test_reversed_quote(self):
        r=self.m['prices'][1]['candidate'];q=self.q[1]
        for x in (r,q):x['player1'],x['player2']=x['player2'],x['player1'];x['player1_odds'],x['player2_odds']=x['player2_odds'],x['player1_odds']
        r['p_player1'],r['p_player2']=r['p_player2'],r['p_player1']
        self.assertTrue(self.decide()['fixed_reference']['selected'])
    def test_invalid_new_prices(self):
        self.q[1]['player2_odds']='NaN'
        with self.assertRaisesRegex(ValueError,'invalid_current_quote'):self.decide()
    def prepare(self,root):
        spec=dict(contract=M.CONTRACT,enabled_at=(NOW-timedelta(minutes=1)).isoformat())
        M.atomic(root/'config/most-aces-fixed-reference-v1.json',spec)
        csvwrite(root/'data/oncourt/players_atp.csv',[dict(id='1',name='Taylor Fritz'),dict(id='2',name='Thiago Agustin Tirante')])
        csvwrite(root/'data/oncourt/tours_atp.csv',[dict(id='99',name='Stockholm',date='2026-11-08')])
        csvwrite(root/'data/oncourt/today_atp.csv',[dict(tour_id='99',round_id='12',player1_id='1',player2_id='2',result='',live='0')])
        csvwrite(root/'data/tennis-props/inbox/quotes.csv',self.q)
        receipt=dict(sources=self.sources,artifacts={'most_aces':{'name':'quotes.csv'}})
        return dict(generated_at=NOW.isoformat(),matches=[self.m]),receipt
    def test_append_once_reschedule_and_no_history_rewrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report,receipt=self.prepare(root)
            with patch.object(M,'check_receipt',return_value=(receipt,None)):
                M.capture(root,report,NOW);path=root/M.REL/'observations.jsonl';old=path.read_bytes()
                self.m['prices'][1]['candidate']['selected_odds']='9.0'
                M.capture(root,report,NOW);self.assertEqual(path.read_bytes(),old)
                # A rescheduled kickoff and date do not create a second bet for same edition/round/IDs.
                self.m['date']='2026-11-15';M.capture(root,report,NOW);self.assertEqual(path.read_bytes(),old)
            d=M.ledger(root/M.REL)[0];self.assertFalse(d['baseline']['selected']);self.assertTrue(d['fixed_reference']['selected'])
    def test_independent_missing_identity_and_missing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report,receipt=self.prepare(root);bad=copy.deepcopy(self.m);bad['model']=list(M.MODELS)[1];bad['tournament_players']=[]
            report['matches'].append(bad)
            with patch.object(M,'check_receipt',return_value=(receipt,None)):
                r=M.capture(root,report,NOW);self.assertEqual(r['capture']['added'],1);self.assertEqual(r['capture']['excluded']['verified_player_ids_missing'],1)
            with patch.object(M,'check_receipt',return_value=(receipt,'bookmaker_check_incomplete')):
                r=M.capture(root,report,NOW);self.assertEqual(r['capture']['status'],'BLOCKED')
    def test_settlement_pnl_calibration_and_repeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report,receipt=self.prepare(root)
            with patch.object(M,'check_receipt',return_value=(receipt,None)):M.capture(root,report,NOW)
            before=(root/M.REL/'observations.jsonl').read_bytes()
            pair=lambda a,b:tuple(sorted((M.norm(a),M.norm(b))))
            match=dict(_tour_id='99',round_id='12',winner_name='Taylor Fritz',loser_name='Thiago Agustin Tirante',tourney_date='20261114',score='6-4 6-4',_settlement_source='oncourt')
            idx={('ATP',2026,pair(self.m['player1'],self.m['player2'])):[match]}
            def settle(rs,*a,**kw):rs[0].update(settlement_status='settled',outcome='P2',actual_player1_aces='5',actual_player2_aces='12',result='win',pnl='1.550',settlement_note='test_exact_fixture')
            C=dict(pair_key=pair,parse_sackmann_date=lambda s:datetime.strptime(s,'%Y%m%d').date());S=dict(pair_key=pair,settle=settle)
            self.assertEqual(M.settle(root,idx,C,S,NOW+timedelta(hours=5)),1)
            self.assertEqual(M.settle(root,idx,C,S,NOW+timedelta(hours=5)),0)
            self.assertEqual((root/M.REL/'observations.jsonl').read_bytes(),before)
            r=M.read(root/M.REL/'report.json',{});d=r['models'][MODEL]
            self.assertEqual(d['arms']['fixed_reference']['pnl_units'],1.55);self.assertEqual(d['arms']['fixed_reference']['history']['profit'],1.55)
            self.assertEqual(d['arms']['baseline']['stake_units'],0);self.assertTrue(d['calibration_identical_between_gates'])
            self.assertEqual(len(M.monitor_rows(r)),4);self.assertIn('ROI +155.00%',M.weekly_text(r))
    def test_wrong_edition_cannot_settle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report,receipt=self.prepare(root)
            with patch.object(M,'check_receipt',return_value=(receipt,None)):M.capture(root,report,NOW)
            pair=lambda a,b:tuple(sorted((M.norm(a),M.norm(b))))
            idx={('ATP',2026,pair(self.m['player1'],self.m['player2'])):[dict(_tour_id='98',round_id='12')]}
            self.assertEqual(M.settle(root,idx,dict(pair_key=pair),{},NOW+timedelta(hours=5)),0)
    def test_registration_cannot_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report,receipt=self.prepare(root)
            with patch.object(M,'check_receipt',return_value=(receipt,None)):M.capture(root,report,NOW)
            s=M.read(root/'config/most-aces-fixed-reference-v1.json',{});s['contract']['gap_pp']=30;M.atomic(root/'config/most-aces-fixed-reference-v1.json',s)
            with self.assertRaisesRegex(ValueError,'registration_mismatch'):M.capture(root,report,NOW)

    def test_actual_settler_and_retirement_contract(self):
        shadow=runpy.run_path(str(Path(__file__).resolve().parents[1]/'tennis-most-aces-shadow.py'))
        pair=shadow['pair_key']
        C=dict(pair_key=pair,parse_sackmann_date=lambda s:datetime.strptime(s,'%Y%m%d').date())
        for score,aces,expected,profit in [('6-4 6-4',('5','12'),'settled',1.55),('W/O',('',''),'void',0),('6-4 2-1 RET',('5','12'),None,None),('6-4 6-4',('','12'),None,None)]:
            with self.subTest(score=score,aces=aces),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);report,receipt=self.prepare(root)
                with patch.object(M,'check_receipt',return_value=(receipt,None)):M.capture(root,report,NOW)
                original=(root/M.REL/'observations.jsonl').read_bytes()
                match=dict(_tour_id='99',round_id='12',winner_name='Taylor Fritz',loser_name='Thiago Agustin Tirante',tourney_date='20261114',tourney_name='Stockholm',_settlement_source='oncourt',score=score,w_ace=aces[0],l_ace=aces[1])
                idx={('ATP',2026,pair(self.m['player1'],self.m['player2'])):[match]}
                class Clock(datetime):
                    @classmethod
                    def now(cls,tz=None):return NOW+timedelta(hours=5)
                # Reuse the real production settlement function; only its clock is fixed.
                with patch.dict(shadow['settle'].__globals__,datetime=Clock):
                    n=M.settle(root,idx,C,shadow,NOW+timedelta(hours=5))
                    self.assertEqual(n,int(expected is not None))
                    self.assertEqual(M.settle(root,idx,C,shadow,NOW+timedelta(hours=5)),0)
                out=M.read(root/M.REL/'outcomes.json',{})
                if expected:
                    result=next(iter(out.values()));self.assertEqual(result['settlement_status'],expected);self.assertAlmostEqual(float(result['pnl']),profit)
                self.assertEqual((root/M.REL/'observations.jsonl').read_bytes(),original)

    def test_null_roi_and_failure_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report,receipt=self.prepare(root)
            with patch.object(M,'check_receipt',return_value=(receipt,None)):
                result=M.capture(root,report,NOW)
            self.assertTrue(all(r['roi'] is None for r in M.monitor_rows(result)))
            self.assertIn('ROI n/a',M.weekly_text(result))
            with patch.object(M,'capture',side_effect=AttributeError('bad row')),patch.object(M,'failure',side_effect=OSError('unwritable')):
                self.assertIsNone(M.safe_capture(root,report))

    def test_real_index_uses_actual_game_date_and_exact_round(self):
        C=runpy.run_path(str(Path(__file__).resolve().parents[1]/'tennis-props-settle-shadow.py'))
        S=runpy.run_path(str(Path(__file__).resolve().parents[1]/'tennis-most-aces-shadow.py'))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report,receipt=self.prepare(root)
            with patch.object(M,'check_receipt',return_value=(receipt,None)):M.capture(root,report,NOW)
            source=root/'data/oncourt'
            # Edition began Nov8, capture Nov14, played Nov15 after rescheduling.
            game=dict(winner_id='1',loser_id='2',tour_id='99',round_id='12',date='2026-11-15',result='6-4 6-4')
            stat=dict(winner_id='1',loser_id='2',tour_id='99',round_id='12',w_ace='5',l_ace='12')
            csvwrite(source/'games_atp.csv',[dict(game,round_id='11',date='2026-11-12'),game])
            csvwrite(source/'stat_atp.csv',[dict(stat,round_id='11',w_ace='20'),stat])
            idx=C['load_oncourt_index'](source,M.pending(root))
            class Clock(datetime):
                @classmethod
                def now(cls,tz=None):return NOW+timedelta(days=2)
            with patch.dict(S['settle'].__globals__,datetime=Clock):self.assertEqual(M.settle(root,idx,C,S,NOW+timedelta(days=2)),1)
            result=next(iter(M.read(root/M.REL/'outcomes.json',{}).values()))
            self.assertEqual(result['actual_date'],'2026-11-15');self.assertEqual(result['outcome'],'P2')
            self.assertEqual(M.ledger(root/M.REL)[0]['date'],'2026-11-14')

if __name__=='__main__':unittest.main()
