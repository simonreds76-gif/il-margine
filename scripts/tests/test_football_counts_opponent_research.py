import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location('count_opponent_research', SCRIPTS / 'football-counts-opponent-research.py')
MODEL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODEL)


def pair(day, shots=10):
    common = dict(date=day, league='epl', home_team='Arsenal', away_team='Chelsea')
    return [dict(common, team=team, opponent=opponent, venue=venue,
                 shots_for=shots, shots_against=shots, corners_for=5, corners_against=5)
            for team, opponent, venue in [('Arsenal','Chelsea','home'), ('Chelsea','Arsenal','away')]]


class CausalResearchTests(unittest.TestCase):
    def history(self):
        return [r for day in range(1, 8) for r in pair(f'2026-03-{day:02}')]

    def test_current_and_future_outcomes_do_not_change_features(self):
        base = self.history() + pair('2026-04-02', 8) + pair('2026-04-03', 9)
        changed = self.history() + pair('2026-04-02', 80) + pair('2026-04-03', 90)
        first, _ = MODEL.build_samples(base, {})
        second, _ = MODEL.build_samples(changed, {})
        for market in ('shots', 'corners'):
            a = [s for s in first[market] if s['date']=='2026-04-02']
            b = [s for s in second[market] if s['date']=='2026-04-02']
            self.assertTrue(a)
            self.assertEqual([s['x'] for s in a], [s['x'] for s in b])

    def test_price_capture_freezes_history_before_capture_day(self):
        fixture = '2026-04-03|epl|arsenal|chelsea'
        market = dict(fixture=fixture, date='2026-04-03', captured='2026-04-01T10:00:00Z', league='epl',home='Arsenal',away='Chelsea')
        base = self.history() + pair('2026-04-01', 80) + pair('2026-04-02', 90) + pair('2026-04-03')
        changed = self.history() + pair('2026-04-01', 2) + pair('2026-04-02', 1) + pair('2026-04-03')
        _, a = MODEL.build_samples(base, {'shots':[market]})
        _, b = MODEL.build_samples(changed, {'shots':[market]})
        lookup = (fixture, 'arsenal', '2026-04-01')
        self.assertEqual(a['shots'][lookup]['x'], b['shots'][lookup]['x'])

    def test_same_day_processing_order_does_not_change_features(self):
        a, _ = MODEL.build_samples(self.history(), {})
        b, _ = MODEL.build_samples(list(reversed(self.history())), {})
        for metric in a:
            index = lambda rows: {(r['fixture'],r['team']):r['x'] for r in rows}
            self.assertEqual(index(a[metric]), index(b[metric]))

    def test_missing_counts_are_not_zero(self):
        self.assertIsNone(MODEL.number(''))
        self.assertIsNone(MODEL.number('nan'))
        self.assertEqual(MODEL.number('0'), 0)
        history = MODEL.History()
        rows = self.history()
        for r in rows:
            r['corners_for'] = r['corners_against'] = None
        for day in sorted({r['date'] for r in rows}):
            history.update_day([r for r in rows if r['date']==day])
        f = dict(league='epl',home='arsenal',away='chelsea',date='2026-04-01')
        self.assertIsNone(history.features(f, 'corners','home','2026-04-01'))

    def test_historical_bookmaker_aliases_join_both_fixture_and_team(self):
        for a,b in [('TSG Hoffenheim','Hoffenheim'),('Nottingham Forest',"Nott'm Forest"),
                    ('Bayer Leverkusen','Leverkusen'),('Tottenham Hotspur','Tottenham'),('Cologne','FC Koln')]:
            self.assertEqual(MODEL.key(a),MODEL.key(b))


if __name__ == '__main__':
    unittest.main()
