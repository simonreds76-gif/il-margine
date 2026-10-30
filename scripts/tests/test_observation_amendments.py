from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib,json,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tennis_observation_amendments as guard

class AmendmentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path.cwd());self.folder=Path(self.temp.name)
        self.now=datetime(2026,10,30,21,tzinfo=timezone.utc);self.before={'engine':'before','model':'same'};self.after={'engine':'after','model':'same'}
        self.proof=self.folder/'observation-proof-20261030.json';self.proof.write_text('{"pricing_ast_identical":true}')
        self.data={'scope':'instrumentation-only-20261030','pricing_changed':False,'effective_at_utc':(self.now-timedelta(minutes=1)).isoformat(),'parity_proof_sha256':hashlib.sha256(self.proof.read_bytes()).hexdigest(),'guard_sha256':hashlib.sha256(Path(guard.__file__).read_bytes()).hexdigest(),'sections':{'model':{'registration_sha256':'original','before':self.before,'after':self.after}}};self.save()
    def tearDown(self):self.temp.cleanup()
    def save(self):self.path=self.folder/'observation-amendment-20261030.json';self.path.write_text(json.dumps(self.data))
    def accept(self,**kw):return guard.accepted_observation_amendment(self.folder,kw.get('reg','original'),kw.get('before',self.before),kw.get('after',self.after),kw.get('section','model'),kw.get('now',self.now))
    def test_exact_reviewed_map_only(self):
        self.assertEqual(self.accept(),hashlib.sha256(self.path.read_bytes()).hexdigest())
        for bad in [{'engine':'drift','model':'same'},{'engine':'after','model':'changed'},{'engine':'after'},dict(self.after,extra='new')]:self.assertIsNone(self.accept(after=bad))
    def test_registration_before_map_and_section_bound(self):
        self.assertIsNone(self.accept(reg='other'));self.assertIsNone(self.accept(before={'engine':'different'}));self.assertIsNone(self.accept(section='downstream'))
    def test_no_future_amendment_or_naive_time(self):
        self.assertIsNone(self.accept(now=self.now-timedelta(days=1)));self.assertIsNone(self.accept(now=self.now.replace(tzinfo=None)))
    def test_proof_and_guard_integrity(self):
        self.proof.write_text('changed');self.assertIsNone(self.accept())
        self.proof.write_text('{"pricing_ast_identical":true}');self.data['guard_sha256']='wrong';self.save();self.assertIsNone(self.accept())
    def test_unapproved_scope_and_missing_file(self):
        self.data['pricing_changed']=True;self.save();self.assertIsNone(self.accept());self.path.unlink();self.assertIsNone(self.accept())

if __name__=='__main__':unittest.main()
