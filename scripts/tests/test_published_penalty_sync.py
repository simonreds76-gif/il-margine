import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('sync', Path(__file__).resolve().parents[1] / 'sync-published-penalty-hierarchies.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)

def entry(player, date):
    return {'primary': player, 'secondary': 'B', 'tertiary': 'C', 'last_updated': date}

class PublishedPenaltySyncTests(unittest.TestCase):
    def test_published_promotion_replaces_stale_local_hierarchy(self):
        local = {'_meta': {}, 'Toulouse': entry('Donnum', '2026-07-01')}
        updated, changes = sync.reconcile(local, {'_meta': {}, 'Toulouse': entry('Tengstedt', '2026-09-21')})
        self.assertEqual(updated['Toulouse']['primary'], 'Tengstedt')
        self.assertEqual(changes, ['Toulouse'])
        self.assertEqual(local['Toulouse']['primary'], 'Donnum')

    def test_newer_local_editorial_decision_is_preserved(self):
        local = {'_meta': {}, 'Brest': entry('Lala', '2026-10-11'), 'PSG': entry('Dembele', '2026-09-01')}
        updated, changes = sync.reconcile(local, {'_meta': {}, 'Brest': entry('Doumbia', '2026-07-01')})
        self.assertEqual(updated, local)
        self.assertEqual(changes, [])

    def test_missing_or_malformed_publication_fails_without_mutation(self):
        local = {'_meta': {}, 'Brest': entry('Lala', '2026-10-11')}
        for publication in ({}, {'_meta': {}, 'Brest': {'primary': 'Wrong'}}):
            with self.assertRaises(ValueError):
                sync.reconcile(local, publication)
        self.assertEqual(local['Brest']['primary'], 'Lala')

if __name__ == '__main__': unittest.main()
