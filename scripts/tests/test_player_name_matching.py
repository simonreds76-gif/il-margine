from __future__ import annotations

import ast
import json
import runpy
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from player_name_matching import fold_name_text
from goalscorer_penalty_utils import player_match_score
from goalkeeper_saves_live import person_match_score
from tennis_props_names import resolve_baseline_name


class PlayerNameMatchingTests(unittest.TestCase):
    def test_shared_unicode_cases_and_idempotence(self):
        for raw, ascii_name in json.loads((SCRIPTS / 'tests/name-folding-cases.json').read_text(encoding='utf-8')):
            with self.subTest(raw=raw):
                self.assertEqual(fold_name_text(raw), ascii_name)
                self.assertEqual(fold_name_text(fold_name_text(raw)), ascii_name)
        self.assertEqual(fold_name_text(None), '')
        self.assertEqual(fold_name_text('Martin &Oslash;degaard'), 'Martin Odegaard')
        self.assertEqual(fold_name_text('张帅'), '张帅')

    def test_matching_keeps_different_players_separate(self):
        for matcher in (player_match_score, person_match_score):
            self.assertEqual(matcher('Martin Ødegaard', 'Martin Odegaard'), 100)
            self.assertEqual(matcher('Martin Ødegaard', 'Markus Odegaard'), 0)
            self.assertEqual(matcher('', ''), 0)

    def test_tennis_keeps_canonical_key_and_tour_scope(self):
        result = resolve_baseline_name(tour='ATP', value='Lukasz Kubot', available_names={'ATP': {'Łukasz Kubot'}})
        self.assertTrue(result.resolved)
        self.assertEqual(result.name, 'Łukasz Kubot')
        self.assertFalse(resolve_baseline_name(tour='WTA', value='Lukasz Kubot', available_names={'ATP': {'Łukasz Kubot'}}).resolved)
        self.assertFalse(resolve_baseline_name(tour='ATP', value='LUKASZ KUBOT', available_names={'ATP': {'Łukasz Kubot', 'Lukasz Kubot'}}).resolved)

    def test_settlement_handles_feed_order_and_special_letters(self):
        settle = runpy.run_path(str(SCRIPTS / 'tennis-props-settle-shadow.py'))
        self.assertEqual(settle['pair_key']('Kubot, Łukasz', 'Tomáš Macháč'), settle['pair_key']('Lukasz Kubot', 'Tomas Machac'))

    def test_tracker_recognizes_recapture_without_rewriting_old_id(self):
        tracker = runpy.run_path(str(SCRIPTS / 'tennis-props-shadow-tracker.py'))
        row = dict(date='2026-09-13', tour='ATP', tournament='Example', player='Łukasz Kubot', opponent='Tomas Machac', market='aces', line='4.5', side='OVER')
        old_id = tracker['signal_id'](row, 'OVER')
        row['signal_id'] = old_id
        plain = dict(row, player='Lukasz Kubot')
        self.assertEqual(tracker['matching_signal_key'](row), tracker['matching_signal_key'](plain))
        self.assertEqual(row['signal_id'], old_id)
        self.assertNotEqual(tracker['matching_signal_key'](row), tracker['matching_signal_key'](dict(plain, line='5.5')))

    def test_reviewed_adapters_compile_and_use_shared_fold(self):
        coverage = json.loads((SCRIPTS / 'tests/name-folding-coverage.json').read_text())
        for file, names in coverage.items():
            source = (SCRIPTS / file).read_text(encoding='utf-8-sig')
            compile(source, file, 'exec')
            tree = ast.parse(source)
            for name in names:
                with self.subTest(file=file, function=name):
                    function = next(f for f in tree.body if isinstance(f, ast.FunctionDef) and f.name == name)
                    self.assertTrue(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'fold_name_text' for n in ast.walk(function)))


if __name__ == '__main__':
    unittest.main()
