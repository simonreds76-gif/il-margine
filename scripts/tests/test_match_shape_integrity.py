"""Operational paper safeguards, independent of pricing calculations."""
import copy
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import tennis_match_shape_integrity as I
import tennis_match_shape_results as R
M=R.M
NOW=datetime(2026,11,10,12,tzinfo=timezone.utc)


class IntegrityTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.folder=self.root/I.RELATIVE
  self.folder.mkdir(parents=True)
  for name in I.DEPENDENCIES:
   path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(name)
  M.atomic(self.folder/'registration.json',{'fingerprints':{},'registered_at':(NOW-timedelta(days=9)).isoformat()})
  self.approved={'registration_sha256':I.file_hash(self.folder/'registration.json'),'fingerprints':I.fingerprints(self.root),'previous_manifest_sha256':None}
  with M.locked(self.folder):self.key=I.register(self.root,self.approved,NOW-timedelta(hours=1))
  self.record={'id':'a'*64,'fixture_key':'9|4|1|2','captured_at':(NOW-timedelta(days=3)).isoformat(),'actual_stake':0,
               'registration_sha256':I.file_hash(self.folder/'registration.json'),
               'market':'total_games','components':{'player1_id':'1'},
               'quote':{'scheduled_start':'2026-11-08T12:00:00Z','line':22.5}}
  M.immutable(self.folder/'captures'/(self.record['id']+'.json'),self.record)
  self.row={'status':'excluded','reason':'native_schedule_walkover_grading_review','score':'w/o','result_date':'2026-11-08','evidence':'today_atp.csv','source_sha256':'b'*64}
 def retained(self,extra=None,clock=NOW):
  I.retain(self.folder,{self.record['fixture_key']:extra or self.row},clock)
 def summarize(self,root,clock):
  outcomes={self.record['id']:M.outcome(self.record,[],clock,self.record['registration_sha256'])}
  M.atomic(self.folder/'outcomes.json',outcomes)
  return outcomes
 def test_walkover_survives_disappearing_schedule_and_repeated_refresh(self):
  self.retained(clock=NOW-timedelta(days=1))
  with patch.object(R,'supplemental',return_value={}),patch.object(M,'summarize',side_effect=self.summarize):
   report=R.refresh_with_results(self.root,clock=NOW,settle_only=True)
   self.assertEqual(report[self.record['id']]['status'],'excluded')
   before=(self.folder/'outcomes.json').read_bytes()
   R.refresh_with_results(self.root,clock=NOW+timedelta(hours=1),settle_only=True)
   self.assertEqual(before,(self.folder/'outcomes.json').read_bytes())
 def test_registration_is_explicit_idempotent_and_chained(self):
  self.assertEqual(I.verify(self.root,NOW)[0],self.key)
  self.assertEqual(I.register(self.root,self.approved,NOW),self.key)
  (self.root/I.DEPENDENCIES[0]).write_text('reviewed upgrade')
  with self.assertRaisesRegex(ValueError,'code_changed'):I.verify(self.root,NOW)
  next_approval={**self.approved,'fingerprints':I.fingerprints(self.root),'previous_manifest_sha256':self.key}
  second=I.register(self.root,next_approval,NOW)
  self.assertEqual(I.verify(self.root,NOW)[1]['previous_manifest_sha256'],self.key)
  self.assertNotEqual(second,self.key)
 def test_missing_registration_does_not_register_itself(self):
  (self.folder/'operational/active.json').unlink()
  with self.assertRaisesRegex(ValueError,'registration_missing'):I.verify(self.root,NOW)
  self.assertFalse((self.folder/'operational/active.json').exists())
 def test_edited_manifest_is_rejected(self):
  path=self.folder/'operational/registrations'/(self.key+'.json')
  value=I.read(path);value['scope']='edited';path.write_text(json.dumps(value))
  with self.assertRaisesRegex(ValueError,'hash_mismatch'):I.verify(self.root,NOW)
 def test_guard_blocks_both_capture_and_settlement_preserving_outputs(self):
  for filename in ('report.json','outcomes.json'):M.atomic(self.folder/filename,{'saved':'evidence'})
  before={name:(self.folder/name).read_bytes() for name in ('report.json','outcomes.json')}
  for name in (I.DEPENDENCIES[0],I.DEPENDENCIES[1],I.DEPENDENCIES[4]):
   path=self.root/name;old=path.read_bytes();path.write_text('unexpected edit')
   with patch.object(M,'capture') as capture,patch.object(M,'summarize') as settle:
    report=R.refresh_with_results(self.root,clock=NOW)
    self.assertEqual(report['capture']['state'],'BLOCKED');capture.assert_not_called();settle.assert_not_called()
   self.assertEqual(before,{name:(self.folder/name).read_bytes() for name in before})
   path.write_bytes(old)
 def test_retained_evidence_is_exact_and_keeps_first_observation(self):
  self.retained(clock=NOW-timedelta(days=1));before=list((self.folder/'result-evidence').glob('*.json'))[0].read_bytes()
  self.retained();self.assertEqual(before,list((self.folder/'result-evidence').glob('*.json'))[0].read_bytes())
  self.assertEqual(len(I.evidence(self.folder,[self.record],NOW)[self.record['fixture_key']]),1)
  other={**self.record,'fixture_key':'10|4|1|2'}
  self.assertEqual(I.evidence(self.folder,[other],NOW),{})
 def test_corruption_time_and_limits_fail_closed(self):
  self.retained();path=list((self.folder/'result-evidence').glob('*.json'))[0];original=path.read_bytes()
  for change,reason in ((lambda x:x['records'][self.record['fixture_key']].update(score='6-0 6-0'),'hash_mismatch'),(lambda x:x.update(observed_at=(NOW+timedelta(days=1)).isoformat()),'observation_invalid')):
   packet=json.loads(original);change(packet);path.write_text(json.dumps(packet))
   with self.assertRaisesRegex(ValueError,reason):I.evidence(self.folder,[self.record],NOW)
  path.write_bytes(original)
  with patch.object(I,'MAX_BYTES',10):
   with self.assertRaisesRegex(ValueError,'too_large'):I.evidence(self.folder,[self.record],NOW)
  with patch.object(I,'MAX_FILES',0):
   with self.assertRaisesRegex(ValueError,'limit_exceeded'):I.evidence(self.folder,[self.record],NOW)
 def test_reasons_are_compatible_but_completed_result_is_flagged(self):
  self.retained(clock=NOW-timedelta(days=1))
  replacement={**self.row,'reason':'native_draw_opponent_changed_grading_review','evidence':'games_atp.csv','replacement_results':[dict(tour_id='9',round_id='4',winner_id='1',loser_id='3',date='2026-11-08',result='6-3 6-1')]}
  self.retained(replacement);rows=I.evidence(self.folder,[self.record],NOW)[self.record['fixture_key']]
  excluded,notices=I.resolve(self.record,{'status':'pending'},{},rows)
  self.assertEqual(excluded['status'],'excluded');self.assertEqual(notices,[]);self.assertEqual(len(rows),2)
  settled={'status':'settled','side1_outcome':1}
  result,notices=I.resolve(self.record,settled,excluded,rows)
  self.assertEqual(result,settled);self.assertEqual(len(notices),1)
 def test_quarantines_and_existing_settlements_cannot_be_overridden(self):
  self.retained();rows=I.evidence(self.folder,[self.record],NOW)[self.record['fixture_key']]
  quarantined={'status':'quarantined','reason':'capture_integrity'}
  settled={'status':'settled','side1_outcome':1}
  self.assertEqual(I.resolve(self.record,quarantined,settled,rows)[0],quarantined)
  self.assertEqual(I.resolve(self.record,{'status':'pending'},settled,rows)[0],settled)
  changed={**settled,'side1_outcome':-1}
  outcome,notices=I.resolve(self.record,changed,settled,rows)
  self.assertEqual(outcome,settled);self.assertEqual(len(notices),1)
 def test_evidence_validation_does_not_overwrite_bad_source_file(self):
  self.retained();path=list((self.folder/'result-evidence').glob('*.json'))[0]
  path.write_text('{}');bad=path.read_bytes()
  with self.assertRaises(ValueError):I.evidence(self.folder,[self.record],NOW)
  self.assertEqual(bad,path.read_bytes())
 def test_single_lock_blocks_concurrent_refresh_before_changes(self):
  with M.locked(self.folder),patch.object(M,'capture') as capture,patch.object(M,'summarize') as settle:
   with self.assertRaises(OSError):R.refresh_with_results(self.root,clock=NOW)
   capture.assert_not_called();settle.assert_not_called()
 def test_guarded_new_capture_has_binding_and_old_capture_does_not(self):
  fresh=copy.deepcopy(self.record);fresh['id']='c'*64;fresh['captured_at']=NOW.isoformat()
  fresh['quote']['scheduled_start']=(NOW+timedelta(hours=2)).isoformat()
  # Existing unbound captures are never retrospectively certified by timestamp.
  late=copy.deepcopy(fresh);late['id']='d'*64
  M.immutable(self.folder/'captures'/(late['id']+'.json'),late)
  def capture(root,clock,receipt):
   self.assertIs(M.map_quote,R.resolve_quote)
   path=self.folder/'captures'/(fresh['id']+'.json')
   created=not path.exists()
   if created:M.immutable(path,fresh)
   return {'state':'CAPTURED' if created else 'NO_NEW_ELIGIBLE_CONTRACTS','captured':int(created)}
  with patch.object(R,'supplemental',return_value={}),patch.object(M,'capture',side_effect=capture),patch.object(M,'summarize',return_value={'ok':True}):
   R.refresh_with_results(self.root,clock=NOW,receipt={'test':True})
   R.refresh_with_results(self.root,clock=NOW+timedelta(minutes=1),receipt={'test':True})
  rows={p.stem:I.read(p) for p in (self.folder/'operational/cohorts').glob('*.json')}
  self.assertEqual(rows[fresh['id']]['operational_hash_at_capture'],self.key)
  self.assertEqual(rows[late['id']]['operational_hash_at_capture'],'unrecorded')
  self.assertEqual(rows[self.record['id']]['operational_hash_at_capture'],'unrecorded')
  self.assertEqual(M.read(self.folder/'capture-status.json')['captured'],0)
 def test_invalid_replacement_and_before_start_evidence_are_rejected(self):
  self.retained(clock=NOW-timedelta(days=3))
  with self.assertRaisesRegex(ValueError,'before_start'):I.evidence(self.folder,[self.record],NOW)
  path=next((self.folder/'result-evidence').glob('*.json'));path.unlink()
  replacement={**self.row,'reason':'native_draw_opponent_changed_grading_review','evidence':'games_atp.csv','replacement_results':[dict(tour_id='9',round_id='4',winner_id='1',loser_id='3',date='2026-11-08',result='1-0 RET')]}
  self.retained(replacement)
  with self.assertRaisesRegex(ValueError,'score_invalid'):I.evidence(self.folder,[self.record],NOW,M.complete_score)
 def test_saved_reporting_overlays_health_without_writing_results(self):
  M.atomic(self.folder/'report.json',{'fixtures':1,'capture':{'state':'CAPTURED'}})
  original=(self.folder/'report.json').read_bytes()
  M.atomic(self.folder/'capture-status.json',{'state':'BLOCKED','reason':'test mismatch'})
  M.atomic(self.folder/'operational/status.json',{'state':'BLOCKED','reason':'test mismatch'})
  result=I.report_with_health(self.root)
  self.assertEqual(result['capture']['state'],'BLOCKED')
  self.assertEqual(result['operational']['reason'],'test mismatch')
  self.assertEqual(original,(self.folder/'report.json').read_bytes())
 def test_registration_refuses_naive_or_reversed_upgrade_clock(self):
  with self.assertRaisesRegex(ValueError,'time_naive'):I.register(self.root,self.approved,NOW.replace(tzinfo=None))
  (self.root/I.DEPENDENCIES[0]).write_text('upgrade')
  approval={**self.approved,'fingerprints':I.fingerprints(self.root),'previous_manifest_sha256':self.key}
  with self.assertRaisesRegex(ValueError,'time_before_parent'):I.register(self.root,approval,NOW-timedelta(hours=2))
  self.assertEqual(I.read(self.folder/'operational/active.json')['manifest_sha256'],self.key)
 def test_conflict_remains_open_until_explicit_dated_resolution(self):
  self.retained(clock=NOW-timedelta(days=1))
  settled={'status':'settled','side1_outcome':1}
  with patch.object(R,'supplemental',return_value={}),patch.object(M,'outcome',return_value=settled),patch.object(M,'summarize',side_effect=self.summarize):
   R.refresh_with_results(self.root,clock=NOW,settle_only=True)
   R.refresh_with_results(self.root,clock=NOW+timedelta(minutes=1),settle_only=True)
   self.assertEqual(I.read(self.folder/'operational/status.json')['state'],'REVIEW_REQUIRED')
   conflicts=list((self.folder/'operational/conflicts').glob('*.json'));self.assertEqual(len(conflicts),1)
   I.immutable(self.folder/'operational/resolutions'/conflicts[0].name,dict(conflict_sha256=conflicts[0].stem,reviewed_at=NOW.isoformat(),decision='accept_recorded_outcome',rationale='Synthetic manual review'))
   R.refresh_with_results(self.root,clock=NOW+timedelta(minutes=2),settle_only=True)
   self.assertEqual(I.read(self.folder/'operational/status.json')['state'],'VERIFIED')
 def test_resolved_quarantine_and_unfinished_to_complete_are_not_silent(self):
  excluded={'status':'excluded','reason':'unfinished_or_unsupported_score'}
  for old,new in ((excluded,{'status':'settled'}),(excluded,{'status':'quarantined'}),({'status':'settled'},{'status':'quarantined'})):
   self.assertEqual(len(I.resolve(self.record,new,old,[])[1]),1)
 def test_frozen_source_and_capture_tampering_are_blocked(self):
  name='scripts/frozen.py';path=self.root/name;path.write_text('frozen')
  M.atomic(self.folder/'registration.json',{'fingerprints':{name:I.file_hash(path)}})
  approval={**self.approved,'registration_sha256':I.file_hash(self.folder/'registration.json'),'previous_manifest_sha256':self.key}
  # Separate fixture registration with the new original hash, not an upgrade.
  (self.folder/'operational/active.json').unlink();approval['previous_manifest_sha256']=None
  I.register(self.root,approval,NOW);path.write_text('changed')
  with self.assertRaisesRegex(ValueError,'frozen_code_changed'):I.verify(self.root,NOW)
  I.record_cohorts(self.folder,[self.record],self.key,{'registered_at':NOW.isoformat()},NOW)
  changed={**self.record,'actual_stake':1}
  with self.assertRaisesRegex(ValueError,'operational_capture_changed'):I.record_cohorts(self.folder,[changed],self.key,{'registered_at':NOW.isoformat()},NOW)
 def test_source_race_sets_blocked_health_without_settlement(self):
  with patch.object(R,'supplemental',side_effect=RuntimeError('native_results_changed_during_reconciliation')),patch.object(M,'summarize') as settle:
   result=R.refresh_with_results(self.root,clock=NOW,settle_only=True)
   self.assertEqual(result['capture']['state'],'BLOCKED');settle.assert_not_called()
 def test_corrupt_health_isolated_from_shared_reporters(self):
  from match_shape_reporting import weekly_text
  metric=dict(roi_pct=None,calibration={'n':0},wins=0,losses=0,pushes=0,profit=0,stake=0,pending=0,overdue=0,excluded=0,quarantined=0)
  report=dict(fixtures=1,contracts=2,settled_fixtures=0,capture={'state':'CAPTURED'},arms={a:{m:metric for m in ('total_games','game_handicap')} for a in ('current','T1')})
  M.atomic(self.folder/'report.json',report);before=(self.folder/'report.json').read_bytes()
  for filename in ('capture-status.json','operational/status.json'):
   for bad in ('{','[]','null'):
    path=self.folder/filename;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(bad)
    overlay=I.report_with_health(self.root)
    self.assertEqual(overlay['capture']['state'],'UNREADABLE')
    self.assertIn('health unreadable',weekly_text(overlay))
    self.assertEqual(before,(self.folder/'report.json').read_bytes())
   path.unlink()
  self.assertIn('unverified registration',weekly_text({**report,'operational':{'state':'BLOCKED','reason':None}}))

if __name__=='__main__':unittest.main()
