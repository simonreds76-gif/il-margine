import csv
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import tennis_pairing_consistency as P

def module(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'), SCRIPTS/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

DAILY=module('run-tennis-props-daily')
LOADER=module('oncourt-load-supabase')

def write(path, rows, fields=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)

class PairingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.db=self.root/'absent.mdb'
        for name in ['courts.csv']+[f'{k}_{t}.csv' for t in ('atp','wta') for k in ('today','players','tours')]:
            p=self.root/'data/oncourt'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('tour_id,player1_id,player2_id,round_id,draw,result\n1,1,1,1,1,\n' if name.startswith('today') else 'id,name\n1,Test\n')
            os.utime(p,ns=(10,10))
        self.fixture=dict(tour='ATP',tour_id='21362',round='R32',player1_id='76127',player2_id='58149')
        self.rows=[dict(tour='ATP',tour_id='21362',round='R32',player_id=a,opponent_id=b,generation_date='2026-11-01',surface='Hard',date='2026-11-02',tournament='Paris',player=n,opponent=o) for a,b,n,o in [('76127','58149','Darderi','Hijikata'),('58149','76127','Hijikata','Darderi')]]
        write(self.root/P.BOARD,self.rows)
    def state(self):
        return P.board_state(self.root,'2026-11-01',expected=[self.fixture],database=self.db)
    def test_both_current_reciprocal_sides_pass(self):
        self.assertEqual(self.state()['state'],'CURRENT')
    def test_fresh_timestamp_cannot_hide_wrong_opponent(self):
        wrong=[dict(r,opponent_id='3700') for r in self.rows];write(self.root/P.BOARD,wrong)
        s=self.state();self.assertTrue(s['board_after_exports']);self.assertEqual(len(s['missing_sides']),2)
        self.assertEqual(s['state'],'REBUILD_REQUIRED')
    def test_one_side_is_not_a_complete_match(self):
        write(self.root/P.BOARD,self.rows[:1]);self.assertEqual(len(self.state()['missing_sides']),1)
    def test_duplicate_row_cannot_replace_missing_opponent(self):
        write(self.root/P.BOARD,[self.rows[0]]*2);s=self.state();self.assertEqual(len(s['missing_sides']),1);self.assertEqual(len(s['unexpected_sides']),1)
    def test_updated_wta_export_alone_triggers_rebuild(self):
        p=self.root/'data/oncourt/today_wta.csv';os.utime(p,ns=(10**19,10**19))
        self.assertEqual(self.state()['state'],'REBUILD_REQUIRED')
    def test_resolved_id_missing_from_player_export_cannot_disappear_silently(self):
        p=self.root/'data/oncourt/today_wta.csv'
        p.write_text('tour_id,player1_id,player2_id,round_id,draw,result\n1,1,2,1,1,\n')
        with self.assertRaisesRegex(ValueError,'native_player_identity_missing:wta:2'):P.native_epoch(self.root,self.db)
    def test_database_newer_than_wta_export_blocks(self):
        self.db.write_text('updated');os.utime(self.db,ns=(2000000000,2000000000))
        for p in (self.root/'data/oncourt').iterdir():
            if p.name!='today_wta.csv':os.utime(p,ns=(3000000000,3000000000))
        with self.assertRaisesRegex(ValueError,'today_wta'):P.native_epoch(self.root,self.db)
    def test_rebuild_repairs_replaced_qualifier(self):
        write(self.root/P.BOARD,[dict(r,opponent_id='3700') for r in self.rows])
        def rebuild(*a,**k):write(self.root/P.BOARD,self.rows);return 0
        with patch.object(P,'expected_props',return_value=[self.fixture]),patch.object(P,'native_epoch',return_value={'today':{'mtime_ns':10}}):
            status=P.ensure_props_board(self.root,'2026-11-01',runner=rebuild)
        self.assertEqual(status['state'],'CURRENT');self.assertTrue(status['rebuilt'])
    def test_failed_rebuild_leaves_explicit_block(self):
        write(self.root/P.BOARD,[dict(r,opponent_id='3700') for r in self.rows])
        with patch.object(P,'expected_props',return_value=[self.fixture]),patch.object(P,'native_epoch',return_value={'today':{'mtime_ns':10}}):
            with self.assertRaisesRegex(RuntimeError,'recovery_failed'):P.ensure_props_board(self.root,'2026-11-01',runner=lambda *a,**k:1)
        self.assertEqual(json.loads((self.root/P.STATUS).read_text())['state'],'BLOCKED')
    def test_mid_rebuild_source_change_is_rejected(self):
        states=[dict(state='REBUILD_REQUIRED',native_epoch={'a':1}),dict(state='CURRENT',native_epoch={'a':2})]
        with patch.object(P,'board_state',side_effect=states):
            with self.assertRaisesRegex(ValueError,'changed_during'):P.ensure_props_board(self.root,'2026-11-01',runner=lambda *a,**k:0)
    def test_derived_fresh_file_still_must_match_exact_pair(self):
        write(self.root/'data/tennis-props/shadow/aces-v3-projection-board.csv',[dict(r,opponent_id='3700') for r in self.rows])
        with self.assertRaisesRegex(ValueError,'pairing_mismatch'):P.verify_derived_board(self.root,'aces-v3-projection-board.csv')
    def test_empty_scope_clears_current_boards_preserves_observations(self):
        write(self.root/P.BOARD,[dict(r,tour='WTA') for r in self.rows])
        ledger=self.root/'data/tennis-props/shadow/observations.jsonl';ledger.parent.mkdir(parents=True,exist_ok=True);ledger.write_text('immutable')
        self.assertTrue(P.clear_empty_derived_scope(self.root))
        self.assertEqual(ledger.read_text(),'immutable')
        self.assertEqual(P.verify_derived_board(self.root,'aces-v3-projection-board.csv')['rows'],0)

class CloudSyncTests(unittest.TestCase):
    def test_missing_schedule_is_not_empty_schedule(self):
        with self.assertRaises(FileNotFoundError):LOADER.read_current_schedule(Path('nonexistent-test-schedule.csv'))
    def test_truncated_export_cannot_clear_remote(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'schedule.csv';p.write_text('')
            with self.assertRaises(ValueError):LOADER.read_current_schedule(p)
    def test_empty_valid_export_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'schedule.csv';p.write_text('tour_id,player1_id,player2_id,round_id,draw,result\n')
            self.assertEqual(LOADER.read_current_schedule(p),[])
    def test_failed_delete_never_inserts_and_never_succeeds(self):
        with patch.object(LOADER,'_delete_all',return_value=False),patch.object(LOADER,'_insert') as insert:
            with self.assertRaises(RuntimeError):LOADER.replace_current_schedule([{'id':1}])
            insert.assert_not_called()
    def test_failed_insert_never_reports_success(self):
        with patch.object(LOADER,'_delete_all',return_value=True),patch.object(LOADER,'_insert',return_value=False):
            with self.assertRaises(RuntimeError):LOADER.replace_current_schedule([{'id':1}])
    def test_same_count_wrong_pair_cloud_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'SUPABASE_URL':'https://example.test','SUPABASE_SERVICE_ROLE_KEY':'test'}):
            root=Path(tmp);row=dict(tour_id='1',player1_id='2',player2_id='3',round_id='4',draw='1',result='')
            write(root/'data/oncourt/today_atp.csv',[row])
            get=Mock(return_value=Mock(json=lambda:[dict(row,player2_id='3700')]))
            with self.assertRaisesRegex(ValueError,'does_not_match'):P.verify_remote_schedule(root,get)

class RefreshFlowTests(unittest.TestCase):
    def test_base_recovery_failure_stops_every_model_consumer(self):
        with patch.object(DAILY,'mark_pipeline_blocked'),patch.object(DAILY,'ensure_props_board',side_effect=ValueError('stale')),patch.object(DAILY,'refresh_current_most_aces') as derived,patch.object(DAILY,'run_comparison') as compare:
            with self.assertRaises(ValueError):DAILY.run_monitor_only('2026-11-01',selections_only=True)
            derived.assert_not_called();compare.assert_not_called()
    def test_fast_refresh_builds_before_comparison_then_all_paper_lanes(self):
        calls=[]
        with patch.object(DAILY,'mark_pipeline_blocked'),patch.object(DAILY,'ensure_props_board',side_effect=lambda *a,**k:calls.append('base')),patch.object(DAILY,'refresh_current_most_aces',side_effect=lambda *a,**k:calls.append('derived') or True),patch.object(DAILY,'select_market_file',return_value=Path('prices.csv')),patch.object(DAILY,'run_comparison',side_effect=lambda *a,**k:calls.append('comparison') or True),patch.object(DAILY,'refresh_current_paper_lanes',side_effect=lambda *a,**k:calls.append('paper') or True),patch.object(DAILY,'run',return_value=0),patch.object(DAILY,'write_pipeline_health',return_value=0):
            self.assertEqual(DAILY.run_monitor_only('2026-11-01',selections_only=True),0)
        self.assertEqual(calls,['base','derived','comparison','paper'])
    def test_paper_lanes_are_independent_and_failure_visible(self):
        calls=[]
        def run(cmd,*a,**kw):
            calls.append(Path(cmd[1]).name);return 1 if 'compass' in cmd[1] else 0
        with tempfile.TemporaryDirectory() as tmp,patch.object(DAILY,'ROOT',Path(tmp)),patch.object(DAILY,'run',side_effect=run):
            self.assertFalse(DAILY.refresh_current_paper_lanes('2026-11-01'))
            health=json.loads((Path(tmp)/'data/tennis-input-health/paper-refresh-status.json').read_text())
            self.assertEqual(health['state'],'FAILED');self.assertEqual(len(calls),3)
            self.assertFalse(any('telegram' in c or 'digest' in c for c in calls))

if __name__=='__main__':unittest.main()

