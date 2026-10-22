import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch,Mock
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from aerial_data import save,read
from skyline_store import restore,persist

class PrivateStore(unittest.TestCase):
    def test_roundtrip_and_conflict(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);key='a'*64
            state={'version':'skyline-v1','forecasts':{key:{'key':key,'odds':8}},'outcomes':{}}
            state['alerts']={key:{'status':'sent','message_id':123}}
            response=Mock();response.json.return_value=[{'payload':state,'updated_at':'2026-10-18T12:00:00Z'}]
            with patch('skyline_store.connection',return_value=('https://test.invalid',{})),patch('skyline_store.requests.get',return_value=response),patch('skyline_store.requests.patch',return_value=response) as post:
                restore(root);restore(root)
                self.assertEqual(read(root/f'data/aerial/skyline/forecasts/{key}.json')['odds'],8)
                persist(root,{'generated_at':'2026-10-18T13:00:00Z'})
                self.assertEqual(post.call_args.kwargs['json']['payload']['forecasts'],state['forecasts'])
                self.assertEqual(post.call_args.kwargs['json']['payload']['alerts'],state['alerts'])
                self.assertEqual(post.call_args.kwargs['params']['updated_at'],'eq.2026-10-18T12:00:00Z')
                save(root/f'data/aerial/skyline/forecasts/{key}.json',{'key':key,'odds':9})
                with self.assertRaises(ValueError):restore(root)

    def test_cas_retries_and_retains_new_receipt(self):
        from skyline_store import update
        first={'version':'skyline-v1'}
        second={'version':'skyline-v1','alerts':{'existing':{'status':'sent'}}}
        a=Mock();a.json.return_value=[]
        b=Mock();b.json.return_value=[{}]
        with patch('skyline_store.connection',return_value=('https://test.invalid',{})),patch('skyline_store.fetch',side_effect=[{'payload':first,'updated_at':'old'},{'payload':second,'updated_at':'new'}]),patch('skyline_store.requests.patch',side_effect=[a,b]) as post:
            self.assertTrue(update(None,lambda state:state.update(extra=True)))
            self.assertEqual(post.call_args.kwargs['json']['payload']['alerts'],second['alerts'])
    def test_fail_closed_and_path_validation(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);response=Mock();response.raise_for_status.side_effect=RuntimeError('Unavailable')
            with patch('skyline_store.connection',return_value=('https://test.invalid',{})),patch('skyline_store.requests.get',return_value=response):
                with self.assertRaises(RuntimeError):restore(root)
            response=Mock();response.json.return_value=[{'payload':{'version':'skyline-v1','forecasts':{'../../escape':{}}}}]
            with patch('skyline_store.connection',return_value=('https://test.invalid',{})),patch('skyline_store.requests.get',return_value=response):
                with self.assertRaises(ValueError):restore(root)

if __name__=='__main__':unittest.main()
