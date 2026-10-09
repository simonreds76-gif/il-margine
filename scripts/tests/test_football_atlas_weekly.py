import copy
import gzip
import json
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import subprocess
import unittest
from unittest.mock import patch
import tempfile

sys.path.insert(0, str(Path(__file__).parents[1]))
import football_atlas_weekly as w
import atlas_fixture_board as fb

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
        new=w.merge_archive(old,[(f,[2.5,3.2,3.1],'id1',2)])
        self.assertEqual(old,prior);self.assertEqual(new['fixtures'][0],old['fixtures'][0]);self.assertEqual(new['fixtures'][-1][-1],2)
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            w.merge_archive(new,[(f,[2.5,3.2,3.1],'id1',2)])

    def test_fallback_is_complete_and_never_cherry_picks_prices(self):
        better = history()
        better['101']['players']['0'][0]['price'] = 2.6
        picked = w.select_market({'pinnacle': history(), 'bet365': better}, NOW)
        self.assertEqual((picked['bookmaker'], picked['code']), ('pinnacle', 2))
        partial = history(); del partial['102']
        picked = w.select_market({'pinnacle': partial, 'bet365': better}, NOW)
        self.assertEqual((picked['bookmaker'], picked['basis'], picked['code']), ('bet365', 'bet365-last-pre-match', 3))
        self.assertEqual(picked['odds'], [2.6, 3.2, 3.1])
        self.assertIn('Missing', picked['rejected']['pinnacle'])
        other_partial = history(); del other_partial['101']
        with self.assertRaisesRegex(ValueError, 'No validated'):
            w.select_market({'pinnacle': partial, 'bet365': other_partial}, NOW)

    def test_fallback_must_pass_the_same_timing_and_suspension_checks(self):
        for invalid in ('suspended', 'in-play', 'conflicting', 'impossible'):
            with self.subTest(invalid=invalid):
                h = history()
                if invalid == 'suspended': h['102']['players']['0'][0]['active'] = False
                if invalid == 'in-play': h['102']['players']['0'][0]['createdAt'] = NOW.isoformat()
                if invalid == 'conflicting': h['102']['players']['0'].append({**h['102']['players']['0'][0], 'price': 4})
                if invalid == 'impossible': h['102']['players']['0'][0]['price'] = 1.01
                with self.assertRaisesRegex(ValueError, 'No validated'):
                    w.select_market({'bet365': h}, NOW)

    def test_one_history_request_caches_both_books_and_checks_fixture_identity(self):
        p = dict(fixtureId='id1', startTime=NOW.isoformat())
        class API:
            def __init__(self): self.calls = []
            def get(self, endpoint, **kwargs):
                self.calls.append((endpoint, kwargs))
                return {'fixtureId': 'id1', 'bookmakers': {'bet365': {'markets': {'101': {'outcomes': history()}}}}}
        api = API()
        with tempfile.TemporaryDirectory() as directory:
            selected, digest = w.historical_market(api, p, NOW, Path(directory), NOW)
            again, same = w.historical_market(api, p, NOW, Path(directory), NOW)
            self.assertEqual(selected, again); self.assertEqual(digest, same)
            self.assertEqual(len(api.calls), 1)
            self.assertEqual(api.calls[0][1]['bookmakers'], 'pinnacle,bet365')
            self.assertEqual(selected['code'], 3)
            with self.assertRaisesRegex(ValueError, 'fixture mismatch'):
                w.historical_market(api, {**p, 'fixtureId': 'id2'}, NOW, Path(directory), NOW)

    def test_legacy_cache_is_reused_or_upgraded_only_when_needed(self):
        from unittest.mock import Mock
        p = dict(fixtureId='id1', startTime=NOW.isoformat())
        saved = {'fixtureId': 'id1', 'signature': [p['startTime'], None, None],
                 'bookmaker': 'pinnacle', 'outcomes': history(), 'responseSha256': 'old'}
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / 'id1.json.gz'
            cache.write_bytes(gzip.compress(json.dumps(saved).encode()))
            api = Mock()
            self.assertEqual(w.historical_market(api, p, NOW, Path(directory), NOW)[1], 'old')
            api.get.assert_not_called()
            saved['outcomes'] = {}
            cache.write_bytes(gzip.compress(json.dumps(saved).encode()))
            api.get.return_value = {'fixtureId': 'id1', 'bookmakers': {'bet365': {'markets': {'101': {'outcomes': history()}}}}}
            self.assertEqual(w.historical_market(api, p, NOW, Path(directory), NOW)[0]['bookmaker'], 'bet365')
            api.get.assert_called_once()

    def test_collection_fallback_reaches_archive_and_does_not_replace_existing_prices(self):
        f = dict(id='g1', league='premier-league', home='Arsenal', away='Chelsea', kickoff=NOW.isoformat(), status=-1, score=[2,1], season='2026-2027')
        p = dict(fixtureId='id1', tournamentId=17, sportId=10, participant1Name='Arsenal', participant2Name='Chelsea', startTime=NOW.isoformat(), statusId=2)
        old = dict(teams=['Arsenal','Chelsea'], leagues=list(w.TOURNAMENTS), seasons=['2026-2027'], fixtures=[])
        class API:
            calls = {}
            def quota(self): return 200
            def get(self, endpoint, **kwargs):
                if endpoint == 'fixtures': return [p] if kwargs['tournamentId'] == 17 else []
                return {'fixtureId':'id1', 'bookmakers':{'bet365':{'markets':{'101':{'outcomes':history()}}}}}
        with tempfile.TemporaryDirectory() as directory, patch.object(w.legacy, 'calendar', return_value=[f]):
            new, report = w.collect(old, {'through':'2026-09-20'}, Path(directory), NOW+timedelta(days=1), API())
            self.assertEqual(new['fixtures'][0][8:], [2.5,3.2,3.1,3])
            self.assertEqual(report['priceSources'], {'pinnacle':0, 'bet365':1})
            self.assertEqual(report['provenance'][0]['bookmaker'], 'bet365')
            again, report = w.collect(new, {'through':'2026-09-22'}, Path(directory), NOW+timedelta(days=1), API())
            self.assertEqual(again, new); self.assertEqual(report['newMatches'], 0)

    def test_csv_byte_preservation_fixes_linux_checkout_without_hiding_real_changes(self):
        def git(root, *args):
            return subprocess.check_output(['git', '-c', 'core.autocrlf=false', '-C', str(root), *args], stderr=subprocess.STDOUT)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git(root, 'init', '-q')
            git(root, 'config', 'user.email', 'test@example.invalid'); git(root, 'config', 'user.name', 'Test')
            attrs = root / '.gitattributes'; csv = root / 'archive.csv'
            attrs.write_text('*.csv -text\n'); csv.write_bytes(b'match,price\r\n1,2.50\r\n')
            git(root, 'add', '.'); git(root, 'commit', '-qm', 'Raw archive')
            attrs.write_text('*.csv text eol=lf\n')
            git(root, 'add', '.gitattributes'); git(root, 'commit', '-qm', 'Reproduce old rule')
            self.assertIn(b'archive.csv', git(root, 'status', '--porcelain'))
            attrs.write_text((w.ROOT / '.gitattributes').read_text())
            self.assertNotIn(b'archive.csv', git(root, 'status', '--porcelain'))
            csv.write_bytes(b'match,price\r\n1,3.00\r\n')
            self.assertIn(b'archive.csv', git(root, 'status', '--porcelain'))

    def test_release_stages_both_retention_deletion_types_and_rejects_unrelated_files(self):
        def run(args, root):
            return subprocess.check_output(args, cwd=root, stderr=subprocess.STDOUT).decode()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(['git','init','-q'], root)
            run(['git','config','user.email','test@example.invalid'], root)
            run(['git','config','user.name','Test'], root)
            for path in ('old-manager.json', 'old-board.json', 'manifest.json', 'unrelated.txt'):
                (root/path).write_text('old\n')
            run(['git','add','.'], root); run(['git','commit','-qm','Initial archives'], root)
            run(['git','rm','--','old-manager.json'], root)
            (root/'old-board.json').unlink()
            (root/'new-manager.json').write_text('new\n'); (root/'manifest.json').write_text('new\n')
            expected = {'old-manager.json','old-board.json','new-manager.json','manifest.json'}
            w.stage_release(run, root, expected)
            self.assertEqual(set(run(['git','diff','--cached','--name-only'], root).splitlines()), expected)
            (root/'unrelated.txt').write_text('changed\n'); run(['git','add','unrelated.txt'], root)
            with self.assertRaisesRegex(ValueError,'Unexpected staged'):
                w.stage_release(run, root, expected)


class FixtureBoardTests(unittest.TestCase):
    def row(self, **changes):
        return dict(id='h1', date='2026-09-12', league='premier-league', home='Chelsea', away='Arsenal',
                    hg=0, ag=2, odds=[3.5, 3.2, 2.1], basis='closing', homeManager='chelsea',
                    awayManager='arsenal', **changes)

    def fixture(self):
        return dict(id='f1', kickoff='2026-09-25T15:00:00+00:00', league='premier-league', round='7',
                    home={'name': 'Arsenal', 'manager': {'id': 'arsenal'}},
                    away={'name': 'Chelsea', 'manager': {'id': 'chelsea'}})

    def test_reversed_venue_follows_current_side_at_actual_prices(self):
        row = fb.orient(self.row(), False)
        self.assertEqual(row['odds'], [2.1, 3.2, 3.5])
        self.assertEqual(row['winner'], 0)
        self.assertEqual(row['profits'], [1.1, -1, -1])
        self.assertAlmostEqual(sum(row['expected']), 1)
        self.assertAlmostEqual(row['expected'][0], (1/2.1)/(1/3.5+1/3.2+1/2.1))

    def test_draw_has_its_own_price_and_profit(self):
        row = {**self.row(), 'hg': 1, 'ag': 1}
        for orientation in [True, False]:
            out = fb.orient(row, orientation)
            self.assertEqual(out['winner'], 1)
            self.assertEqual(out['profits'], [-1, 2.2, -1])

    def test_three_meeting_highlight_is_not_a_changed_roi(self):
        row = fb.orient(self.row(), False)
        two, three = fb.summarize([row]*2), fb.summarize([row]*3)
        self.assertFalse(two['outcomes'][0]['positive'])
        self.assertTrue(three['outcomes'][0]['positive'])
        self.assertEqual(two['outcomes'][0]['roi'], three['outcomes'][0]['roi'])
        self.assertEqual(three['outcomes'][0]['withoutBest'], 2.2)
        self.assertIsNone(fb.summarize([])['outcomes'][0]['roi'])

    def test_duplicates_cutoff_and_missing_odds(self):
        row = self.row()
        invalid = [{**row, 'id': 'today', 'date': NOW.date().isoformat()},
                   {**row, 'id': 'future', 'date': '2027-01-01'},
                   {**row, 'id': 'missing', 'odds': None}, {**row, 'id': 'unfinished', 'hg': None}]
        self.assertEqual(fb.valid_history([row, row, *invalid], NOW), [row, invalid[2]])
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            fb.valid_history([row, {**row, 'hg': 3}], NOW)

    def test_manager_follows_across_clubs_and_shared_match_counts_once(self):
        common = self.row()
        other = {**common, 'id': 'other', 'home': 'Brighton', 'away': 'Everton'}
        cards, evidence = fb.build([self.fixture()], [common, common], [common, other], NOW, {})
        self.assertEqual(cards[0]['clubs']['count'], 1)
        self.assertEqual(cards[0]['managers']['count'], 2)
        self.assertEqual(cards[0]['shared'], 1)
        self.assertEqual(evidence['f1']['managers'][0]['profits'][0], 1.1)

    def test_unpriced_meetings_neither_dilute_roi_nor_unlock_positive_highlights(self):
        priced=fb.orient(self.row(),False)
        missing=fb.orient({**self.row(),'id':'missing','odds':None,'basis':None,'hg':2,'ag':0},False)
        result=fb.summarize([priced,priced,missing])
        self.assertEqual(result['meetings'],3)
        self.assertEqual(result['count'],2)
        self.assertEqual(result['results'],[2,0,1])
        self.assertEqual(result['outcomes'][0]['roi'],110)
        self.assertFalse(result['outcomes'][0]['positive'])
        self.assertIsNone(missing['profits'])

    def test_inconsistent_shared_price_blocks_board(self):
        with self.assertRaisesRegex(ValueError, 'Shared match'):
            fb.build([self.fixture()], [self.row()], [{**self.row(), 'odds': [3.5, 3.2, 2.2]}], NOW, {})

    def test_unverified_manager_keeps_club_history_only(self):
        fixture = self.fixture(); fixture['home']['manager'] = None
        cards, _ = fb.build([fixture], [self.row()], [self.row()], NOW, {})
        self.assertEqual(cards[0]['managers']['count'], 0)
        self.assertEqual(cards[0]['clubs']['count'], 1)
        self.assertEqual(cards[0]['alignment'], [])

    def roster(self):
        return {'details': {'id': 1}, 'squad': {'squad': [{'title': 'coach', 'members': [
            {'id': 7, 'name': 'Full Name', 'dateOfBirth': '1970-01-02', 'role': {'key': 'coach'}}]}]}}

    def test_reviewed_id_and_dob_resolve_alternate_name(self):
        registry = {'managers': [{'id': 'm1', 'name': 'Short Name'}]}
        cross = {'7': {'managerId': 'm1', 'names': ['Full Name'], 'birthDate': '1970-01-02'}}
        out = fb.resolve_manager(self.roster(), 1, registry, cross, {}, NOW)
        self.assertEqual(out['id'], 'm1')
        cross['7']['birthDate'] = '1981-01-02'
        self.assertIsNone(fb.resolve_manager(self.roster(), 1, registry, cross, {}, NOW)['id'])
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            fb.resolve_manager(self.roster(), 2, registry, cross, {}, NOW)

    def test_ambiguous_name_never_guesses(self):
        reg = {'managers': [{'id': 'm1', 'name': 'Full Name'}, {'id': 'm2', 'name': 'Full Name'}]}
        self.assertIsNone(fb.resolve_manager(self.roster(), 1, reg, {}, {}, NOW)['id'])

    def test_calendar_excludes_started_postponed_and_out_of_window(self):
        m = {'id': 1, 'home': {'id': 1, 'name': 'Arsenal'}, 'away': {'id': 2, 'name': 'Chelsea'},
             'status': {'utcTime': (NOW+timedelta(days=1)).isoformat()}}
        excluded = [{**m, 'id': str(i+2), 'status': {**m['status'], **change}}
                    for i, change in enumerate([{'started': True}, {'finished': True}, {'cancelled': True},
                                               {'reason': {'short': 'Postponed'}}, {'utcTime': (NOW-timedelta(hours=1)).isoformat()},
                                               {'utcTime': (NOW+timedelta(days=22)).isoformat()}])]
        payload = {'details': {'id': 47}, 'fixtures': {'allMatches': [m, *excluded, *([excluded[0]]*200)]}}
        self.assertEqual(len(fb.league_fixtures(payload, 'premier-league', NOW, {}, ['Arsenal', 'Chelsea'])), 1)
        payload['fixtures']['allMatches'] = [m]
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            fb.league_fixtures(payload, 'premier-league', NOW, {}, ['Arsenal', 'Chelsea'])

    def test_provider_failure_preserves_last_good_published_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {'src/data/football-atlas-release.json': {'indexUrl': '/f.json'},
                     'src/data/manager-atlas-release.json': {'indexUrl': '/m.json'},
                     'public/f.json': {}, 'public/m.json': {},
                     'scripts/config/football-atlas-clubs.json': {},
                     'scripts/config/manager-atlas-identities.json': {},
                     'scripts/config/manager-fotmob-identities.json': {},
                     'public/manager-atlas/portraits.json': {}, 'src/data/atlas-fixtures.json': {'version': 'last-good'}}
            for name, data in files.items(): fb.atomic(root/name, data)
            with patch.object(fb, 'ROOT', root), patch.object(fb.requests, 'get', side_effect=fb.requests.RequestException('offline')):
                with self.assertRaises(fb.requests.RequestException): fb.refresh(root/'private-state', now=NOW)
            self.assertEqual(fb.read(root/'src/data/atlas-fixtures.json'), {'version': 'last-good'})
            self.assertFalse((root/'public/football-atlas/fixtures').exists())

    def test_cached_rerun_is_idempotent_and_retains_previous_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); state = root/'private-state'
            files = {'src/data/football-atlas-release.json': {'indexUrl': '/f.json', 'version': 'f', 'through': '2026-09-20'},
                     'src/data/manager-atlas-release.json': {'indexUrl': '/m.json', 'version': 'm', 'through': '2026-09-20'},
                     'public/f.json': {'teams': [], 'leagues': [], 'fixtures': [], 'crests': {}},
                     'public/m.json': {'columns': [], 'rows': []},
                     'scripts/config/football-atlas-clubs.json': {},
                     'scripts/config/manager-atlas-identities.json': {'managers': []},
                     'scripts/config/manager-fotmob-identities.json': {},
                     'public/manager-atlas/portraits.json': {}}
            for name, data in files.items(): fb.atomic(root/name, data)
            for identity in fb.LEAGUES.values():
                fb.atomic(state/f'fixture-board/provider/leagues-{identity}.json', {'checkedAt': NOW.isoformat(),
                    'payload': {'details': {'id': identity}, 'fixtures': {'allMatches': [{'status': {'finished': True}}]*200}}})
            with patch.object(fb, 'ROOT', root), patch.object(fb.requests, 'get') as request:
                first = fb.refresh(state, offline=True, now=NOW)
                prior = root/'public/football-atlas/fixtures/evidence-000000000000.json'
                fb.atomic(prior, {'version': 'previous'})
                second = fb.refresh(state, offline=True, now=NOW+timedelta(hours=1))
            self.assertEqual(first['report']['version'], second['report']['version'])
            self.assertFalse(second['changed'])
            self.assertTrue(prior.exists())
            request.assert_not_called()


if __name__ == '__main__': unittest.main()
