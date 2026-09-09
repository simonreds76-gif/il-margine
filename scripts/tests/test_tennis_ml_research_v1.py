import unittest, tempfile,json,importlib.util
from pathlib import Path
from datetime import datetime,timezone
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import tennis_ml_research_v1 as research
import tennis_ml_evidence as evidence

class EvidenceTests(unittest.TestCase):
 def test_archive_is_immutable_deduplicated_and_bounded(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t); (r/'scripts').mkdir(); (r/'scripts/oncourt-compute-fair-odds.py').write_text('# model')
   at=datetime(2026,9,9,10,tzinfo=timezone.utc)
   self.assertEqual(evidence.capture_components(r,[{'p_rank':.6}],at),'saved:1')
   self.assertEqual(evidence.capture_components(r,[{'p_rank':.6}],at),'unchanged')
   first=list(r.rglob('*.json'))[0]; content=first.read_bytes()
   for i in range(1,8): self.assertEqual(evidence.capture_components(r,[{'p_rank':i/10}],at),'saved:1' if i!=6 else 'unchanged')
   evidence.capture_components(r,[{'p_rank':.85}],at)
   self.assertEqual(evidence.capture_components(r,[{'p_rank':.91}],at),'daily_limit')
   self.assertEqual(first.read_bytes(),content)
   self.assertEqual(len(list(r.rglob('*.json'))),8)
   self.assertIn('requires_verified_pre_match',json.loads(content)['timing_status'])
 def test_no_fake_forecast_or_naive_timestamp(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t)
   self.assertEqual(evidence.capture_components(r,[]),'empty')
   with self.assertRaises(ValueError):evidence.capture_components(r,[{'p':float('nan')}])
   with self.assertRaises(ValueError):evidence.capture_components(r,[{}],datetime(2026,1,1))

class ResearchTests(unittest.TestCase):
 def test_model_fit_is_symmetric_and_constrained(self):
  rng=np.random.default_rng(7);p=rng.uniform(.1,.9,(100,4));m=rng.uniform(.2,.8,100);y=rng.binomial(1,m)
  w=research.fit_stack(p,m,y); reverse=research.fit_stack(1-p,1-m,1-y)
  np.testing.assert_allclose(w,reverse,atol=1e-6)
  self.assertTrue(np.all(w>=-1e-8));self.assertLessEqual(w.sum(),1.000001)
  np.testing.assert_allclose(research.stack_predict(1-p,1-m,w),1-research.stack_predict(p,m,w),atol=1e-12)
 def test_no_bet_is_not_a_zero_roi_and_settlement_orientation(self):
  rows=[{'date':'2025-01-01','probs':[.65], 'market':.6,'y':1,'odds':[2,2]}]
  score=research.metrics(rows,np.array([.65]));self.assertEqual(score['wins'],1);self.assertEqual(score['roi_pct'],100)
  rows[0]['y']=0;score=research.metrics(rows,np.array([.65]));self.assertEqual(score['losses'],1)
  self.assertIsNone(score['roi_without_best_win_pct'])
  rows[0]['odds']=[1.5,2.5];score=research.metrics(rows,np.array([.6]));self.assertIsNone(score['roi_pct'])
 def test_actual_folds_have_no_future_training_dates(self):
  report=json.loads(Path(__file__).resolve().parents[2].joinpath('docs/audits/tennis-ml-20260909.json').read_text())
  for fold in report['folds']:self.assertLess(fold['train_end'],fold['test_start'])

if __name__=='__main__':unittest.main()
