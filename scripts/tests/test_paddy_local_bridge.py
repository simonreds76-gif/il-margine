import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aerial_data import save, read
from paddy_headed import capture
from paddy_local_bridge import run, publish
from skyline_store import restore

NOW=datetime(2026,10,28,15,tzinfo=timezone.utc)

@patch('paddy_headed.DIRECT_COLLECTION_ENABLED', True)
@patch('paddy_local_bridge.DIRECT_COLLECTION_ENABLED', True)
class PaddyBridgeTests(unittest.TestCase):
    def test_cloud_never_requests_restricted_hosts_and_expiry_stays_original(self):
        with tempfile.TemporaryDirectory() as d, patch.dict('os.environ',{'GITHUB_ACTIONS':'true'}):
            root=Path(d);get=Mock(side_effect=AssertionError('No remote access'))
            self.assertEqual(capture(root,{},NOW,get=get)['status'],'LOCAL_CAPTURE_AWAITING_PC')
            old={'status':'CAPTURED','generated_at':NOW.isoformat(),'headed_sot':4,'headed_goals':2,'fixtures':1}
            save(root/'data/aerial/paddy/status.json',old)
            self.assertEqual(capture(root,{},NOW,get=get)['status'],'LOCAL_CAPTURE_READY')
            save(root/'data/aerial/paddy/status.json',old)
            result=capture(root,{},NOW+timedelta(hours=3),get=get)
            self.assertEqual(result['status'],'LOCAL_CAPTURE_STALE')
            self.assertEqual(result['generated_at'],old['generated_at']);get.assert_not_called()

    def test_private_source_update_preserves_models_and_alerts(self):
        state={'forecasts':{'a':{'x':1}},'outcomes':{'a':{'win':True}},'report':{'old':True},'alerts':{'a':'sent'}}
        original=dict(state)
        def writer(root,change):return change(state) is not False
        status={'generated_at':NOW.isoformat(),'status':'CAPTURED'}
        self.assertTrue(publish(None,{'events':[]},status,writer))
        for k in original:self.assertEqual(state[k],original[k])
        self.assertFalse(publish(None,{'events':['older']},{**status,'generated_at':(NOW-timedelta(minutes=1)).isoformat()},writer))
        self.assertEqual(state['source_prices']['paddy']['prices']['events'],[])

    def test_cadence_and_private_upload_with_no_alert_sender(self):
        with tempfile.TemporaryDirectory() as d,patch.dict('os.environ',{'GITHUB_ACTIONS':'false'}):
            root=Path(d);get=Mock();get.return_value.json.return_value={'generated_at':NOW.isoformat(),'fixtures':[]}
            collector=Mock(return_value={'generated_at':NOW.isoformat(),'status':'CAPTURED','headed_sot':0,'headed_goals':0})
            state={}
            def writer(root,change):return change(state) is not False
            self.assertEqual(run(root,NOW,get,collector,writer)['status'],'PUBLISHED')
            self.assertEqual(run(root,NOW+timedelta(minutes=29),get,collector,writer)['status'],'NOT_DUE')
            get.assert_called_once();collector.assert_called_once()
            self.assertIn('paddy',state['source_prices'])

    def test_403_backoff_and_stale_blob(self):
        with tempfile.TemporaryDirectory() as d,patch.dict('os.environ',{'GITHUB_ACTIONS':'false'}):
            root=Path(d);get=Mock();get.return_value.json.return_value={'generated_at':NOW.isoformat(),'fixtures':[]}
            collector=Mock(return_value={'generated_at':NOW.isoformat(),'status':'FAILED','http_status':403})
            self.assertEqual(run(root,NOW,get,collector,lambda r,c:True)['source_status'],'FAILED')
            self.assertEqual(run(root,NOW+timedelta(hours=23),get,collector)['status'],'NOT_DUE')
            get.return_value.json.return_value={'generated_at':NOW.isoformat(),'fixtures':[]}
            self.assertEqual(run(root,NOW+timedelta(hours=25),get,collector)['status'],'FAILED')
            self.assertEqual(collector.call_count,1)

    def test_cloud_restore_brings_private_quotes_without_changing_records(self):
        source={'prices':{'generated_at':NOW.isoformat(),'events':[]},'status':{'generated_at':NOW.isoformat(),'status':'CAPTURED'}}
        with tempfile.TemporaryDirectory() as d,patch('skyline_store.connection',return_value=('url',{})),patch('skyline_store.requests.get') as get:
            get.return_value.json.return_value=[{'payload':{'version':'skyline-v1','source_prices':{'paddy':source}}}]
            root=Path(d);restore(root)
            self.assertEqual(read(root/'data/aerial/paddy/prices.json'),source['prices'])
            self.assertEqual(read(root/'data/aerial/paddy/status.json'),source['status'])

    def test_old_crash_lock_recovers_but_current_lock_holds(self):
        with tempfile.TemporaryDirectory() as d,patch.dict('os.environ',{'GITHUB_ACTIONS':'false'}):
            root=Path(d);directory=root/'data/aerial/paddy';directory.mkdir(parents=True)
            (directory/'bridge.lock').write_text(NOW.isoformat())
            self.assertEqual(run(root,NOW)['status'],'LOCKED')
            get=Mock(side_effect=ValueError('test missing snapshot'))
            self.assertEqual(run(root,NOW+timedelta(minutes=21),get=get)['status'],'FAILED')
            self.assertFalse((directory/'bridge.lock').exists())

class DirectPaddyDisabledTests(unittest.TestCase):
    def test_revocation_makes_no_requests_and_discards_active_quotes(self):
        from paddy_headed import quoted
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);get=Mock(side_effect=AssertionError('No website request'))
            post=Mock(side_effect=AssertionError('No website request'))
            save(root/'data/aerial/paddy/prices.json',{'events':[{'stale':True}]})
            self.assertEqual(capture(root,{},NOW,get=get,post=post)['status'],'DISABLED_BY_USER')
            self.assertEqual(read(root/'data/aerial/paddy/prices.json')['events'],[])
            self.assertEqual(run(root,NOW,get=get)['status'],'DISABLED_BY_USER')
            self.assertEqual(quoted({}, {}, {}, NOW),[])
            get.assert_not_called();post.assert_not_called()

    def test_existing_direct_forecast_cannot_send_an_alert(self):
        from test_skyline_alerts import fixture
        from skyline_alerts import eligible
        r,state=fixture();r['quote'].update(bookmaker='Paddy Power',contract='paddy_super_sub_v1')
        self.assertFalse(eligible(r,state,datetime.fromisoformat(r['captured_at'])))

if __name__=='__main__':unittest.main()
