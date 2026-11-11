import csv
import json
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tennis_indoor_expansion as M
import tennis_indoor_paper as BASE
from tennis_paper_quote_identity import tables

class Expansion(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.now=datetime(2026,11,11,12,tzinfo=timezone.utc)
        self.hashes=patch.object(M,'hashes',return_value={'model':'fixed'});self.hashes.start()
        self.env=patch.object(M,'environment',return_value={});self.env.start()
        p=self.root/'scripts';p.mkdir();(p/'tennis_source_contract.py').write_text("VERSION='contract'\n")
        p=self.root/'config';p.mkdir();(p/'indoor-expansion-paper-v1.json').write_text('{"actual_stake":0,"alerts":false}')
        p=self.root/'data/oncourt';p.mkdir(parents=True)
        (p/'tours_atp.csv').write_text('id,name,date\n10,Stockholm,2026-11-09\n')
        (p/'today_atp.csv').write_text('tour_id,round_id,player1_id,player2_id,result,live\n10,3,1,2,,\n')
        (p/'games_atp.csv').write_text('tour_id,round_id,winner_id,loser_id,date,result\n')
        self.row=dict(tour_id=10,round_id=3,player1_id=1,player2_id=2,player1='First Player',player2='Second Player',tour_name='Stockholm',event_key='stockholm',surface='I.hard',official_category='ATP250',best_of=3,confidence='high',source_contract='contract',model_policy='category_corrected',p1_win_prob=.60)
        self.q=dict(odds1='1.90',odds2='2.00',captured_at=(self.now-timedelta(minutes=1)).isoformat(),kickoff_iso=(self.now+timedelta(hours=1)).isoformat(),player1_name='First Player',player2_name='Second Player',bookmaker='Pinnacle',league='ATP',league_name='ATP Stockholm - Qualifiers',is_live='false')
        self.write_quote()
        M.register(self.root,self.now-timedelta(minutes=2))
    def tearDown(self):
        self.hashes.stop();self.env.stop();tables.cache_clear();self.tmp.cleanup()
    def write_quote(self):
        p=self.root/'data/pinnacle-history';p.mkdir(parents=True,exist_ok=True)
        with (p/'pinnacle-history-20261111-120000.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=self.q);w.writeheader();w.writerow(self.q)
    def capture(self):return M.capture(self.root,[self.row],self.now,self.now.isoformat())
    def test_250_and_500_including_qualifying(self):
        for category in ('ATP250','ATP500'):
            self.assertTrue(M.select(.6,dict(odds1=1.9,odds2=2),dict(self.row,official_category=category))['qualifies'])
        self.assertEqual(self.capture()['counts']['captured'],1)
        self.assertEqual(M.summarize(self.root,self.now)['qualifying_fixtures'],1)
    def test_numerical_parity_with_registered_masters_gates(self):
        for p in (.1,.25,.45,.60,.75,.9):
            for prices in ((1.2,5),(1.9,2),(2.64,1.505)):
                q=dict(odds1=prices[0],odds2=prices[1])
                self.assertEqual(M.select(p,q,self.row),BASE.select(p,q,dict(self.row,official_category='Masters 1000')))
    def test_other_categories_outside_expansion(self):
        for cat in ('Masters 1000','Challenger','Grand Slam'):
            self.row['official_category']=cat;self.assertEqual(self.capture()['scope_fixtures'],0)
    def test_pre_registration_forecast_rejected(self):
        with self.assertRaises(ValueError):M.capture(self.root,[self.row],self.now,(self.now-timedelta(minutes=3)).isoformat())
    def test_repeat_and_reschedule_do_not_duplicate(self):
        self.capture();self.q['kickoff_iso']=(self.now+timedelta(hours=2)).isoformat();self.write_quote()
        self.assertEqual(self.capture()['counts']['already_recorded'],1)
        self.assertEqual(len(list((self.root/M.RELATIVE/'captures').glob('*.json'))),1)
    def test_stale_round_does_not_capture(self):
        self.row['round_id']=1;self.assertNotIn('captured',self.capture()['counts'])
    def test_later_quote_than_forecast_is_not_joined(self):
        self.q['captured_at']=(self.now+timedelta(seconds=1)).isoformat();self.write_quote();self.assertNotIn('captured',self.capture()['counts'])
    def test_old_quote_rejected(self):
        self.q['captured_at']=(self.now-timedelta(hours=3)).isoformat();self.write_quote();self.assertNotIn('captured',self.capture()['counts'])
    def test_live_quote_rejected(self):
        self.q['is_live']='true';self.write_quote();self.assertNotIn('captured',self.capture()['counts'])
    def test_bo5_rejected(self):
        self.row['best_of']=5;self.assertEqual(self.capture()['counts']['not_bo3'],1)
    def test_guard_blocks_drift(self):
        with patch.object(M,'hashes',return_value={'model':'changed'}):
            with self.assertRaises(ValueError):self.capture()
    def test_exact_settlement_roi_and_no_rewrite(self):
        self.capture();p=self.root/'data/oncourt/games_atp.csv'
        p.write_text('tour_id,round_id,winner_id,loser_id,date,result\n10,3,1,2,2026-11-11,6-3 6-4\n')
        r=M.summarize(self.root,self.now+timedelta(hours=5));self.assertEqual((r['wins'],r['losses'],r['stake_units']),(1,0,1));self.assertAlmostEqual(r['roi_pct'],90)
        self.assertEqual(r['paired_accuracy']['model']['n'],1);self.assertEqual(r['actual_stake'],0)
        p.write_text('tour_id,round_id,winner_id,loser_id,date,result\n10,3,2,1,2026-11-11,6-3 6-4\n')
        r=M.summarize(self.root,self.now+timedelta(hours=6));self.assertEqual(r['wins'],1);self.assertTrue(list((self.root/M.RELATIVE/'conflicts').glob('*.json')))
    def test_wrong_round_does_not_settle(self):
        self.capture();(self.root/'data/oncourt/games_atp.csv').write_text('tour_id,round_id,winner_id,loser_id,date,result\n10,1,1,2,2026-11-11,6-3 6-4\n')
        r=M.summarize(self.root,self.now+timedelta(days=3));self.assertEqual(r['overdue'],1);self.assertIsNone(r['roi_pct'])
    def test_retirement_void(self):
        self.capture();(self.root/'data/oncourt/games_atp.csv').write_text('tour_id,round_id,winner_id,loser_id,date,result\n10,3,1,2,2026-11-11,6-3 1-0 RET\n')
        r=M.summarize(self.root,self.now+timedelta(hours=5));self.assertEqual(r['void'],1);self.assertEqual(r['stake_units'],0)
    def test_weekly_reports_no_promotions_or_alerts(self):
        self.capture();r=M.summarize(self.root,self.now);t=M.weekly_text(r)
        self.assertIn('ATP250/500',t);self.assertIn('zero real stake',t);self.assertFalse(r['alerts']);self.assertFalse(r['automatic_promotion'])

if __name__=='__main__':unittest.main()
