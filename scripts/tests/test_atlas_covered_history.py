import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import unittest
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import atlas_covered_history as extension
from atlas_fixture_board import build, orient, summarize


class CoveredHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]
        cls.seed = extension.read(cls.root / 'data/football-atlas/championship-seed.json')
        cls.rows = [dict(zip(extension.COLUMNS, r)) for r in cls.seed['rows']]

    def test_complete_unique_seed(self):
        extension.validate(self.rows)
        self.assertEqual(len(self.rows), 7860)
        for year in range(2012, 2026):
            season = [r for r in self.rows if r['season'] == f'{year}-{year+1}']
            self.assertEqual(len(season), 552)
            self.assertEqual(len({(r['home'], r['away']) for r in season}), 552)
        self.assertTrue(all(r['odds'] for r in self.rows))

    def test_no_stale_provider_pinnacle_after_warning(self):
        self.assertTrue(all(r['basis'].startswith('bet365') for r in self.rows if r['date'] >= '2025-07-23'))

    def test_price_contract_and_missing_price(self):
        header = 'Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,PSCH,PSCD,PSCA,B365CH,B365CD,B365CA\n'
        raw = (header + 'E1,01/09/2025,A,B,1,0,H,2,3,4,2.1,3.4,3.6\n').encode()
        row = extension.parse_season(raw, 2025, '2026-01-01', {'A':'A', 'B':'B'})[0]
        self.assertEqual(row['odds'], [2.1,3.4,3.6])
        self.assertEqual(row['basis'], 'bet365-closing')
        row['odds'] = None
        record = summarize([orient(row, True)])
        self.assertEqual((record['meetings'], record['count'], record['results']), (1,0,[1,0,0]))
        self.assertIsNone(record['outcomes'][0]['roi'])

    def test_conflicting_results_and_unknown_clubs_fail(self):
        raw = b'Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\nE1,01/09/2025,A,B,1,0,A\n'
        with self.assertRaises(ValueError):
            extension.parse_season(raw, 2025, '2026-01-01', {'A':'A', 'B':'B'})
        with self.assertRaises(KeyError):
            extension.parse_season(raw.replace(b',0,A', b',0,H'), 2025, '2026-01-01', {'A':'A'})

    def test_duplicate_fails(self):
        with self.assertRaises(ValueError):
            extension.validate([self.rows[0], self.rows[0]])

    def test_sunderland_golden_and_manager_parity(self):
        board = extension.read(self.root / 'src/data/atlas-fixtures.json')
        release = extension.read(self.root / 'src/data/covered-leagues-release.json')
        expanded = extension.read(self.root / 'public' / release['boardUrl'].lstrip('/'))
        original = {f['id']: f for f in board['fixtures']}
        self.assertEqual({f['id'] for f in expanded['fixtures']}, set(original))
        for f in expanded['fixtures']:
            self.assertNotEqual(f['league'], 'championship')
            self.assertEqual(f['managers'], original[f['id']]['managers'])
        match = next(f for f in expanded['fixtures'] if f['id']=='fm-5795494')
        self.assertEqual(match['clubs']['results'], [2,4,2])
        self.assertEqual(match['clubs']['count'], 8)
        self.assertEqual([o['profit'] for o in match['clubs']['outcomes']], [.31,7.73,-2.81])
        self.assertEqual(match['managers']['count'], 2)
        self.assertEqual(original[match['id']]['clubs']['results'], [1,1,0])

    def test_future_excluded_and_orientation(self):
        row = copy.deepcopy(self.rows[0])
        normal, reverse = orient(row, True), orient(row, False)
        self.assertEqual(normal['odds'], reverse['odds'][::-1])
        self.assertEqual(normal['profits'], reverse['profits'][::-1])
        fixture = {'id':'test','kickoff':'2026-10-26T15:00:00Z','home':{'name':row['home']},'away':{'name':row['away']}}
        cutoff = datetime.fromisoformat(row['date']).replace(tzinfo=timezone.utc)
        cards, _ = build([fixture], [row], [], cutoff, {})
        self.assertEqual(cards[0]['clubs']['meetings'], 0)

    def test_extension_preserves_every_original_meeting_and_fixture(self):
        board = extension.read(self.root / 'src/data/atlas-fixtures.json')
        release = extension.read(self.root / 'src/data/covered-leagues-release.json')
        expanded = extension.read(self.root / 'public' / release['boardUrl'].lstrip('/'))
        old_evidence = extension.read(self.root / 'public' / board['evidenceUrl'].lstrip('/'))['fixtures']
        new_evidence = extension.read(self.root / 'public' / expanded['evidenceUrl'].lstrip('/'))['fixtures']
        originals = {f['id']: f for f in board['fixtures']}
        for fixture in expanded['fixtures']:
            mid = fixture['id']
            for key in ('league', 'round', 'kickoff', 'home', 'away', 'managers'):
                self.assertEqual(fixture[key], originals[mid][key], (mid, key))
            self.assertEqual(new_evidence[mid]['managers'], old_evidence[mid]['managers'])
            old_clubs = {r['id']: r for r in old_evidence[mid]['clubs']}
            new_clubs = {r['id']: r for r in new_evidence[mid]['clubs']}
            self.assertEqual({key: new_clubs[key] for key in old_clubs}, old_clubs)
            self.assertTrue(all(r['league'] == 'championship' for key, r in new_clubs.items() if key not in old_clubs))

    def test_frozen_seed_download_disabled(self):
        with self.assertRaisesRegex(ValueError, 'Frozen seed'):
            extension.refresh(self.root / 'unused-test-state', offline=False)

    def test_forward_checkpoint_rejects_missing_matches_and_price_rewrites(self):
        original = extension.read(self.root / 'data/football-atlas/championship-forward.json')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / 'data/football-atlas/championship-forward.json'
            incoming = root / 'incoming.json'
            extension.atomic(target, original)
            with patch.object(extension, 'ROOT', root), patch.dict('os.environ', {'CHAMPIONSHIP_CHECKPOINT':str(incoming)}):
                for mutation in ('remove', 'price', 'result', 'provenance', 'scope', 'conflict'):
                    candidate = copy.deepcopy(original)
                    if mutation == 'remove': candidate['rows'].pop()
                    if mutation == 'price': candidate['rows'][0]['odds'][0] += .1
                    if mutation == 'result': candidate['rows'][0]['hg'] += 1
                    if mutation == 'provenance': candidate['rows'][0]['provenance'] = 'unknown'
                    if mutation == 'scope': candidate['scope'] = 'playoffs'
                    if mutation == 'conflict': candidate['conflicts'] = ['unresolved']
                    extension.atomic(incoming, candidate)
                    with self.assertRaises(ValueError, msg=mutation): extension.sync_forward_checkpoint()
                    self.assertEqual(extension.read(target), original)
                extension.atomic(incoming, original)
                self.assertEqual(extension.sync_forward_checkpoint(), [])

    def test_forward_checkpoint_accepts_append_only_update(self):
        original = extension.read(self.root / 'data/football-atlas/championship-forward.json')
        candidate = copy.deepcopy(original)
        new = copy.deepcopy(original['rows'][0])
        new.update(id='test-new', date='2026-10-26', kickoff='2026-10-26T19:00:00+00:00')
        candidate['rows'].append(new)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / 'data/football-atlas/championship-forward.json'
            incoming = root / 'incoming.json'
            extension.atomic(target, original)
            extension.atomic(incoming, candidate)
            with patch.object(extension, 'ROOT', root), patch.dict('os.environ', {'CHAMPIONSHIP_CHECKPOINT':str(incoming)}):
                self.assertEqual(extension.sync_forward_checkpoint(), ['data/football-atlas/championship-forward.json'])
                self.assertEqual(extension.read(target), candidate)


if __name__ == '__main__':
    unittest.main()
