import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('backfill', ROOT / 'scripts/backfill-football-atlas-prices.py')
backfill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backfill)


class PriceBackfillTests(unittest.TestCase):
    def example(self):
        index = {'teams': ['A', 'B'], 'leagues': ['serie-a'], 'seasons': ['2025-2026'],
                 'fixtures': [['m', '2025-12-15', 0, 0, 0, 1, 1, 0, None, None, None, 0]]}
        review = {'m': {'date': '2025-12-15', 'league': 'serie-a', 'season': '2025-2026',
                         'home': 'A', 'away': 'B', 'score': [1, 0], 'odds': [2.2, 3, 3.7],
                         'basis': 'bet365-closing'}}
        return index, review

    def test_prefers_complete_closing_market_without_mixing_snapshots(self):
        row = dict(B365CH='2.2', B365CD='3', B365CA='3.7', B365H='2.1', B365D='3.3', B365A='3.6')
        self.assertEqual(backfill.source_prices(row)[:2], ([2.2, 3, 3.7], 'bet365-closing'))
        row['B365CD'] = ''
        self.assertEqual(backfill.source_prices(row)[:2], ([2.1, 3.3, 3.6], 'bet365-pre-match'))
        row['B365A'] = ''
        with self.assertRaisesRegex(ValueError, 'No complete'):
            backfill.source_prices(row)

    def test_bad_prices_cannot_enter_an_roi(self):
        for values in [('nan', '3', '4'), ('0', '3', '4'), ('2', 'inf', '4'), ('20', '20', '20')]:
            with self.assertRaises(ValueError):
                backfill.source_prices(dict(zip(('B365CH', 'B365CD', 'B365CA'), values)))

    def test_backfill_is_idempotent_and_does_not_mutate_original(self):
        index, reviews = self.example()
        original = copy.deepcopy(index)
        new = backfill.apply(index, reviews)
        self.assertEqual(index, original)
        self.assertEqual(new['fixtures'][0][8:], [2.2, 3, 3.7, 4])
        self.assertEqual(backfill.apply(new, reviews), new)
        reviews['m']['odds'][0] = 2.3
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            backfill.apply(new, reviews)

    def test_identity_and_score_must_match_exactly(self):
        for key, value in [('home', 'B'), ('date', '2025-12-14'), ('score', [0, 1]), ('league', 'la-liga'), ('season', '2024-2025')]:
            index, reviews = self.example()
            reviews['m'][key] = value
            with self.assertRaisesRegex(ValueError, 'identity'):
                backfill.apply(index, reviews)

    def test_review_cannot_insert_an_unknown_fixture(self):
        index, reviews = self.example()
        reviews['unknown'] = reviews.pop('m')
        with self.assertRaisesRegex(ValueError, 'not in archive'):
            backfill.apply(index, reviews)

    def test_published_repair_has_no_price_gaps_and_keeps_reviewed_markets(self):
        read = lambda path: json.loads(path.read_text(encoding='utf-8'))
        reviews = read(ROOT / 'scripts/config/football-atlas-reviewed-prices.json')['fixtures']
        repaired = {fid: item for fid, item in reviews.items() if item.get('sourceFile')}
        meta = read(ROOT / 'src/data/football-atlas-release.json')
        new = read(ROOT / 'public' / meta['indexUrl'].lstrip('/'))
        changed = []
        for row in new['fixtures']:
            self.assertTrue(backfill.valid(row[8:11]))
            if row[0] in repaired:
                review = repaired[row[0]]
                self.assertEqual(row[8:11], review['odds'])
                self.assertEqual(row[11], backfill.CODES[review['basis']])
                self.assertIn(row[11], (4, 5))
                changed.append(row)
        self.assertEqual(len(changed), 253)
        self.assertEqual(sum(r[11] == 4 for r in changed), 249)
        self.assertEqual(sum(r[11] == 5 for r in changed), 4)
        manager_meta = read(ROOT / 'src/data/manager-atlas-release.json')
        managers = read(ROOT / 'public' / manager_meta['indexUrl'].lstrip('/'))
        clubs = {r[0]: r for r in new['fixtures']}
        for packed in managers['rows']:
            row = dict(zip(managers['columns'], packed))
            self.assertTrue(backfill.valid(row['odds']))
            self.assertEqual(row['odds'], clubs[row['id']][8:11])
            self.assertEqual(backfill.CODES[row['basis']], clubs[row['id']][11])


if __name__ == '__main__':
    unittest.main()
