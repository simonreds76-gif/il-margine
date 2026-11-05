import copy, importlib.util, json, subprocess, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import tennis_match_shape_quotes as Q
NOW=datetime.now(timezone.utc)
def packet():
    event=dict(id=123,homeName='A Player',awayName='B Player',start=(NOW+timedelta(hours=2)).isoformat(),group='Paris',sport='TENNIS',state='NOT_STARTED',path=[{'termKey':'atp'}])
    offer=dict(id=456,eventId=123,criterion={'englishLabel':'Total Games'},betOfferType={'id':6},tags=['OFFERED_PREMATCH','MAIN_LINE'],outcomes=[dict(type=t,status='OPEN',odds=o,line=22500,betOfferId=456,changedDate=NOW.isoformat()) for t,o in [('OT_OVER',2000),('OT_UNDER',1900)]])
    return dict(events=[dict(requested_id=123,captured_at=NOW.isoformat(),payload=dict(events=[event],betOffers=[offer]))])
class CloudTests(unittest.TestCase):
    def test_minimal_import_no_model_dependencies(self):
        code="import sys;sys.path.insert(0,'scripts');import tennis_match_shape_quotes;assert not any(x in sys.modules for x in ['pandas','scipy','numpy','tennis_match_shape'])"
        subprocess.run([sys.executable,'-c',code],cwd=ROOT,check=True)
    def test_capture_is_immutable_price_only_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=packet()
            for n in range(2):
                status=Q.capture_quotes(root,p,clock=NOW+timedelta(minutes=n),collector=lambda:self.fail('unnecessary network'))
                self.assertEqual(status['state'],'QUOTES_SAVED_FOR_NATIVE_TRACKER')
            files=list((root/Q.RELATIVE/'cloud-quotes').rglob('*.json'));self.assertEqual(len(files),1)
            saved=json.loads(files[0].read_text());self.assertEqual(saved['events'][0]['captured_at'],NOW.isoformat())
            self.assertEqual(files[0].stem,Q.digest(saved));self.assertFalse((root/Q.RELATIVE/'captures').exists())
    def test_invalid_offers_and_source_errors_remain_explicit(self):
        for mutation in ('suspended','live','future','stale','wrong_contract','one_sided'):
            p=packet();i=p['events'][0];o=i['payload']['betOffers'][0]
            if mutation=='suspended':o['outcomes'][0]['status']='SUSPENDED'
            if mutation=='live':i['payload']['events'][0]['state']='STARTED'
            if mutation=='future':i['captured_at']=(NOW+timedelta(minutes=1)).isoformat()
            if mutation=='stale':i['captured_at']=(NOW-timedelta(hours=1)).isoformat()
            if mutation=='wrong_contract':o['criterion']['englishLabel']='Total Games - Set 1'
            if mutation=='one_sided':o['outcomes'].pop()
            self.assertEqual(Q.parse_receipt(p,NOW),[],mutation)
        with tempfile.TemporaryDirectory() as tmp:
            s=Q.capture_quotes(Path(tmp),{},collector=lambda:dict(events=[],errors=['catalogue:Timeout']))
            self.assertEqual(s['state'],'SOURCE_ERROR');self.assertEqual(s['quote_count'],0)
    def test_native_handoff_preserves_observation_and_rejects_tampering(self):
        spec=importlib.util.spec_from_file_location('sync_hosted',ROOT/'scripts/sync-tennis-props-hosted-captures.py');sync=importlib.util.module_from_spec(spec);spec.loader.exec_module(sync)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=packet();raw=json.dumps(p).encode();name=Q.digest(p)+'.json';rel=str(Q.RELATIVE/'cloud-quotes'/NOW.date().isoformat()/name).replace('\\','/')
            result=subprocess.CompletedProcess([],0,stdout=(rel+'\n').encode())
            with patch.object(sync,'ROOT',root),patch.object(sync,'git_command',return_value=result),patch.object(sync,'remote_blob',side_effect=lambda ref,path:raw if path==rel else None):
                self.assertEqual(sync.sync_match_shape_quotes('ref',NOW.date(),1)['imported_packets'],1)
                self.assertEqual(sync.sync_match_shape_quotes('ref',NOW.date(),1)['imported_packets'],0)
                self.assertEqual((root/Q.RELATIVE/'quote-evidence'/name).read_bytes(),raw)
                raw=b'{"events":[]}'
                with self.assertRaises(ValueError):sync.sync_match_shape_quotes('ref',NOW.date(),1)
    def test_parser_matches_frozen_parser_source(self):
        import ast
        def source(path):
            text=path.read_text();n=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='parse_receipt');return ast.dump(n,include_attributes=False)
        self.assertEqual(source(ROOT/'scripts/tennis_match_shape.py'),source(ROOT/'scripts/tennis_match_shape_quotes.py'))
if __name__=='__main__':unittest.main()
