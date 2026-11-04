import copy
import csv
import gzip
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from football_identity import write, read
from football_identity_research import lookup, SUPPLEMENT, REVIEWS
from keeper_feed_comparison import compare, append_record, count, digest, team_matches, apply_reviewed_counts
from keeper_feed_store import merge as merge_private, persist as persist_private, local as local_private, FIELD

spec = importlib.util.spec_from_file_location('collector', ROOT / 'scripts/compare-keeper-feeds.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class KeeperComparisonTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = {'leagues': {'47': {'goal': 'L', 'espn': 'eng.1'}}}
        self.ref = {'match_id': '1', 'league_id': '47', 'kickoff': '2026-11-01T16:00:00Z',
                    'home': {'id': 'h', 'name': 'Home'}, 'away': {'id': 'a', 'name': 'Away'},
                    'observed_at': '2026-11-02T12:00:00Z', 'source_sha256': 'ref', 'keepers': []}
        self.gf = {'id': 'G1', 'leagueId': 'L', 'matchStatus': 'FINISHED', 'kickoffUtc': self.ref['kickoff']}
        self.gs = {'data': {'hasStatistics': True, 'players': {}, 'match': {'fullTime': [{'type': 'Saves', 'home': '3', 'away': '2'}]}}}
        competition = {'date': self.ref['kickoff'], 'status': {'type': {'completed': True}}, 'competitors': []}
        self.ep = {'header': {'id': 'E1', 'competitions': [competition]}, 'rosters': []}
        for side, pid, saves in [('home', '10', 3), ('away', '20', 2)]:
            team = self.ref[side]
            self.gf.update({side+'TeamId': team['id'], side+'TeamName': team['name'], side+'TeamScore': '1'})
            competition['competitors'].append({'homeAway': side, 'team': team, 'score': '1'})
            self.ref['keepers'].append({'player_id': pid, 'player': side+' Keeper', 'team_id': team['id'], 'minutes': 90, 'saves': saves, 'target_conflict': False})
            self.gs['data']['players'][side] = [{'fixtureId': 'G1', 'playerId': 'g'+pid, 'playerName': side+' Keeper', 'playerPosition': 'Goalkeepers', 'minutesPlayed': '95', 'saves': str(saves), 'punches': '0', 'updatedAt': '2026-11-02T11:00:00Z'}]
            self.ep['rosters'].append({'homeAway': side, 'team': team, 'roster': [{'athlete': {'id': 'e'+pid, 'fullName': side+' Keeper'}, 'position': {'abbreviation': 'G'}, 'starter': True, 'stats': [{'name': 'saves', 'value': saves}, {'name': 'shotsFaced', 'value': 0}]}]})

    def result(self):
        return compare(self.root, self.ref, self.gf, self.gs, self.ep, self.config, '2026-11-03T12:00:00Z')

    def test_agreement_preserves_zero_and_ignores_bad_minutes_shots_faced(self):
        before = digest(self.ref)
        r = self.result()
        self.assertEqual(r['status'], 'agreement')
        self.assertEqual(r['keepers'][0]['goal_punches'], 0)
        self.assertEqual(r['keepers'][0]['goal_minutes_diagnostic_only'], 95)
        self.assertEqual(digest(self.ref), before)
        self.assertNotIn('shotsFaced', json.dumps(r))

    def test_missing_is_not_zero(self):
        self.gs['data']['players']['home'][0]['saves'] = None
        r = self.result()
        self.assertEqual(r['status'], 'quarantined')
        self.assertIsNone(r['keepers'][0]['saves']['goal'])
        self.assertIn('missing_saves', r['keepers'][0]['flags'])

    def test_wrong_fixture_result_league_time_or_roster_rejected(self):
        for key, value in [('homeTeamScore', '4'), ('leagueId', 'wrong'), ('kickoffUtc', '2026-11-02T16:00:00Z'), ('matchStatus', 'LIVE'), ('awayTeamName', 'Different')]:
            with self.subTest(key=key):
                old = self.gf[key]; self.gf[key] = value
                with self.assertRaises(ValueError): self.result()
                self.gf[key] = old
        self.ep['rosters'][0]['team'] = {'id': 'wrong'}
        with self.assertRaises(ValueError): self.result()

    def test_team_keeper_conflict_even_when_individuals_agree(self):
        self.gs['data']['match']['fullTime'][0]['away'] = '3'
        r = self.result()
        self.assertEqual(r['status'], 'quarantined')
        self.assertIn('away:goal_team_keeper_saves_conflict', r['flags'])

    def test_duplicate_conflicting_team_stat_and_native_event_conflict(self):
        self.gs['data']['match']['fullTime'].append({'type': 'Saves', 'home': '9', 'away': '2'})
        self.ref['keepers'][0]['target_conflict'] = True
        r = self.result()
        self.assertIn('home:goal_team_saves_missing_or_conflicting', r['flags'])
        self.assertIn('reference_event_conflict', r['keepers'][0]['flags'])

    def reviewed_conflict(self):
        p=self.ref['keepers'][0]
        p.update(target_conflict=True, event_saves=2, started=True)
        self.config['reviewed_published_counts']=[{
            'scope':'source_comparison_only','match_id':'1','player_id':'10','team_id':'h','league_id':'47',
            'kickoff':self.ref['kickoff'],'reference_sha256':'ref','goal_player_id':'g10','espn_player_id':'e10',
            'published_saves':3,'event_saves':2,'source_urls':['https://one.example','https://two.example'],
            'reviewed_at':'2026-11-03T12:00:00Z','reason':'Published totals corroborated; event discrepancy retained.'}]

    def test_exact_review_retains_event_discrepancy_without_mutating_history(self):
        self.reviewed_conflict(); before=copy.deepcopy(self.ref)
        r=self.result()
        self.assertEqual(r['status'],'reviewed_agreement')
        self.assertEqual(r['keepers'][0]['event_evidence']['event_saves'],2)
        self.assertEqual(r['keepers'][0]['event_evidence']['original_flag'],'reference_event_conflict')
        self.assertEqual(self.ref,before)
        archive={}; old=copy.deepcopy(r); old['status']='quarantined';old['keepers'][0]['flags']=['reference_event_conflict']
        append_record(archive,old);append_record(archive,r)
        self.assertEqual(len(archive['fixtures']['1']),2)

    def test_review_must_match_exact_identity_counts_scope_and_source_revision(self):
        self.reviewed_conflict(); original=copy.deepcopy(self.config['reviewed_published_counts'][0])
        for field,value in [('match_id','2'),('player_id','20'),('team_id','wrong'),('league_id','wrong'),
                            ('kickoff','2026-11-02T16:00:00Z'),('reference_sha256','changed'),
                            ('goal_player_id','wrong'),('espn_player_id','wrong'),('published_saves',4),
                            ('event_saves',1),('scope','model_training'),('source_urls',[]),
                            ('reviewed_at','2099-01-01T00:00:00Z')]:
            with self.subTest(field=field):
                self.config['reviewed_published_counts']=[{**original,field:value}]
                self.assertEqual(self.result()['status'],'quarantined')

    def test_review_does_not_release_provider_disagreement_or_team_conflict(self):
        self.reviewed_conflict();self.gs['data']['players']['home'][0]['saves']='4'
        self.assertEqual(self.result()['status'],'quarantined')
        self.gs['data']['players']['home'][0]['saves']='3'
        self.gs['data']['match']['fullTime'][0]['away']='9'
        self.assertEqual(self.result()['status'],'quarantined')
        self.gs['data']['match']['fullTime'][0]['away']='2'
        self.ref['keepers'][0]['minutes']=45
        self.assertEqual(self.result()['status'],'quarantined')

    def test_substitute_keeper_is_not_assigned_to_starter(self):
        self.gs['data']['players']['home'].append({'fixtureId': 'G1', 'playerId': 'sub', 'playerName': 'Sub Keeper', 'playerPosition': 'Goalkeepers', 'minutesPlayed': '20', 'saves': '1'})
        r = self.result()
        self.assertIn('home:keeper_appearance_coverage', r['flags'])
        self.assertEqual(r['keepers'][0]['goal_player_id'], 'g10')

    def test_duplicate_player_id_quarantined(self):
        self.gs['data']['players']['home'].append(copy.deepcopy(self.gs['data']['players']['home'][0]))
        self.assertIn('identity_unresolved', self.result()['keepers'][0]['flags'])

    def test_id_link_must_be_on_correct_team(self):
        write(self.root / REVIEWS, {'players': {'10': {'reviewed_at': '2026-11-03', 'targets': {'espn|person|': {'id': 'e20', 'evidence': ['official profile']}}}}})
        r = self.result()
        self.assertEqual(r['keepers'][0]['espn_identity'], 'mapped_id_absent_from_same_team')
        self.assertIsNone(r['keepers'][0]['espn_player_id'])

    def test_repeated_capture_idempotent_and_revisions_append_only(self):
        archive = {}; r = self.result(); r['cohort'] = 'installation_replay'
        self.assertTrue(append_record(archive, r))
        r['observed_at'] = 'later'; r['cohort'] = 'historical_backfill'
        self.assertFalse(append_record(archive, r))
        self.gs['data']['players']['home'][0]['saves'] = '4'
        revision = self.result(); revision['cohort'] = 'historical_backfill'
        self.assertTrue(append_record(archive, revision))
        self.assertEqual(len(archive['fixtures']['1']), 2)
        self.assertEqual(archive['fixtures']['1'][0]['keepers'][0]['saves']['goal'], 3)

    def test_reviewed_bridge_never_overwrites_existing_or_colliding_id(self):
        write(self.root / REVIEWS, {'players': {'10': {'reviewed_at': '2026-11-03', 'targets': {'espn|person|': {'id': 'e10', 'evidence': ['official']}}}}})
        self.assertEqual(lookup(self.root, 10, 'espn', 'person')['id'], 'e10')
        self.assertEqual(lookup(self.root, 10, 'espn', 'person', 'e11')['status'], 'reviewed_id_conflict')
        write(self.root / SUPPLEMENT, {'schema_version': 1, 'release': 'test', 'entities': {'fotmob|person|10': {'status': 'linked', 'reep_id': 'r', 'targets': {'espn|person|': {'status': 'target_collision', 'id': None}}}}})
        self.assertEqual(lookup(self.root, 10, 'espn', 'person')['status'], 'reviewed_id_conflict')

    def test_http_budget_no_redirect_or_secret_logging(self):
        client = collector.Client('secret', 1, 1)
        with patch.object(collector.requests, 'get') as get:
            get.return_value.status_code = 302
            with self.assertRaisesRegex(RuntimeError, 'goal_http_302'): client.get('goal', '/fixtures')
            self.assertFalse(get.call_args.kwargs['allow_redirects'])
            with self.assertRaises(collector.BudgetError): client.get('goal', '/other')
            self.assertEqual(get.call_count, 1)
            self.assertNotIn('secret', json.dumps(client.receipts))

    def test_missing_auth_makes_no_request(self):
        client = collector.Client('', 2, 2)
        with patch.object(collector.requests, 'get') as get:
            with self.assertRaisesRegex(RuntimeError, 'credential_missing'): client.get('goal', '/fixtures')
            get.assert_not_called()

    def test_counts_reject_invalid_values(self):
        for v in (None, '', -1, 1.5, 'nan', True): self.assertIsNone(count(v))
        self.assertEqual(count('0'), 0)

    def test_reviewed_club_bridges_match_ids_not_loose_names(self):
        config = read(ROOT / 'config/keeper-feed-comparison.json')
        # These clubs caused valid fixtures to be missed when provider names differed.
        for native_id in ('8686', '8669', '9902', '10203', '9866', '9864', '10189', '10269', '9788', '9905'):
            bridge = config['teams'][native_id]
            ref = {'id': native_id, 'name': bridge['name']}
            for provider in ('goal', 'espn'):
                with self.subTest(native_id=native_id, provider=provider):
                    self.assertTrue(team_matches(ref, provider, bridge[provider], config))
                    self.assertFalse(team_matches(ref, provider, {'id': 'wrong-club', 'name': ref['name']}, config))
        for provider in ('goal', 'espn'):
            ids = [str(row[provider]['id']) for row in config['teams'].values() if provider in row]
            self.assertEqual(len(ids), len(set(ids)), 'Provider identity belongs to multiple clubs')

    def test_reviewed_club_mapping_still_rejects_wrong_kickoff_and_duplicates(self):
        config = read(ROOT / 'config/keeper-feed-comparison.json')
        ref = dict(self.ref, home={'id': '9902', 'name': 'Ipswich Town'},
                   away={'id': '10203', 'name': 'Nottingham Forest'})
        row = {'id': 'test-calendar', 'kickoffUtc': ref['kickoff'], 'leagueId': config['leagues']['47']['goal']}
        for side in ('home', 'away'):
            bridge = config['teams'][ref[side]['id']]['goal']
            row.update({side+'TeamId': bridge['id'], side+'TeamName': bridge['name']})
        client = collector.Client('', 0, 0)
        with patch.object(client, 'get', return_value={'data': [row]}):
            self.assertEqual(collector.find_goal(client, ref, config, '2026-11-01', '2026-11-02')['id'], row['id'])
        with patch.object(client, 'get', return_value={'data': [row, copy.deepcopy(row)]}):
            with self.assertRaisesRegex(ValueError, 'identity_unresolved'):
                collector.find_goal(client, ref, config, '2026-11-01', '2026-11-02')
        row['kickoffUtc'] = '2026-11-01T17:00:00Z'
        with patch.object(client, 'get', return_value={'data': [row]}):
            with self.assertRaisesRegex(ValueError, 'identity_unresolved'):
                collector.find_goal(client, ref, config, '2026-11-01', '2026-11-02')

    def test_v4_registry_checks_global_collision_and_leaves_original_unchanged(self):
        spec = importlib.util.spec_from_file_location('reep_builder', ROOT / 'scripts/build-reep-research.py')
        builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
        write(self.root / 'data/aerial/heights.json.gz', {'10': {'id': '10', 'name': 'Keeper One'}})
        original = self.root / 'data/aerial/identity-registry.json.gz'
        original.write_bytes(b'unchanged original')
        content = {
            'bridges': 'reep_id,provider,namespace,external_id,entity_type\nr1,fotmob,person,10,player\nr1,espn,person,100,player\nr2,espn,person,100,player\n',
            'entities': 'reep_id,entity_type,canonical_name\nr1,player,Keeper One\n',
            'redirects': 'from_id,to_id\n',
        }
        hashes = {}
        for name, text in content.items():
            blob = gzip.compress(text.encode()); (self.root / (name+'.csv.gz')).write_bytes(blob)
            hashes[name] = hashlib.sha256(blob).hexdigest()
        with patch.object(builder, 'HASHES', hashes):
            builder.build(self.root, self.root, self.root / SUPPLEMENT)
            result = lookup(self.root, 10, 'espn', 'person')
            self.assertEqual(result['status'], 'target_collision')
            self.assertEqual(original.read_bytes(), b'unchanged original')
            (self.root / 'bridges.csv.gz').write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'checksum'): builder.build(self.root, self.root, self.root / SUPPLEMENT)

    def test_private_persistence_preserves_other_model_fields(self):
        record = self.result(); record['cohort'] = 'installation_replay'
        archive = {}; append_record(archive, record)
        directory = self.root / 'data/goalkeeper-saves/source-comparison'
        write(directory/'comparisons.json.gz', archive)
        write(directory/'state.json', {'1': {'checked_at': '2026-11-03', 'status': 'agreement'}})
        write(directory/'status.json', {'generated_at': '2026-11-03'})
        old = {'version': 'skyline-v1', 'forecasts': {'unchanged': 1}, 'alerts': {'sent': 123}, 'generated_at': 'earlier'}
        expected = copy.deepcopy(old)
        with patch('keeper_feed_store.update', side_effect=lambda root, change: change(old)):
            persist_private(self.root)
        self.assertEqual({k:v for k,v in old.items() if k != FIELD}, expected)
        incoming = local_private(self.root)
        self.assertEqual(merge_private(old[FIELD], incoming), old[FIELD])
        bad = copy.deepcopy(incoming); bad['archive']['fixtures']['1'][0]['keepers'][0]['saves']['goal'] = 99
        with self.assertRaisesRegex(ValueError, 'immutable'): merge_private(old[FIELD], bad)


if __name__ == '__main__':
    unittest.main()
