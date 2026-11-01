import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import tennis_elo_health as h


class EloSourceHealth(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.folder=self.root/'data/tennis-elo-source/atp'
        (self.folder/'snapshots').mkdir(parents=True)
        (self.folder/'raw').mkdir()
        self.now=datetime(2026,11,1,14,tzinfo=timezone.utc)
        self.raw=b'<html>validated source evidence</html>'
        self.rawhash=hashlib.sha256(self.raw).hexdigest()
        (self.folder/'raw'/f'{self.rawhash}.html').write_bytes(self.raw)
        self.data={'version':'ta-elo-isolated-v1','tour':'ATP','live_writes':False,
                   'publication_date':'2026-10-26','observed_at':'2026-11-01T11:51:20+00:00',
                   'raw_sha256':self.rawhash,'players':[{'oncourt_id':1,'overall':1600}],
                   'gaps':[{'name':'Unmapped'}],'source_row_count':2}
        self.status={'live_writes':False,'state':'VALIDATED','last_attempt_at':'2026-11-01T11:51:18+00:00'}
        self.write()
    def write(self):
        raw=json.dumps(self.data).encode();p=self.folder/'snapshots/good.json';p.write_bytes(raw)
        self.status['last_good']={'snapshot':'snapshots/good.json','sha256':hashlib.sha256(raw).hexdigest(),
                                 'publication_date':self.data['publication_date'],'observed_at':self.data['observed_at']}
        (self.folder/'status.json').write_text(json.dumps(self.status))
    def read(self):return h.published_source(self.root,'ATP',self.now)[0]
    def test_current_source_is_research_only_and_not_live_proof(self):
        s={'status':'MISSING','elo_lineage':'UNVERIFIED','fixtures':[{'missing_elo_keys':[[2,'I.hard']]}]}
        h.annotate_sources(self.root,s,[{'player_id':1,'surface':'Overall','elo':1650}],self.now,{2:'Missing Player'})
        self.assertEqual(s['elo_sources']['published_research']['ATP']['state'],'CURRENT')
        self.assertEqual(s['elo_sources']['live']['state'],'PROVENANCE_UNVERIFIED')
        self.assertEqual(s['status'],'MISSING');self.assertEqual(s['elo_lineage'],'UNVERIFIED')
        self.assertEqual(s['published_overall_parity']['different_players'],1)
        self.assertEqual(s['missing_elo_players'][0]['name'],'Missing Player')
        self.assertFalse(s['missing_elo_players'][0]['available_in_verified_published_snapshot'])
    def test_missing_source_is_explicit(self):
        self.assertEqual(h.published_source(self.root,'WTA',self.now)[0]['state'],'MISSING_EVIDENCE')
    def test_snapshot_tampering_rejected(self):
        (self.folder/'snapshots/good.json').write_text('{}')
        self.assertEqual(self.read()['state'],'INVALID_EVIDENCE')
    def test_raw_tampering_rejected(self):
        (self.folder/'raw'/f'{self.rawhash}.html').write_bytes(b'changed')
        self.assertEqual(self.read()['state'],'INVALID_EVIDENCE')
    def test_stale_publication_even_with_recent_attempt(self):
        self.data['publication_date']='2026-10-01';self.write()
        self.assertEqual(self.read()['state'],'STALE_PUBLICATION')
    def test_stale_observation_not_healed_by_new_attempt(self):
        self.data['observed_at']='2026-10-28T11:00:00Z';self.write()
        self.assertEqual(self.read()['state'],'STALE_OBSERVATION')
    def test_failed_latest_attempt_keeps_valid_old_evidence_but_warns(self):
        self.status['state']='FAILED';self.write()
        r=self.read();self.assertEqual(r['state'],'LAST_ATTEMPT_FAILED_OR_INCOMPLETE');self.assertTrue(r['integrity_verified'])
    def test_future_source_rejected(self):
        self.data['observed_at']='2026-11-02T11:00:00Z';self.write()
        self.assertEqual(self.read()['state'],'INVALID_EVIDENCE')
    def test_pointer_metadata_mismatch_rejected(self):
        self.status['last_good']['publication_date']='2026-10-27'
        (self.folder/'status.json').write_text(json.dumps(self.status))
        self.assertEqual(self.read()['state'],'INVALID_EVIDENCE')
    def test_path_escape_rejected(self):
        self.status['last_good']['snapshot']='../../outside.json'
        (self.folder/'status.json').write_text(json.dumps(self.status))
        self.assertEqual(self.read()['state'],'INVALID_EVIDENCE')
    def test_paper_source_cannot_claim_to_write_live(self):
        self.data['live_writes']=True;self.write()
        self.assertEqual(self.read()['state'],'INVALID_EVIDENCE')
    def test_duplicate_mapping_rejected(self):
        self.data['players']*=2;self.data['source_row_count']=3;self.write()
        self.assertEqual(self.read()['state'],'INVALID_EVIDENCE')
    def test_invalid_rating_cannot_reach_parity_comparison(self):
        for value in ('not a number', float('nan'), float('inf'), -1):
            with self.subTest(value=value):
                self.data['players'][0]['overall']=value;self.write()
                self.assertEqual(self.read()['state'],'INVALID_EVIDENCE')

if __name__=='__main__':unittest.main()
