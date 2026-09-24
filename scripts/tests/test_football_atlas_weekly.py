import copy
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import tempfile

sys.path.insert(0, str(Path(__file__).parents[1]))
import football_atlas_weekly as w

NOW = datetime(2026, 9, 22, 18, tzinfo=timezone.utc)


def history():
    return {oid: {'players': {'0': [{'createdAt': (NOW-timedelta(minutes=4)).isoformat(),
                                   'price': price, 'active': True}]}}
            for oid, price in zip(('101', '102', '103'), (2.5, 3.2, 3.1))}


class WeeklyAtlasTests(unittest.TestCase):
    def test_rate_limit_retry_is_bounded_and_quota_is_not_retried(self):
        api = w.OddsPapi('test-only-key')
        with patch.object(w, 'fetch_json', side_effect=[w.RateLimited(6), []]) as fetch, patch.object(w.time, 'sleep'):
            self.assertEqual(api.get('fixtures'), [])
            self.assertEqual(fetch.call_count, 2)
        with patch.object(w, 'fetch_json', side_effect=RuntimeError('monthly request allowance exhausted')) as fetch, patch.object(w.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError,'monthly'): api.get('fixtures')
            self.assertEqual(fetch.call_count, 1)
        with patch.object(w, 'fetch_json', side_effect=w.RateLimited(6)) as fetch, patch.object(w.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError,'bounded'): api.get('fixtures')
            self.assertEqual(fetch.call_count, 3)

    def test_utf8_bom_calendar_response(self):
        class Response:
            status_code = 200
            content = b'\xef\xbb\xbf{"TeamInfo":[]}'
        with patch.object(w.requests, 'get', return_value=Response()):
            self.assertEqual(w.fetch_json('https://calendar.example'), {'TeamInfo': []})

    def test_collection_rejects_partial_fixture_feed(self):
        f = dict(id='g1',league='premier-league',home='Arsenal',away='Chelsea',kickoff=NOW.isoformat(),status=-1,score=[2,1],season='2026-2027')
        old=dict(teams=['Arsenal','Chelsea'],leagues=list(w.TOURNAMENTS),seasons=['2026-2027'],fixtures=[])
        class EmptyAPI:
            calls = {}
            def quota(self): return 200
            def get(self, *args, **kwargs): return []
        with tempfile.TemporaryDirectory() as directory, patch.object(w.legacy, 'calendar', return_value=[f]):
            with self.assertRaisesRegex(ValueError, 'Incomplete fixture reconciliation'):
                w.collect(old, {'through':'2026-09-20'}, Path(directory), NOW+timedelta(days=1), EmptyAPI())

    def test_collection_adds_validated_match_then_is_idempotent(self):
        f = dict(id='g1',league='premier-league',home='Arsenal',away='Chelsea',kickoff=NOW.isoformat(),status=-1,score=[2,1],season='2026-2027')
        p = dict(fixtureId='id1',tournamentId=17,sportId=10,participant1Name='Arsenal',participant2Name='Chelsea',startTime=NOW.isoformat(),statusId=2)
        old=dict(teams=['Arsenal','Chelsea'],leagues=list(w.TOURNAMENTS),seasons=['2026-2027'],fixtures=[])
        class API:
            calls = {}
            def quota(self): return 200
            def get(self, endpoint, **kwargs):
                if endpoint == 'fixtures': return [p] if kwargs['tournamentId'] == 17 else []
                return {'fixtureId':'id1', 'bookmakers':{'pinnacle':{'markets':{'101':{'outcomes':history()}}}}}
        with tempfile.TemporaryDirectory() as directory, patch.object(w.legacy, 'calendar', return_value=[f]):
            new, report = w.collect(old, {'through':'2026-09-20'}, Path(directory), NOW+timedelta(days=1), API())
            self.assertEqual(report['newMatches'], 1)
            self.assertEqual(new['fixtures'][0][6:], [2,1,2.5,3.2,3.1,2])
            again, report = w.collect(new, {'through':'2026-09-22'}, Path(directory), NOW+timedelta(days=1), API())
            self.assertEqual(again, new)
            self.assertEqual(report['newMatches'], 0)

    def test_strict_pre_match_and_draw_orientation(self):
        h = history()
        h['101']['players']['0'] += [dict(createdAt=NOW.isoformat(), price=99, active=True)]
        self.assertEqual(w.prices_at_cutoff(h, NOW)[0], [2.5, 3.2, 3.1])

    def test_suspension_is_not_ignored(self):
        h = history()
        h['102']['players']['0'].append(dict(createdAt=(NOW-timedelta(seconds=5)).isoformat(),price=3.2,active=False))
        with self.assertRaisesRegex(ValueError, 'suspended'):
            w.prices_at_cutoff(h, NOW)

    def test_unchanged_price_is_not_rejected_as_old(self):
        h = history()
        for outcome in h.values():
            outcome['players']['0'][0]['createdAt'] = (NOW-timedelta(hours=2)).isoformat()
        self.assertEqual(w.prices_at_cutoff(h, NOW)[0], [2.5, 3.2, 3.1])

    def test_conflicting_ties_missing_outcomes_and_invalid_books(self):
        h = history()
        h['101']['players']['0'].append({**h['101']['players']['0'][0], 'price': 2.8})
        with self.assertRaisesRegex(ValueError,'Conflicting'): w.prices_at_cutoff(h,NOW)
        h = history(); del h['102']
        with self.assertRaisesRegex(ValueError,'Missing'): w.prices_at_cutoff(h,NOW)
        h = history(); h['101']['players']['0'][0]['price'] = 1.01
        with self.assertRaisesRegex(ValueError,'overround'): w.prices_at_cutoff(h,NOW)

    def test_completed_identity_and_timing_cross_check(self):
        f = dict(id='g1',league='premier-league',home='Arsenal',away='Chelsea',kickoff=NOW.isoformat(),status=-1,score=[2,1],season='2026-2027')
        p = dict(fixtureId='id1',tournamentId=17,sportId=10,participant1Name='Arsenal',participant2Name='Chelsea',startTime=NOW.isoformat(),trueStartTime=(NOW+timedelta(minutes=3)).isoformat())
        old={'teams':['Arsenal','Chelsea']}
        self.assertEqual(w.match_fixture(p,'premier-league',[f],{},old)[1],NOW)
        with self.assertRaisesRegex(ValueError,'timing review'):
            w.match_fixture({**p,'trueStartTime':(NOW+timedelta(hours=1)).isoformat()},'premier-league',[f],{},old)
        with self.assertRaisesRegex(ValueError,'Unconfirmed'):
            w.match_fixture(p,'premier-league',[{**f,'status':0}],{},old)
        with self.assertRaisesRegex(ValueError,'mismatch'):
            w.match_fixture(p,'premier-league',[{**f,'home':'Chelsea','away':'Arsenal'}],{},old)

    def test_canonical_names_never_use_fuzzy_matching(self):
        self.assertEqual(w.canonical('x',['Arsenal FC','Arsenal'],{},['Arsenal']), 'Arsenal')
        with self.assertRaisesRegex(ValueError,'Unreviewed'):
            w.canonical('x',['Arsena1'],{},['Arsenal'])
        with self.assertRaisesRegex(ValueError,'conflicting'):
            w.canonical('x',['Arsenal','Chelsea'],{},['Arsenal','Chelsea'])

    def test_merge_keeps_existing_rows_and_tags_last_pre_match(self):
        old=dict(teams=['Arsenal','Chelsea'],leagues=['premier-league'],seasons=['2026-2027'],fixtures=[['old','2026-09-15',0,0,0,1,1,0,2.5,3.2,3.1,1]])
        prior=copy.deepcopy(old)
        f=dict(id='g1',league='premier-league',home='Arsenal',away='Chelsea',kickoff=NOW.isoformat(),score=[2,1],season='2026-2027')
        new=w.merge_archive(old,[(f,[2.5,3.2,3.1],'id1')])
        self.assertEqual(old,prior);self.assertEqual(new['fixtures'][0],old['fixtures'][0]);self.assertEqual(new['fixtures'][-1][-1],2)
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            w.merge_archive(new,[(f,[2.5,3.2,3.1],'id1')])


if __name__ == '__main__': unittest.main()
