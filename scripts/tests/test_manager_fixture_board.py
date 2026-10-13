import copy
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))
import atlas_fixture_board as board


class SharedFixtureTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 13, tzinfo=timezone.utc)
        self.club = {'id':'history', 'date':'2021-09-11', 'league':'serie-a',
                     'home':'Napoli', 'away':'Juventus', 'hg':2, 'ag':1,
                     'odds':[2.16,3.59,3.55], 'basis':'closing'}
        self.manager = {**self.club, 'homeManager':'spalletti', 'awayManager':'allegri'}
        self.fixture = {'id':'next', 'kickoff':'2026-10-20T18:00:00Z',
                        'home':{'name':'Juventus', 'manager':{'id':'spalletti'}},
                        'away':{'name':'Napoli', 'manager':{'id':'allegri'}}}

    def build(self, manager=None):
        return board.build([self.fixture], [self.club], [manager or self.manager], self.now, {})

    def test_swapped_manager_clubs_keep_distinct_correct_returns(self):
        cards, evidence = self.build()
        self.assertEqual(cards[0]['shared'], 1)
        self.assertEqual(cards[0]['clubs']['outcomes'][0]['profit'], -1)
        self.assertEqual(cards[0]['managers']['outcomes'][0]['profit'], 1.16)
        self.assertEqual(evidence['next']['clubs'][0]['odds'], [3.55,3.59,2.16])
        self.assertEqual(evidence['next']['managers'][0]['odds'], [2.16,3.59,3.55])

    def test_same_orientation_still_passes(self):
        self.fixture['home']['manager']['id'] = 'allegri'
        self.fixture['away']['manager']['id'] = 'spalletti'
        cards, _ = self.build()
        self.assertEqual(cards[0]['clubs']['outcomes'], cards[0]['managers']['outcomes'])

    def test_draw_remains_draw_when_orientation_reverses(self):
        self.club['ag'] = self.manager['ag'] = 2
        cards, _ = self.build()
        self.assertEqual(cards[0]['clubs']['outcomes'][1]['profit'], 2.59)
        self.assertEqual(cards[0]['managers']['outcomes'][1]['profit'], 2.59)

    def test_genuine_conflicts_are_still_rejected(self):
        for key, value in [('odds',[2.2,3.59,3.55]), ('hg',3), ('date','2021-09-12')]:
            with self.subTest(key=key):
                row=copy.deepcopy(self.manager)
                row[key]=value
                with self.assertRaisesRegex(ValueError,'Shared match'):
                    self.build(row)


if __name__ == '__main__':
    unittest.main()
