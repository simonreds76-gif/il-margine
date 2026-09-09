import csv
import runpy
import tempfile
import unittest
from pathlib import Path

REPORT = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'weekly-research-report.py'))


class WeeklyPropsMarketScopeTests(unittest.TestCase):
    def test_breaks_cannot_inflate_aces_df_returns_or_promotion_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = [
                ('aces', 'two_way_player_shadow', '1'),
                ('double_faults', 'two_way_player_shadow', '-1'),
                ('match_breaks', 'breaks_calibration_unfiltered', '500'),
                ('player_breaks', 'breaks_single_source_shadow', '20'),
            ]
            with (root / 'signals.csv').open('w', newline='') as handle:
                writer = csv.writer(handle)
                writer.writerow(['market', 'decision_mode', 'pnl', 'settlement_status'])
                for market, mode, pnl in rows:
                    writer.writerow([market, mode, pnl, 'settled'])
            (root / 'health.json').write_text('{}')
            result = REPORT['tennis_props_shadow_decision'](root / 'signals.csv', root / 'health.json')
            self.assertEqual(result['registered'], 2)
            self.assertEqual(result['settled'], 2)
            self.assertEqual(result['pnl_units'], 0)
            self.assertEqual(result['roi_pct'], 0)
            self.assertFalse(result['gates']['settled_sample']['pass'])


if __name__ == '__main__':
    unittest.main()
