"""Verified additions survive independent held fixtures and retry exactly once."""
import copy
from pathlib import Path
import tempfile
import unittest
from datetime import datetime,timezone
from unittest.mock import patch
import test_manager_monthly_preservation as monthly
from test_manager_monthly_preservation import collector, read, write

class ProviderCompetitionTests(unittest.TestCase):
    def test_null_group_is_a_known_parse_failure(self):
        with self.assertRaises(ValueError):collector.normalize_day({'leagues':[None]})

    def test_corrupt_queue_is_retained_and_rebuilt_from_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);p=root/'pending-fixtures.json';p.write_text('{broken')
            row={'id':'held','reason':'x'}
            write(root/'refresh-report.json',{'checkedAt':'2026-11-01T00:00:00Z','pending':[row]})
            collector.save_pending_queue(p,[row],[],'2026-11-12T00:00:00Z')
            self.assertEqual(read(p)['fixtures']['held']['firstSeenAt'],'2026-11-01T00:00:00Z')
            self.assertEqual(len(list(root.glob('pending-fixtures-invalid-*'))),1)
    def test_pending_cache_expires_but_offline_uses_saved_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'cache.json'
            stamp=datetime(2026,11,1,tzinfo=timezone.utc).timestamp()
            write(p,{'checkedAt':'2026-11-01T00:00:00+00:00'})
            with patch.object(collector.time,'time',return_value=stamp+30):
                self.assertTrue(collector.cache_usable(p))
            with patch.object(collector.time,'time',return_value=stamp+86401):
                self.assertFalse(collector.cache_usable(p))
                self.assertTrue(collector.cache_usable(p,True))
    def test_stable_ids_cover_changed_groups_without_name_matching(self):
        payload={'leagues':[{'id':1000005083,'primaryId':54,'matches':[]},
                            {'id':1000006325,'primaryId':'53','matches':[]},
                            {'id':938366,'primaryId':38,'name':'Bundesliga','matches':[]},
                            {'id':516,'name':'Ligue 1','matches':[]}]}
        self.assertEqual([g['league'] for g in collector.normalize_day(payload)],['bundesliga','ligue-1'])

    def test_conflicting_provider_id_rejected(self):
        m={'id':1,'home':{'name':'A'},'away':{'name':'B'}}
        with self.assertRaisesRegex(ValueError,'Conflicting duplicate'):
            collector.normalize_day({'leagues':[{'id':54,'matches':[m,{**m,'home':{'name':'C'}}]}]})

    def test_exact_partition_rejects_missing_duplicate_and_overlap(self):
        candidates=[['a'],['b']]
        held={'id':'b','code':'identity_review','reason':'review','date':'2026-11-01','home':'A','away':'B'}
        self.assertTrue(collector.fixture_quarantine_complete(candidates,[{'id':'a'}],[held]))
        for added,pending in [([], [held]),([{'id':'a'},{'id':'a'}],[held]),([{'id':'b'}],[held])]:
            self.assertFalse(collector.fixture_quarantine_complete(candidates,added,pending))

class FixtureIsolationTests(unittest.TestCase):
    def test_global_manager_failure_retains_archive_and_returns_explicit_warning(self):
        helper=monthly.MonthlyPreservationTests()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);helper.fixture_tree(root)
            p=root/'src/data/manager-atlas-release.json';before=p.read_bytes()
            with patch.object(monthly.weekly,'ROOT',root),patch.object(monthly.weekly,'refresh',side_effect=TimeoutError('bounded')):
                result=monthly.weekly.refresh_or_retain(root/'state')
            self.assertFalse(result['changed']);self.assertEqual(result['publicationState'],'retained_manager_failure')
            self.assertEqual(p.read_bytes(),before)
            self.assertEqual(result['added'],0)

    def test_null_status_holds_one_fixture_without_aborting(self):
        helper=monthly.MonthlyPreservationTests()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);helper.fixture_tree(root)
            p=root/'state/managers/dates-v2/2026-10-30.json';cache=read(p)
            cache['leagues'][0]['matches'][0]['status']=None;write(p,cache)
            result=helper.run_offline(root)
            self.assertFalse(result['changed']);self.assertEqual(result['pending'][0]['code'],'invalid_evidence')
    def test_good_fixture_publishes_bad_fixture_retries_then_resolves_once(self):
        helper=monthly.MonthlyPreservationTests()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);before=helper.fixture_tree(root)
            atlas=read(root/'public/football-test.json')
            second=copy.deepcopy(atlas['fixtures'][0]);second[0]='test-held';second[1]='2026-10-31'
            atlas['fixtures'].append(second);write(root/'public/football-test.json',atlas)
            cache=read(root/'state/managers/dates-v2/2026-10-30.json')
            cache['date']='2026-10-31';cache['leagues'][0]['matches'][0]['id']=999999
            write(root/'state/managers/dates-v2/2026-10-31.json',cache)
            review=read(root/'scripts/config/manager-fixture-reviews.json')['fotmob:5868120']
            row={**review,'providerMatchId':'999999','date':'2026-10-31'}
            row['coaches']=[{'id':'unknown-coach','name':'Test unresolved manager'},review['coaches'][1]]
            write(root/'state/managers/matches/999999.json',row)
            result=helper.run_offline(root)
            self.assertEqual(result['added'],1);self.assertEqual(len(result['pending']),1)
            current=read(root/'public'/result['manifest']['indexUrl'].lstrip('/'))
            rows={r[0]:r for r in current['rows']}
            self.assertTrue(all(rows[r[0]]==r for r in before['rows']))
            first=result['pending'][0]['firstSeenAt']
            again=helper.run_offline(root)
            self.assertEqual(again['added'],0);self.assertFalse(again['changed'])
            self.assertEqual(again['pending'][0]['firstSeenAt'],first)
            row['coaches']=review['coaches'];write(root/'state/managers/matches/999999.json',row)
            fixed=helper.run_offline(root);self.assertEqual(fixed['added'],1)
            self.assertEqual(fixed['pending'],[])
            self.assertEqual(read(root/'state/managers/pending-fixtures.json')['fixtures']['test-held']['state'],'verified')
            self.assertFalse(helper.run_offline(root)['changed'])

    def test_legacy_incomplete_cache_is_never_reused(self):
        helper=monthly.MonthlyPreservationTests()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);helper.fixture_tree(root)
            p=root/'state/managers/dates-v2/2026-10-30.json'
            write(root/'state/managers/dates/2026-10-30.json',read(p)['leagues']);p.unlink()
            result=helper.run_offline(root)
            self.assertEqual(result['added'],0)
            self.assertEqual(result['pending'][0]['code'],'source_unavailable')

if __name__=='__main__':unittest.main()
