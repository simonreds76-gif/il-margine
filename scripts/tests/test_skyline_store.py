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
            response=Mock();response.json.return_value=[{'payload':state}]
            with patch('skyline_store.connection',return_value=('https://test.invalid',{})),patch('skyline_store.requests.get',return_value=response),patch('skyline_store.requests.post',return_value=Mock()) as post:
                restore(root);restore(root)
                self.assertEqual(read(root/f'data/aerial/skyline/forecasts/{key}.json')['odds'],8)
                persist(root,{'generated_at':'2026-10-18T13:00:00Z'})
                self.assertEqual(post.call_args.kwargs['json'][0]['payload']['forecasts'],state['forecasts'])
                save(root/f'data/aerial/skyline/forecasts/{key}.json',{'key':key,'odds':9})
                with self.assertRaises(ValueError):restore(root)
    def test_fail_closed_and_path_validation(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);response=Mock();response.raise_for_status.side_effect=RuntimeError('Unavailable')
            with patch('skyline_store.connection',return_value=('https://test.invalid',{})),patch('skyline_store.requests.get',return_value=response):
                with self.assertRaises(RuntimeError):restore(root)
            response=Mock();response.json.return_value=[{'payload':{'version':'skyline-v1','forecasts':{'../../escape':{}}}}]
            with patch('skyline_store.connection',return_value=('https://test.invalid',{})),patch('skyline_store.requests.get',return_value=response):
                with self.assertRaises(ValueError):restore(root)

if __name__=='__main__':unittest.main()
