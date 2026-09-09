import json,runpy,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
M=runpy.run_path(str(ROOT/'scripts/weekly-research-report.py'),run_name='watchlist_test')

class ModelReviewWatchlistTests(unittest.TestCase):
 def payload(self):
  p=json.loads((ROOT/'data/football-form/weekly-research-report.json').read_text(encoding='utf8'))
  p['model_review_watchlist']=M['model_watchlist_summary']()
  return p

 def test_frozen_volume_is_separate_from_strict_and_forward_evidence(self):
  registry=M['model_watchlist_summary']();c=registry['candidates'][0];h=c['historical_replay']
  self.assertFalse(registry['automatic_promotion']);self.assertFalse(c['live_routing']);self.assertEqual(c['actual_stake'],0)
  self.assertEqual(c['profile'],'volume_200_hard');self.assertEqual(h['bets'],h['wins']+h['losses'])
  self.assertAlmostEqual(h['roi_pct'],100*h['profit_units']/h['stake_units'])
  self.assertEqual(c['model_sha256'],'d2fa88cb767faa7a4a2659e9d415eac239801c246703c2836308c1904af66c9a')

 def test_every_report_format_keeps_capture_gap_visible(self):
  p=self.payload()
  for fn in ['render_report','telegram_text','tennis_telegram_text']:
   text=M[fn](p)
   self.assertIn('Astra Volume [RESEARCH]',text);self.assertIn('historical replay ROI +7.25%, n=69',text)
   self.assertIn('prospective capture NOT_CONNECTED',text)
   self.assertIn('historical bets are not forward evidence',text)

 def test_missing_register_is_not_reported_as_healthy(self):
  self.assertIn('UNAVAILABLE',M['model_watchlist_text']({}))

 def test_register_includes_both_football_and_tennis_families(self):
  ids={r['id'] for r in M['model_watchlist_summary']()['families']}
  self.assertTrue({'tennis_ml','astra_aces_df','tennis_breaks','football_counts','gk_saves','goalscorers','assists'}.issubset(ids))

if __name__=='__main__':unittest.main()
