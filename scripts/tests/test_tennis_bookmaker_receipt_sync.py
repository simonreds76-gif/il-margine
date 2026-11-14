import unittest,tempfile,csv,json,sys,importlib.util
from pathlib import Path
from datetime import datetime,timezone,date
from hashlib import sha256
from unittest.mock import patch
S=Path(__file__).resolve().parents[1];sys.path.insert(0,str(S))
spec=importlib.util.spec_from_file_location('receipt_sync_test',S/'sync-tennis-props-hosted-captures.py');sync=importlib.util.module_from_spec(spec);sys.modules[spec.name]=sync;spec.loader.exec_module(sync)
import tennis_bookmaker_check as check
class Sync(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.addCleanup(self.tmp.cleanup)
  self.day='2026-11-14';self.names={'props':f'bet365-lines-{self.day}.csv','most_aces':f'betmgm-most-aces-1x2-{self.day}.csv','most_df':f'most-df-1x2-{self.day}.csv'}
  self.packet={'generated_at':'2026-11-14T11:00:00Z','artifacts':{k:{'name':n,'sha256':sha256(b'capture_ts\n').hexdigest()} for k,n in self.names.items()}}
  self.base='data/tennis-props/inbox/';self.payload={self.base+n:b'capture_ts\n' for n in self.names.values()};self.payload[self.base+f'bookmaker-check-{self.day}.json']=json.dumps(self.packet).encode()
 def run_sync(self):
  with patch.object(sync,'ROOT',self.root),patch.object(sync,'remote_blob',side_effect=lambda ref,p:self.payload.get(p)):
   return sync.sync_bookmaker_checks('test',date(2026,11,14),0)
 def test_empty_current_packet_replaces_old_quote(self):
  p=self.root/self.base/self.names['props'];p.parent.mkdir(parents=True);p.write_text('capture_ts\n2026-11-14T10:00:00Z\n')
  result,protected=self.run_sync();self.assertEqual(p.read_bytes(),b'capture_ts\n');self.assertEqual(len(result['copied_receipts']),1);self.assertEqual(len(protected),3)
 def test_hash_mismatch_does_not_install_receipt(self):
  self.payload[self.base+self.names['most_df']]=b'bad';result,_=self.run_sync();self.assertEqual(len(result['errors']),1);self.assertFalse((self.root/self.base/f'bookmaker-check-{self.day}.json').exists())
 def test_newer_local_packet_is_not_replaced(self):
  p=self.root/self.base/f'bookmaker-check-{self.day}.json';p.parent.mkdir(parents=True);p.write_text(json.dumps({'generated_at':'2026-11-14T12:00:00Z'}));result,protected=self.run_sync();self.assertFalse(result['copied_receipts']);self.assertEqual(len(protected),3)
 def test_newer_local_price_is_not_replaced(self):
  p=self.root/self.base/self.names['props'];p.parent.mkdir(parents=True);p.write_text('capture_ts\n2026-11-14T12:00:00Z\n');result,_=self.run_sync();self.assertTrue(result['errors']);self.assertIn('12:00',p.read_text())
 def test_audit_retains_no_bets_once(self):
  p=self.root/'data/tennis-props/comparison-2026-11-14.csv';p.parent.mkdir(parents=True)
  p.write_text('match_start_utc,capture_ts,bettable,block_reasons\n2026-11-14T12:00:00Z,2026-11-14T10:55:00Z,false,MODEL_MARKET_GAP\n')
  now=datetime(2026,11,14,11,tzinfo=timezone.utc)
  first=check.retain_candidates(self.root,self.day,{},now);target=self.root/first['path'];raw=target.read_bytes()
  second=check.retain_candidates(self.root,self.day,{},now.replace(minute=1));self.assertEqual(first['sha256'],second['sha256']);self.assertEqual(raw,target.read_bytes());self.assertEqual(first['rows'],1)
if __name__=='__main__':unittest.main()
