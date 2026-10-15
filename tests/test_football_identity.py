import sys
import csv
import gzip
import hashlib
import importlib.util
import io
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from football_identity import audit, canonical, compatible_label, inventory, key, resolve, write


class IdentityTests(unittest.TestCase):
    def test_existing_refresh_survives_identity_failure_and_keeps_payload(self):
        spec = importlib.util.spec_from_file_location('refresh_identity_test', Path(__file__).resolve().parents[1] / 'scripts/refresh-aerial.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / 'data/aerial/calendar.json.gz', {'observed_at': '2026-10-15T00:00:00Z'})
            payload = {'fixtures': [], 'exclusions': {}, 'history_through': '2026-10-14'}
            with patch.object(module, 'build', return_value=payload), patch.object(module, 'page') as network:
                with patch('football_identity.refresh_health', side_effect=ValueError('broken registry')):
                    result = module.refresh(root, datetime(2026, 10, 15, tzinfo=timezone.utc), online=False)
                self.assertEqual(result, payload)
                network.assert_not_called()

    def test_full_names_are_not_false_identity_conflicts(self):
        self.assertTrue(compatible_label(['Nico Schlotterbeck'], 'Nico Cedric Schlotterbeck'))
        self.assertTrue(compatible_label(['Martin Odegaard'], 'Martin Ødegaard'))
        self.assertFalse(compatible_label(['Manu Koné'], 'Kouadio Emmanuel Boris Koné'))
        self.assertFalse(compatible_label(['Alex Silva'], 'Alex Smith'))
        self.assertFalse(compatible_label(['J. Silva'], 'João Silva'))

    def test_builder_rejects_global_collision_withdrawal_and_wrong_identity(self):
        spec = importlib.util.spec_from_file_location('identity_builder', Path(__file__).resolve().parents[1] / 'scripts/build-football-identity.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heights = {str(i): {'id': str(i), 'name': 'Player ' + str(i), 'team_id': '10'} for i in range(1, 5)}
            write(root / 'data/aerial/heights.json.gz', heights)
            tables = {
                'bridges': [['provider', 'namespace', 'external_id', 'reep_id', 'upstream_status'],
                            ['fotmob', 'person', '1', 'rp1', ''], ['sofascore', 'player', '77', 'rp1', ''],
                            ['sofascore', 'player', '77', 'rpOutside', ''],
                            ['fotmob', 'person', '2', 'rp2', ''], ['sofascore', 'player', '88', 'rp2', ''],
                            ['sofascore', 'player', '89', 'rp2', ''],
                            ['fotmob', 'person', '3', 'withdrawn', ''],
                            ['fotmob', 'person', '4', 'rp4', '']],
                'players': [['reep_id', 'label', 'status'], ['rp1', 'Player 1', 'active'],
                            ['rp2', 'Player 2', 'active'], ['rp4', 'Someone Else', 'active']],
                'redirects': [['from_id', 'to_id'], ['withdrawn', '']],
            }
            for name, rows in tables.items():
                stream = io.StringIO(newline='')
                csv.writer(stream).writerows(rows)
                body = gzip.compress(stream.getvalue().encode())
                (root / (name + '.csv.gz')).write_bytes(body)
                builder.CHECKSUMS[name] = hashlib.sha256(body).hexdigest()
            result = builder.build(root, root, root / 'output/registry.json.gz')
            self.assertEqual(resolve(result, 'fotmob', 'person', 1, 'sofascore', 'player')['status'], 'target_collision')
            self.assertEqual(resolve(result, 'fotmob', 'person', 2, 'sofascore', 'player')['status'], 'ambiguous_target')
            self.assertEqual(result['entities']['fotmob|person|3']['status'], 'withdrawn_or_inactive_source')
            self.assertEqual(result['entities']['fotmob|person|4']['status'], 'name_review_required')
            (root / 'players.csv.gz').write_bytes(b'corrupted')
            with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
                builder.build(root, root, root / 'output/registry.json.gz')

    def registry(self):
        return {'schema_version': 1, 'release': 'test', 'entities': {
            'fotmob|person|12': {'status': 'linked', 'reep_id': 'rp1', 'targets': {
                'sofascore|player|': {'status': 'linked', 'id': '34'}}}}}

    def test_namespace_and_provider_are_required(self):
        r = self.registry()
        self.assertEqual(resolve(r, 'fotmob', 'player', 12, 'sofascore', 'player')['status'], 'not_in_registry')
        self.assertEqual(resolve(r, 'opta', 'person', 12, 'sofascore', 'player')['status'], 'not_in_registry')
        self.assertEqual(resolve(r, 'fotmob', 'person', 12, 'sofascore', 'person')['status'], 'provider_not_mapped')
        self.assertEqual(resolve(r, 'fotmob', 'person', 12, 'sofascore', 'player')['id'], '34')

    def test_cannot_replace_existing_id(self):
        r = self.registry()
        self.assertEqual(resolve(r, 'fotmob', 'person', 12, 'sofascore', 'player', 35)['status'], 'existing_id_conflict')
        self.assertEqual(resolve(r, 'fotmob', 'person', 12, 'sofascore', 'player', 34)['status'], 'registry_linked')

    def test_source_and_target_quarantines(self):
        r = self.registry()
        for status in ('ambiguous_source', 'withdrawn_or_inactive_source', 'name_review_required'):
            r['entities']['fotmob|person|12']['status'] = status
            self.assertEqual(resolve(r, 'fotmob', 'person', 12, 'sofascore', 'player'), {'status': status})
        r = self.registry()
        for status in ('ambiguous_target', 'target_collision', 'inactive_target'):
            r['entities']['fotmob|person|12']['targets']['sofascore|player|']['status'] = status
            self.assertEqual(resolve(r, 'fotmob', 'person', 12, 'sofascore', 'player'), {'status': status})

    def test_redirects_withdrawals_cycles(self):
        self.assertEqual(canonical('a', {'a': 'b', 'b': 'c'}), 'c')
        self.assertIsNone(canonical('a', {'a': ''}))
        self.assertIsNone(canonical('a', {'a': 'b', 'b': 'a'}))

    def test_penalty_names_require_unique_same_club_roster(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / 'data/aerial/heights.json.gz', {
                '1': {'id': '1', 'name': 'Alex Silva', 'team_id': '10', 'source_kind': 'current_squad'},
                '2': {'id': '2', 'name': 'Alex Silva', 'team_id': '20', 'source_kind': 'current_squad'},
                '3': {'id': '3', 'name': 'Other Man', 'team_id': '20', 'source_kind': 'current_squad'}})
            write(root / 'data/goalscorer/team-logo-map.json', {'leagues': {'epl': {'teams': {
                'Club One': {'fotmob_team_id': 10}}}}})
            write(root / 'data/goalscorer/epl-penalty-takers.json', {
                'Club One': {'primary': 'Alex Silva', 'secondary': 'Other Man'}})
            result = inventory(root)
            self.assertEqual(result['scopes']['penalty_takers'], ['fotmob|person|1'])
            self.assertEqual(result['unresolved'][0]['name'], 'Other Man')
            heights = {'1': {'id': '1', 'name': 'Alex Silva', 'team_id': '10', 'source_kind': 'current_squad'},
                       '4': {'id': '4', 'name': 'Alex Silva', 'team_id': '10', 'source_kind': 'current_squad'}}
            write(root / 'data/aerial/heights.json.gz', heights)
            self.assertNotIn('penalty_takers', inventory(root)['scopes'])

    def test_missing_registry_and_name_only_ledger_do_not_resolve(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'data/goalkeeper-saves/gk-saves-v1-shadow-signals.csv'
            path.parent.mkdir(parents=True)
            path.write_text('goalkeeper,team\nAlex Keeper,Club One\n', encoding='utf-8')
            result = audit(root)
            self.assertEqual(result['gk_ledger_rows_without_player_id'], 1)
            self.assertEqual(result['scopes'], {})
            self.assertEqual(resolve({}, 'fotmob', 'person', 1, 'sofascore', 'player')['status'], 'registry_unavailable')


if __name__ == '__main__':
    unittest.main()
