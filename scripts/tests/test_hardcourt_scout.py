import ast, csv, importlib.util, json, os, sys, tempfile, unittest
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tennis_hardcourt_scout as s


class ScoutTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path.cwd());self.root=Path(self.temp.name)
        self.now=datetime(2026,10,13,10,tzinfo=timezone.utc)
        for name in s.MODEL_FILES:
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('VERSION = "test"\n',encoding='utf8')
        s.register(self.root,self.now-timedelta(minutes=1))
        self.row=dict(tour_id=101,round_id=5,player1_id=1,player2_id=2,player1='First Player',player2='Second Player',
                      tour_name='Example Challenger',surface='Hard',official_category='Challenger',
                      model_policy='category_corrected',source_contract='test',p1_win_prob=.6,confidence='high',data_coverage_tag='HIGH')
        self.q=dict(captured_at=(self.now-timedelta(minutes=30)).isoformat(),kickoff_iso='2026-10-14T12:00:00+00:00',
                    bookmaker='Pinnacle',league='Challenger',league_name='Example Challenger',player1_name='First Player',
                    player2_name='Second Player',odds1=1.88,odds2=2.1,capture_mode='prematch')
        self.write_quotes([self.q])
    def tearDown(self):
        assert self.root.resolve().is_relative_to(Path.cwd().resolve())
        self.temp.cleanup()
    def write_quotes(self,rows):
        p=self.root/'data/pinnacle-history/pinnacle-history-20261013-test.csv';p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('w',newline='',encoding='utf8') as f:
            w=csv.DictWriter(f,fieldnames=self.q);w.writeheader();w.writerows(rows)
    def capture(self,rows=None):return s.capture(self.root,rows or [self.row],self.now,self.now.date().isoformat())
    def game(self,rows):
        p=self.root/'data/oncourt/games_atp.csv';p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('w',newline='',encoding='utf8') as f:
            w=csv.DictWriter(f,fieldnames=['tour_id','round_id','winner_id','loser_id','date','result']);w.writeheader();w.writerows(rows)
    def result(self,winner='1',score='6-4 6-4',round_id='5'):
        return dict(tour_id='101',round_id=round_id,winner_id=winner,loser_id='2' if winner=='1' else '1',date='2026-10-14',result=score)
    def report(self):return s.summarize(self.root,now=self.now+timedelta(days=2))
    def test_locked_first_capture_and_no_historical_enrolment(self):
        self.assertEqual(self.capture()['selected'],1)
        path=next((self.root/s.RELATIVE/'captures').glob('*.json'));raw=path.read_bytes()
        self.row['p1_win_prob']=.61;self.capture();self.assertEqual(path.read_bytes(),raw)
        with self.assertRaises(ValueError):s.capture(self.root,[self.row],self.now-timedelta(days=1),'2026-10-12')
        with self.assertRaises(ValueError):s.capture(self.root,[self.row],self.now,'2026-10-12')
    def test_prices_fresh_identity_reverse_and_conflicts(self):
        q=dict(self.q,player1_name='Second Player',player2_name='First Player',odds1=2.1,odds2=1.88)
        self.write_quotes([q]);self.assertEqual(self.capture()['selected'],1)
        result,reason=s.match_quote(self.row,[self.q,dict(self.q,odds1=1.9)])
        self.assertIsNone(result);self.assertEqual(reason,'conflicting_prices')
        self.write_quotes([dict(self.q,captured_at='2026-10-13T01:00:00+00:00')]);self.assertFalse(s.quotes(self.root,self.now)[0])
        self.write_quotes([dict(self.q,kickoff_iso='2026-10-13T09:00:00+00:00')]);self.assertFalse(s.quotes(self.root,self.now)[0])
    def test_outside_scope_and_rejected_selection_are_separate(self):
        self.assertEqual(self.capture([dict(self.row,surface='Clay')])['captured'],0)
        self.assertEqual(self.capture([dict(self.row,official_category='ATP250')])['captured'],0)
        self.assertEqual(self.capture([dict(self.row,confidence='medium')])['captured'],1)
        r=self.report();self.assertEqual(r['registered_fixtures'],1);self.assertEqual(r['selections_total'],0)
        self.assertIsNone(r['roi_pct'])
    def test_duplicate_rows_fail_before_writes(self):
        with self.assertRaises(ValueError):self.capture([self.row,self.row])
        self.assertFalse(list((self.root/s.RELATIVE/'captures').glob('*.json')))
    def test_frozen_model_change_is_blocked(self):
        (self.root/s.MODEL_FILES[1]).write_text('VERSION = "changed"')
        with self.assertRaises(ValueError):self.capture()
        s.capture_current(self.root,[self.row],as_of='2026-10-13')
        self.assertEqual(s.read(self.root/s.RELATIVE/'capture-status.json')['state'],'BLOCKED')
    def test_settlement_corrections_and_paper_roi(self):
        self.capture();r=self.report();self.assertEqual(r['pending'],1);self.assertIsNone(r['roi_pct'])
        self.game([self.result()]);r=self.report();self.assertEqual(r['wins'],1);self.assertAlmostEqual(r['roi_pct'],88)
        self.assertEqual(r['actual_stake'],0);self.assertEqual(r['stake_units'],1)
        self.game([self.result('2')]);r=self.report();self.assertEqual(r['losses'],1);self.assertEqual(r['roi_pct'],-100)
        self.assertTrue(list((self.root/s.RELATIVE/'outcome-history').glob('*.json')))
        self.game([self.result(score='6-4 2-1 RET')]);r=self.report();self.assertEqual(r['void'],1);self.assertEqual(r['stake_units'],0);self.assertIsNone(r['roi_pct'])
    def test_result_identity_ambiguity_and_unfinished(self):
        self.capture();self.game([self.result(round_id='6')]);self.assertEqual(self.report()['pending'],1)
        self.game([self.result(),self.result()]);self.assertEqual(self.report()['quarantined'],1)
        self.game([self.result(score='6-4')]);self.assertEqual(self.report()['pending'],1)
        self.game([dict(self.result(),date='2026-10-01')]);self.assertEqual(self.report()['quarantined'],1)
    def test_valid_completed_scores(self):
        for score in ['6-4 6-4','7-6(5) 4-6 7-5','6-7(2) 6-0 6-3']:self.assertTrue(s.completed(score))
        for score in ['6-4','6-4 6-4 6-4','6-4 6-5','4-6 4-6','6-4 RET']:self.assertFalse(s.completed(score))
    def test_weekly_reports_pending_void_and_no_false_roi(self):
        self.capture();text=s.weekly_text(self.report());self.assertIn('PAPER ONLY',text);self.assertIn('ROI awaits',text)
        self.assertIn('1 pending',text);self.assertIn('zero real stake',text)
    def test_late_daily_price_save_cannot_reuse_old_forecasts(self):
        self.assertIn('No fresh',s.capture_latest(self.root,self.now))
        p=self.root/'data/tennis-ml-research/components/2026-10-13/old.json';p.parent.mkdir(parents=True)
        p.write_text(json.dumps({'captured_at':'2026-10-13T05:00:00+00:00','rows':[self.row]}))
        self.assertIn('No fresh',s.capture_latest(self.root,self.now))
        p.write_text(json.dumps({'captured_at':self.now.isoformat(),'rows':[self.row],'model_file_sha256':'wrong'}))
        self.assertIn('version mismatch',s.capture_latest(self.root,self.now))
        packet={'captured_at':self.now.isoformat(),'rows':[self.row],
                'model_file_sha256':s.sha256((self.root/s.MODEL_FILES[0]).read_bytes()).hexdigest(),
                'payload_sha256':s.sha256(json.dumps([self.row],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()}
        p.write_text(json.dumps(packet))
        with patch.object(s,'capture_current',return_value='captured') as collect:
            self.assertEqual(s.capture_latest(self.root,self.now),'captured')
            self.assertEqual(collect.call_args.kwargs['forecast_generated_at'],self.now.isoformat())
        packet['payload_sha256']='wrong';p.write_text(json.dumps(packet))
        with self.assertRaises(ValueError):s.capture_latest(self.root,self.now)
    def test_source_forecast_timestamp_locked_and_stale_rejected(self):
        with self.assertRaises(ValueError):
            s.capture(self.root,[self.row],self.now,self.now.date().isoformat(),(self.now-timedelta(hours=3)).isoformat())
        generated=self.now-timedelta(seconds=30)
        s.capture(self.root,[self.row],self.now,self.now.date().isoformat(),generated.isoformat())
        packet=s.read(next((self.root/s.RELATIVE/'captures').glob('*.json')))
        self.assertEqual(packet['forecast_generated_at'],generated.isoformat())
    def test_daily_capture_hook_has_no_close_or_dry_run_side_effects(self):
        tree=ast.parse((Path(__file__).resolve().parents[1]/'pinnacle-capture-history.py').read_text(encoding='utf-8-sig'))
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        hook=next(n for n in main.body if isinstance(n,ast.If) and 'args.capture_mode' in ast.unparse(n.test))
        code=compile(ast.Module(body=[hook],type_ignores=[]),'daily_hook','exec')
        with patch.object(s,'capture_latest',return_value='checked') as collect:
            for mode,dry in [('close',False),('daily',True),('daily',False)]:
                exec(code,{'Path':Path,'__file__':str(self.root/'scripts/pinnacle-capture-history.py'),
                           'args':SimpleNamespace(capture_mode=mode,dry_run=dry),'print':lambda *args:None})
            collect.assert_called_once_with(self.root)


if __name__=='__main__':unittest.main()
