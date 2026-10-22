import importlib.util
from pathlib import Path
import sys,types,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
spec=importlib.util.spec_from_file_location('weekly',Path(__file__).resolve().parents[1]/'weekly-research-report.py')
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
class ReportingRegression(unittest.TestCase):
    def test_new_calibrated_version_retains_results(self):
        payload={'model_review_watchlist':{'schema_version':1,'candidates':[{'id':'shots_market_offset_v1','forward_evidence':{'version':'paired-market-offset-new-version','models':{'shots_market_offset_v1':{'hypothetical_selections':{'settled':15,'roi':.0916}}},'status':'ACTIVE','paired_fixtures':57}}]}}
        text=w.model_watchlist_text(payload)
        self.assertIn('+9.2%',text);self.assertIn('settled 15',text);self.assertNotIn('SNAPSHOT_UNAVAILABLE',text)
    def test_missing_calibrated_evidence_does_not_claim_zero_roi(self):
        text=w.model_watchlist_text({'model_review_watchlist':{'schema_version':1,'candidates':[{'id':'shots_market_offset_v1'}]}})
        self.assertIn('awaiting evidence',text)
    def test_provisional_uses_separate_lane_and_its_stake(self):
        payload={'generated_at':'test','tennis_model_evidence':{'lanes':{'provisional_hard':{'wins':17,'losses':14,'void':1,'roi_pct':28.548,'pnl_units':4.425,'staked_units':15.5}},'gap_replacements':{'strict_gap_10_20_same_side':{'performance':{'settled':53,'pnl_units':13.869,'roi_pct':27.19}}}}}
        stub=types.SimpleNamespace(weekly_text=lambda _: '')
        with patch.dict(sys.modules,{'tennis_hardcourt_scout':stub}),patch.object(w,'most_aces_suspended',return_value=True):
            text=w.tennis_telegram_text(payload)
        self.assertIn('17W/14L',text);self.assertIn('15.50u',text);self.assertNotIn('13.87u',text)
        self.assertIn('Expansion: alert-lane record unavailable',text)
if __name__=='__main__':unittest.main()
