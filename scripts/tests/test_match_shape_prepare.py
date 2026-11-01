import json,sys,tempfile,unittest,os
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch,Mock
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import tennis_match_shape_prepare as P
import tennis_match_shape_collect as C

NOW=datetime(2026,11,1,22,0,tzinfo=timezone.utc)

class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.verify=patch.object(P,'verify_remote_schedule',return_value={'rows':1});self.verify.start();self.addCleanup(self.verify.stop)
        (ROOT/'outputs').mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'outputs');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.out=self.root/P.RELATIVE;self.out.mkdir(parents=True)
        (self.out/'registration.json').write_text(json.dumps({'registered_at':(NOW-timedelta(hours=2)).isoformat(),'fingerprints':{'model':'fixed'}}))
        self.db=self.root/'source.mdb';self.db.write_text('data');os.utime(self.db,(NOW.timestamp()-600,NOW.timestamp()-600))
        folder=self.root/'data/oncourt';folder.mkdir(parents=True)
        for n in P.INPUTS:
            p=folder/n;p.write_text('id\n1\n');os.utime(p,(NOW.timestamp()-300,NOW.timestamp()-300))

    def test_database_newer_than_recent_forecast_blocks_old_exports(self):
        os.utime(self.db,(NOW.timestamp(),NOW.timestamp()))
        with patch.object(P,'fresh_components') as get:
            r=P.readiness(self.root,NOW,self.db)
        self.assertEqual(r['reason'],'database_newer_than_exports');get.assert_not_called()

    def test_new_export_requires_new_forecast(self):
        with patch.object(P,'fresh_components',return_value=(NOW-timedelta(minutes=10),{'rows':[1]})):
            r=P.readiness(self.root,NOW,self.db)
        self.assertEqual(r['reason'],'forecast_predates_current_inputs')

    def test_ready_does_no_export_sync_or_model_run(self):
        runner=Mock()
        with patch.object(P,'fresh_components',return_value=(NOW,{'rows':[1]})):
            r=P.prepare(self.root,NOW,self.db,runner)
        self.assertTrue(r['ready']);self.assertFalse(r['refreshed']);runner.assert_not_called()

    def test_refresh_sync_then_dry_forecast_and_no_alert_stage(self):
        state=P.source_state(self.root,self.db);runner=Mock()
        missing=dict(ready=False,reason='forecast_predates_current_inputs',source=state)
        ready=dict(ready=True,reason='current',source=state)
        with patch.object(P,'readiness',side_effect=[missing,ready]),patch.object(P,'fingerprints',return_value={'model':'fixed'}):
            r=P.prepare(self.root,NOW,self.db,runner)
        self.assertEqual(r['steps'],['sync','forecast']);self.assertTrue(r['refreshed'])
        args=runner.call_args_list[0].args[2]
        self.assertIn('--quick',args);self.assertIn('--current-players',args)
        self.assertIn('--forecast-only',runner.call_args_list[1].args[2])

    def test_failed_sync_never_runs_forecast(self):
        state=P.source_state(self.root,self.db);runner=Mock(side_effect=RuntimeError('sync_failed'))
        with patch.object(P,'readiness',return_value=dict(ready=False,reason='forecast_predates_current_inputs',source=state)),patch.object(P,'fingerprints',return_value={'model':'fixed'}):
            r=P.prepare(self.root,NOW,self.db,runner)
        self.assertFalse(r['ready']);self.assertEqual(r['state'],'FAILED');self.assertEqual(runner.call_count,1)

    def test_incomplete_remote_sync_never_runs_forecast(self):
        state=P.source_state(self.root,self.db);runner=Mock()
        with patch.object(P,'readiness',return_value=dict(ready=False,reason='forecast_predates_current_inputs',source=state)),patch.object(P,'fingerprints',return_value={'model':'fixed'}),patch.object(P,'verify_remote_schedule',side_effect=RuntimeError('remote_schedule_does_not_match_native_export')):
            r=P.prepare(self.root,NOW,self.db,runner)
        self.assertFalse(r['ready']);self.assertEqual(r['steps'],['sync']);self.assertEqual(runner.call_count,1)

    def test_export_must_replace_all_files_before_sync(self):
        os.utime(self.db,(NOW.timestamp(),NOW.timestamp()));runner=Mock()
        with patch.object(P,'fingerprints',return_value={'model':'fixed'}):
            r=P.prepare(self.root,NOW,self.db,runner)
        self.assertFalse(r['ready']);self.assertIn('native_export_did_not_refresh_all',r['reason']);self.assertEqual(runner.call_count,1)

    def test_changed_frozen_model_is_not_refreshed(self):
        runner=Mock()
        with patch.object(P,'fresh_components',return_value=(None,None)),patch.object(P,'fingerprints',return_value={'model':'changed'}):
            with self.assertRaisesRegex(RuntimeError,'frozen_model_changed'):P.prepare(self.root,NOW,self.db,runner)
        runner.assert_not_called()

    def test_new_forecast_gets_a_new_quote_even_if_old_receipt_was_fresh(self):
        new={'fresh':'new'}
        with patch.object(C,'prepare',return_value={'ready':True,'refreshed':True}),patch.object(C,'collect',return_value=new) as collect,patch.object(C,'refresh',return_value={}) as refresh:
            C.capture_shared(self.root,{'old':'quote'})
        collect.assert_called_once();self.assertEqual(refresh.call_args.kwargs['receipt'],new)

    def test_failed_preparation_keeps_saved_bets_and_never_prices(self):
        with patch.object(C,'prepare',return_value={'ready':False,'reason':'failed'}),patch.object(C,'collect') as collect,patch.object(C,'refresh',return_value={}) as refresh:
            C.capture_shared(self.root,{'old':'quote'})
        collect.assert_not_called();self.assertTrue(refresh.call_args.kwargs['settle_only'])
        status=json.loads((self.out/'capture-status.json').read_text());self.assertEqual(status['state'],'INPUT_REFRESH_REQUIRED')

    def test_snapshot_reports_stale_inputs_without_network_or_model_work(self):
        with patch.object(C,'readiness',return_value={'ready':False,'reason':'database_newer_than_exports'}),patch.object(C,'prepare') as prepare,patch.object(C,'collect') as collect,patch.object(C,'refresh',return_value={}) as refresh:
            C.refresh_saved(self.root)
        prepare.assert_not_called();collect.assert_not_called();self.assertTrue(refresh.call_args.kwargs['settle_only'])

if __name__=='__main__':unittest.main()
