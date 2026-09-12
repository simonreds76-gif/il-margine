import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('counts_calibration_audit', SCRIPTS/'football-counts-calibration-audit.py')
AUDIT = importlib.util.module_from_spec(spec)
spec.loader.exec_module(AUDIT)
PUB = AUDIT.module('audit_test_pub','publish-football-research-picks.py')

class CalibrationArchiveTests(unittest.TestCase):
    def test_never_construct_pair_across_books_or_use_later_better_price(self):
        base = dict(captured_at='2026-09-01T12:00:00Z',kickoff_at='2026-09-01T15:00:00Z',
                    competition='Premier League',home_team='Arsenal',away_team='Chelsea',
                    team='Arsenal',market='TEAM_SHOTS',line='10.5',odds_decimal='2',bookmaker='A')
        over = {**base,'side':'over'}
        under = {**base,'side':'under','bookmaker':'B'}
        self.assertEqual(AUDIT.earliest_markets([over,under],PUB,'shots'),[])
        first = [over,{**under,'bookmaker':'A'}]
        later = [{**r,'captured_at':'2026-09-01T14:00:00Z','odds_decimal':'3'} for r in first]
        selected = AUDIT.earliest_markets(later+first,PUB,'shots')
        self.assertEqual(len(selected),1)
        self.assertEqual(selected[0]['over'],2)
        self.assertEqual(AUDIT.earliest_markets([{**r,'captured_at':base['kickoff_at']} for r in first],PUB,'shots'),[])

if __name__ == '__main__':
    unittest.main()
