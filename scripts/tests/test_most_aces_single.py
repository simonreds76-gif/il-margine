import copy,json,runpy,tempfile,unittest
from pathlib import Path
from datetime import datetime,timedelta
from unittest.mock import patch
from test_most_aces_reference import fixture,csvwrite,NOW,MODEL
import test_most_aces_reference as paired_tests
import tennis_most_aces_reference as P
import tennis_most_aces_single as S

class SingleTests(unittest.TestCase):
    def setUp(self):self.m,self.ident,self.q,self.sources=fixture()
    def prepare(self,root,books=1):
        report,receipt=paired_tests.Tests.prepare(self,root)
        self.m['prices']=self.m['prices'][:books];self.q=self.q[:books]
        csvwrite(root/'data/tennis-props/inbox/quotes.csv',self.q)
        P.atomic(root/'config/most-aces-single-book-v1.json',dict(contract=S.CONTRACT,enabled_at=(NOW-timedelta(minutes=1)).isoformat()))
        return report,receipt
    def capture(self,root,report,receipt,now=NOW):
        with patch.object(P,'check_receipt',return_value=(receipt,None)):return S.capture(root,report,now)
    def test_single_selected_and_paired_contract_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report,receipt=self.prepare(root);old=(root/'config/most-aces-fixed-reference-v1.json').read_bytes()
            result=self.capture(root,report,receipt);data=result['models'][MODEL]
            self.assertEqual((data['fixtures'],data['selected'],data['no_bets']),(1,1,0));self.assertIsNone(data['roi_pct'])
            row=P.ledger(root/S.REL)[0];self.assertEqual(row['bookmaker'],'Bet365');self.assertNotIn('reference',row)
            self.assertEqual(float(row['execution']['selected_odds']),2.25);self.assertFalse(row['gate_comparison_applicable'])
            self.assertEqual((root/'config/most-aces-fixed-reference-v1.json').read_bytes(),old)
            self.assertEqual(P.ledger(root/P.REL),[])
    def test_no_bets_retained_for_confidence_and_overround(self):
        for reason in ['confidence','overround']:
            with self.subTest(reason=reason),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);report,receipt=self.prepare(root)
                if reason=='confidence':self.m['prices'][0]['candidate']['eligibility_reason']='LOW_COUNT_CONFIDENCE'
                else:
                    self.q[0].update(player1_odds='1.2',draw_odds='1.5',player2_odds='1.2')
                    csvwrite(root/'data/tennis-props/inbox/quotes.csv',self.q)
                result=self.capture(root,report,receipt);data=result['models'][MODEL]
                self.assertEqual((data['fixtures'],data['selected'],data['no_bets']),(1,0,1))
                self.assertIn('LOW_COUNT_CONFIDENCE' if reason=='confidence' else 'OVERROUND_GT_20',data['records'][0]['reasons'])
                self.setUp()
    def test_single_then_two_books_frozen_overlap_not_added(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report,receipt=self.prepare(root);self.capture(root,report,receipt)
            path=root/S.REL/'observations.jsonl';old=path.read_bytes();old_time=P.ledger(root/S.REL)[0]['captured_at']
            m,ident,raw,sources=fixture();m['prices'][0]['candidate']['selected_odds']='9.0'
            later=NOW+timedelta(minutes=1);report=dict(generated_at=later.isoformat(),matches=[m])
            csvwrite(root/'data/tennis-props/inbox/quotes.csv',raw)
            with patch.object(P,'check_receipt',return_value=(receipt,None)):paired=P.capture(root,report,later)
            result=self.capture(root,report,receipt,later)
            self.assertEqual(path.read_bytes(),old);self.assertEqual(P.ledger(root/S.REL)[0]['captured_at'],old_time)
            self.assertEqual(P.ledger(root/P.REL)[0]['captured_at'],later.isoformat())
            self.assertEqual(float(P.ledger(root/P.REL)[0]['execution']['selected_odds']),2.55)
            self.assertEqual(result['models'][MODEL]['overlap_with_paired'],1)
            self.assertFalse(result['aggregate_eligible']);self.assertFalse(result['models'][MODEL]['aggregate_eligible'])
            self.assertTrue(result['models'][MODEL]['records'][0]['also_in_paired'])
            self.assertEqual(paired['models'][MODEL]['fixtures'],1)
    def test_paired_first_does_not_add_later_single(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report,receipt=self.prepare(root,3)
            with patch.object(P,'check_receipt',return_value=(receipt,None)):P.capture(root,report,NOW)
            self.q=self.q[:1];self.m['prices']=self.m['prices'][:1];csvwrite(root/'data/tennis-props/inbox/quotes.csv',self.q)
            result=self.capture(root,report,receipt)
            self.assertEqual(result['capture']['excluded'],{'already_in_paired_before_single':1});self.assertEqual(P.ledger(root/S.REL),[])
    def test_multiple_books_do_not_enter_single(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report,receipt=self.prepare(root,2)
            result=self.capture(root,report,receipt);self.assertEqual(result['capture']['excluded'],{'paired_coverage_available':1})
    def test_high_margin_second_book_does_not_remove_single_opportunity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report,receipt=self.prepare(root,2)
            self.q[1].update(player1_odds='1.01',draw_odds='1.01',player2_odds='8.0')
            csvwrite(root/'data/tennis-props/inbox/quotes.csv',self.q)
            result=self.capture(root,report,receipt);row=P.ledger(root/S.REL)[0]
            self.assertEqual((row['verified_books'],row['quality_books']),(2,1))
            self.assertEqual(row['bookmaker'],'Bet365');self.assertTrue(row['selection']['selected'])
            self.assertEqual(row['excluded_vectors'][0]['book'],'Grosvenor')
            self.assertEqual(result['models'][MODEL]['cohorts'],{'multiple_quotes_one_quality':1})
            with patch.object(P,'check_receipt',return_value=(receipt,None)):P.capture(root,report,NOW)
            self.assertEqual(P.ledger(root/P.REL),[])
    def test_all_high_margin_vectors_retained_as_no_bet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report,receipt=self.prepare(root,2)
            for q in self.q:q.update(player1_odds='1.2',draw_odds='1.5',player2_odds='1.2')
            csvwrite(root/'data/tennis-props/inbox/quotes.csv',self.q)
            result=self.capture(root,report,receipt);row=P.ledger(root/S.REL)[0]
            self.assertEqual(row['quality_books'],0);self.assertFalse(row['selection']['selected'])
            self.assertIn('OVERROUND_GT_20',row['selection']['reasons'])
            self.assertEqual(result['models'][MODEL]['no_bets'],1);self.assertEqual(result['models'][MODEL]['stake_units'],0)
    def test_repeat_and_reschedule_dedup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report,receipt=self.prepare(root);self.capture(root,report,receipt)
            path=root/S.REL/'observations.jsonl';old=path.read_bytes()
            self.capture(root,report,receipt)
            self.m['date']='2026-11-15';self.q[0]['date']='2026-11-15';csvwrite(root/'data/tennis-props/inbox/quotes.csv',self.q)
            result=self.capture(root,report,receipt);self.assertEqual(path.read_bytes(),old);self.assertEqual(result['capture']['excluded'],{'already_recorded':1})
    def test_invalid_source_report_future_started_and_missing_identity(self):
        for case in ['source','report','future','started','identity','before_registration']:
            with self.subTest(case=case),tempfile.TemporaryDirectory() as tmp:
                self.setUp();root=Path(tmp);report,receipt=self.prepare(root)
                if case=='report':report['generated_at']=(NOW-timedelta(minutes=3)).isoformat()
                if case=='future':self.m['prices'][0]['candidate']['registered_at_utc']=(NOW+timedelta(seconds=1)).isoformat()
                if case=='started':self.m['prices'][0]['candidate']['match_start_utc']=(NOW-timedelta(seconds=1)).isoformat()
                if case=='identity':self.m['tournament_players']=[]
                if case=='before_registration':P.atomic(root/'config/most-aces-single-book-v1.json',dict(contract=S.CONTRACT,enabled_at=(NOW+timedelta(seconds=1)).isoformat()))
                with patch.object(P,'check_receipt',return_value=(receipt,'bookmaker_check_stale' if case=='source' else None)):S.capture(root,report,NOW)
                self.assertEqual(P.ledger(root/S.REL),[])
    def test_newer_removed_quote_cannot_resurrect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report,receipt=self.prepare(root)
            self.q[0]['capture_ts']=NOW.isoformat();csvwrite(root/'data/tennis-props/inbox/quotes.csv',self.q)
            self.capture(root,report,receipt);self.assertEqual(P.ledger(root/S.REL),[])
    def test_actual_settler_includes_no_bets_for_calibration_only(self):
        C=runpy.run_path(str(Path(__file__).resolve().parents[1]/'tennis-props-settle-shadow.py'))
        shadow=runpy.run_path(str(Path(__file__).resolve().parents[1]/'tennis-most-aces-shadow.py'))
        for no_bet in [False,True]:
            with self.subTest(no_bet=no_bet),tempfile.TemporaryDirectory() as tmp:
                self.setUp();root=Path(tmp);report,receipt=self.prepare(root)
                if no_bet:self.m['prices'][0]['candidate']['eligibility_reason']='LOW_COUNT_CONFIDENCE'
                self.capture(root,report,receipt);original=(root/S.REL/'observations.jsonl').read_bytes()
                game=dict(winner_id='1',loser_id='2',tour_id='99',round_id='12',date='2026-11-15',result='6-4 6-4')
                stat=dict(winner_id='1',loser_id='2',tour_id='99',round_id='12',w_ace='5',l_ace='12')
                csvwrite(root/'data/oncourt/games_atp.csv',[game]);csvwrite(root/'data/oncourt/stat_atp.csv',[stat])
                idx=C['load_oncourt_index'](root/'data/oncourt',S.pending(root))
                class Clock(datetime):
                    @classmethod
                    def now(cls,tz=None):return NOW+timedelta(days=2)
                with patch.dict(shadow['settle'].__globals__,datetime=Clock):
                    self.assertEqual(S.settle(root,idx,C,shadow,NOW+timedelta(days=2)),1)
                    self.assertEqual(S.settle(root,idx,C,shadow,NOW+timedelta(days=2)),0)
                self.assertEqual((root/S.REL/'observations.jsonl').read_bytes(),original)
                d=P.read(root/S.REL/'report.json',{})['models'][MODEL]
                self.assertEqual(d['settled_fixtures'],1);self.assertEqual(d['calibration']['model']['n'],1)
                self.assertEqual(d['stake_units'],int(not no_bet));self.assertEqual(d['pnl_units'],0 if no_bet else 1.25)
                self.assertEqual(d['roi_pct'],None if no_bet else 125.);self.assertEqual(d['history']['profit'],d['pnl_units'])
                self.assertEqual(d['records'][0]['paper_pnl'],0 if no_bet else 1.25)
    def test_bad_result_identity_and_overdue_remain_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report,receipt=self.prepare(root);self.capture(root,report,receipt)
            pair=lambda a,b:tuple(sorted((P.norm(a),P.norm(b))))
            idx={('ATP',2026,pair(self.m['player1'],self.m['player2'])):[dict(_tour_id='98',round_id='12')]}
            self.assertEqual(S.settle(root,idx,dict(pair_key=pair),{},NOW+timedelta(days=3)),0)
            d=P.read(root/S.REL/'report.json',{})['models'][MODEL];self.assertEqual(d['overdue'],1);self.assertIsNone(d['roi_pct'])
    def test_frozen_registration_and_failure_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report,receipt=self.prepare(root);self.capture(root,report,receipt)
            spec=P.read(root/'config/most-aces-single-book-v1.json',{});spec['contract']['gap_pp']=50;P.atomic(root/'config/most-aces-single-book-v1.json',spec)
            with self.assertRaisesRegex(ValueError,'single_book_registration_mismatch'):self.capture(root,report,receipt)
            with patch.object(S,'capture',side_effect=AttributeError('bad row')):self.assertIsNone(S.safe_capture(root,report))
            self.assertEqual(P.read(root/S.REL/'report.json',{})['capture']['status'],'BLOCKED')
    def test_monitor_and_weekly_labels_no_aggregate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report,receipt=self.prepare(root);result=self.capture(root,report,receipt)
            cards=S.monitor_rows(result);text=S.weekly_text(result)
            self.assertEqual(len(cards),2);self.assertTrue(all(not c['aggregate_eligible'] for c in cards))
            self.assertTrue(all(c['roi'] is None for c in cards));self.assertIn('ROI n/a',text)
            self.assertIn('Gate comparison not applicable',text);self.assertIn('never add totals',text)

if __name__=='__main__':unittest.main()
