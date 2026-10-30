from pathlib import Path
import tempfile,unittest,json,hashlib,sys,csv
from datetime import datetime,timezone,timedelta
S=Path(__file__).resolve().parents[1];sys.path.insert(0,str(S))
import sisal_observation_amendment as A
from tennis_props_identity_health import verify_identity_buckets
W=Path(__file__).resolve().parent
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class SourceRepairs(unittest.TestCase):
 def test_guard_exact_map_and_time(self):
  with tempfile.TemporaryDirectory(dir=W) as td:
   p=Path(td);proof=p/'observation-proof-20261030.json';proof.write_text('{}')
   data=dict(scope='instrumentation-only-20261030',pricing_changed=False,effective_at_utc='2026-10-30T12:00:00+00:00',parity_proof_sha256=h(proof),guard_sha256=h(S/'sisal_observation_amendment.py'),sections={'event':dict(registration_sha256='reg',before={'a':'old'},after={'a':'new'},caller_guard_file='sisal_event_comparison.py',caller_guard_sha256=h(S/'sisal_event_comparison.py'))})
   path=p/'observation-amendment-20261030.json';path.write_text(json.dumps(data));now=datetime(2026,10,30,22,tzinfo=timezone.utc)
   self.assertTrue(A.accepted_observation_amendment(p,'reg',{'a':'old'},{'a':'new'},'event',now))
   for reg,before,after,when in [('bad',{'a':'old'},{'a':'new'},now),('reg',{'a':'old'},{'a':'other'},now),('reg',{'a':'old','b':'extra'},{'a':'new'},now),('reg',{'a':'old'},{'a':'new'},now-timedelta(days=1))]:
    self.assertIsNone(A.accepted_observation_amendment(p,reg,before,after,'event',when))
   proof.write_text('{"changed":true}');self.assertIsNone(A.accepted_observation_amendment(p,'reg',{'a':'old'},{'a':'new'},'event',now))


 def fixture(self,folder,dob='19971028',country='USA',name='Taylor Harry Fritz'):
  for t in ('atp','wta'):
   for rel,fields,rows in [(f'data/oncourt/players_{t}.csv',['id','name','birthdate','country'],[dict(id='29932',name=name,birthdate='1997-10-28',country='USA')] if t=='atp' else []),(f'data/sackmann/{t}_players.csv',['player_id','name_first','name_last','dob','ioc'],[dict(player_id='126203',name_first='Taylor',name_last='Fritz',dob=dob,ioc=country)] if t=='atp' else [])]:
    p=folder/rel;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',newline='') as f:
     w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
  return [dict(tour='ATP',player_id='oc:29932',player_name=name),dict(tour='ATP',player_id='126203',player_name='Taylor Fritz')]
 def test_verified_split_rejected(self):
  with tempfile.TemporaryDirectory(dir=W) as t:
   p=Path(t);rows=self.fixture(p)
   with self.assertRaisesRegex(ValueError,'verified_split_player_histories'):verify_identity_buckets(p,rows)
 def test_dob_mismatch_never_merged(self):
  with tempfile.TemporaryDirectory(dir=W) as t:
   p=Path(t);rows=self.fixture(p,dob='19981028');r=verify_identity_buckets(p,rows)
   self.assertEqual(r['verified_splits'],0);self.assertEqual(len(r['unverified_name_candidates']),1)
 def test_missing_dob_never_verified(self):
  with tempfile.TemporaryDirectory(dir=W) as t:
   p=Path(t);rows=self.fixture(p,dob='');r=verify_identity_buckets(p,rows)
   self.assertEqual(len(r['unverified_name_candidates']),1)
 def test_repaired_id_is_not_split(self):
  with tempfile.TemporaryDirectory(dir=W) as t:
   p=Path(t);rows=self.fixture(p);self.assertEqual(verify_identity_buckets(p,rows[1:])['verified_splits'],0)
if __name__=='__main__':unittest.main()
