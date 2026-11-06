import base64, copy, importlib.util, json, unittest, zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

spec=importlib.util.spec_from_file_location('capture', Path(__file__).with_name('bookmaker-browser-import.py'))
capture=importlib.util.module_from_spec(spec);spec.loader.exec_module(capture)

class CaptureValidation(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,9,5,12,tzinfo=timezone.utc)
        self.data={'captured_at':self.now.isoformat(),'pages':[
          {'sport':s,'home':'Home','away':'Away','url':f'https://www.oddschecker.com/{s}/event-{i}/winner',
           'captured_at':self.now.isoformat(),'starts_at':(self.now+timedelta(hours=2)).isoformat(),
           'grids':[{'market':'Win Market','selections':[]}]}
          for s in ['football','tennis'] for i in range(2)]}
    def test_valid_bounded_snapshot(self):
        self.assertEqual(len(capture.validate(self.data,self.now)['pages']),4)
    def test_duplicate_event_rejected(self):
        self.data['pages'][1]=copy.deepcopy(self.data['pages'][0])
        with self.assertRaises(ValueError):capture.validate(self.data,self.now)
    def test_stale_capture_rejected(self):
        self.data['captured_at']=(self.now-timedelta(hours=7)).isoformat()
        with self.assertRaises(ValueError):capture.validate(self.data,self.now)
    def test_started_event_rejected(self):
        self.data['pages'][0]['starts_at']=self.now.isoformat()
        with self.assertRaises(ValueError):capture.validate(self.data,self.now)
    def test_foreign_source_rejected(self):
        self.data['pages'][0]['url']='https://other.example/football/event/winner'
        with self.assertRaises(ValueError):capture.validate(self.data,self.now)
    def test_both_sports_required(self):
        self.data['pages']=self.data['pages'][:2]
        with self.assertRaises(ValueError):capture.validate(self.data,self.now)
    def test_compressed_capture_roundtrip(self):
        encoded=base64.b64encode(zlib.compress(json.dumps(self.data).encode())).decode()
        self.assertEqual(capture.decode_capture(encoded),self.data)
    def test_oversized_compression_rejected(self):
        encoded=base64.b64encode(zlib.compress(b'x'*2_000_001)).decode()
        with self.assertRaises(ValueError):capture.decode_capture(encoded)
    def test_inadequate_builder_results_rejected(self):
        with self.assertRaises(ValueError):capture.check_result({'status':'CAPTURE_FAILED'})
        with self.assertRaises(ValueError):capture.check_result({'status':'PASS','coverage':{'payload_operators':2}})

if __name__=='__main__':unittest.main()
