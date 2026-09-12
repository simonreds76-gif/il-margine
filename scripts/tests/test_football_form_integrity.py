import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from football_form_integrity import unique_team_results
SPEC = importlib.util.spec_from_file_location('integrity_pub', SCRIPTS / 'publish-football-research-picks.py')
PUB = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PUB
SPEC.loader.exec_module(PUB)


class FormIntegrityTests(unittest.TestCase):
    def row(self):
        return dict(date='2026-08-19',league='la-liga',team='Malaga',team_key='malaga',
                    opponent='Ath Madrid',opponent_key='ath madrid',venue='away',
                    shots_for='5',shots_against='15',corners_for='1',corners_against='6',xg_for='')

    def test_alias_duplicates_count_once_in_live_indexes_and_keep_enrichment(self):
        a = self.row()
        b = dict(a,opponent='Atl. Madrid',opponent_key='atl madrid',xg_for='0.23')
        teams, leagues = PUB.build_base_indexes([a,b])
        self.assertEqual(len(teams[('la-liga','malaga')]),1)
        self.assertEqual(len(leagues['la-liga']),1)
        self.assertEqual(teams[('la-liga','malaga')][0]['xg_for'],'0.23')
        self.assertEqual(a['xg_for'],'')  # Caller input is not mutated.

    def test_duplicate_disagreement_is_rejected(self):
        a = self.row()
        with self.assertRaisesRegex(ValueError,'Conflicting shots_for'):
            unique_team_results([a,dict(a,shots_for='6')],PUB.team_key)
        with self.assertRaisesRegex(ValueError,'Conflicting fixtures'):
            unique_team_results([a,dict(a,opponent='Barcelona')],PUB.team_key)

    def test_form_builder_and_live_publisher_agree_on_verified_aliases(self):
        for a,b in [('Dep. A Coruna','La Coruna'),('Atl. Madrid','Ath Madrid')]:
            self.assertEqual(PUB.team_key(a),PUB.team_key(b))
            self.assertEqual(PUB.FORM_BUILD.team_key(a),PUB.FORM_BUILD.team_key(b))

    def test_rolling_form_cannot_count_aliased_match_twice(self):
        base = {field: None for field in PUB.FORM_BUILD.TEAM_MATCH_FIELDS}
        base.update(self.row(), season='2026-2027',home_team='Ath Madrid',away_team='Malaga')
        for field in ('shots_for','shots_against','corners_for','corners_against'):
            base[field] = float(base[field])
        base['xg_for'] = None
        duplicate = dict(base, opponent='Atl. Madrid',home_team='Atl. Madrid')
        later = dict(base,date='2026-08-26')
        expected = PUB.FORM_BUILD.build_rolling_rows([base,later])
        actual = PUB.FORM_BUILD.build_rolling_rows([base,duplicate,later])
        self.assertEqual(actual,expected)


if __name__ == '__main__':
    unittest.main()
