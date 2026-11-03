"""The read-only weekly report must work without HTML collector packages."""
from pathlib import Path
import subprocess
import sys
import unittest


class WeeklyDependencies(unittest.TestCase):
    def test_all_renderers_without_html_parser(self):
        scripts = Path(__file__).resolve().parents[1]
        program = r'''
import importlib.abc, runpy, sys
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
class NoHTMLParser(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'bs4', 'soupsieve', 'lxml'}:
            raise ModuleNotFoundError('Collector dependency used by reporting: ' + fullname)
sys.meta_path.insert(0, NoHTMLParser())
report = runpy.run_path(sys.argv[1] + '/weekly-research-report.py')
arm = dict(wins=2, losses=1, stake=3, profit=0.5, roi_pct=16.6667,
           pending_bets=1, captured_fixtures=4, pending_fixtures=1)
elo = dict(history_through='2026-11-02', cohorts={'ATP': {'baseline': arm}},
           published_source={'paired': 4, 'settled': 3})
with patch.dict(report['build_payload'].__globals__, {'load_tennis_evidence_snapshot': lambda: {}}):
    payload = report['build_payload']()
payload['tennis_elo_rebuild'] = elo
for renderer in ('render_report', 'tennis_telegram_text', 'telegram_text'):
    text = report[renderer](payload)
    assert text
    if renderer != 'telegram_text':
        assert '2W/1L' in text, renderer
        assert 'PUBLISHED ELO' in text, renderer
assert 'bs4' not in sys.modules
print('All weekly renderers passed without HTML collector dependencies')
'''
        # No env-file loader, network calls or Telegram send is invoked.
        result = subprocess.run([sys.executable, '-c', program, str(scripts)],
                                capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
