import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from datetime import datetime,timezone

spec=importlib.util.spec_from_file_location('v4_current',Path(__file__).resolve().parents[1]/'tennis_v4_current_capture.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)

class CurrentV4Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  gate=self.root/'gate.json';gate.write_text('{}');self.ledger=self.root/'ledger.csv';self.ledger.write_text('old evidence')
  self.old={'observation_id':'old','p_model':'0.57','selected_odds':'2.2','registered_at_utc':'2026-10-01'}
  self.mod=SimpleNamespace(DEFAULT_LEDGER=self.ledger,DEFAULT_GATE=gate,DEFAULT_REPORT=self.root/'report.txt',DEFAULT_JSON=self.root/'report.json',read_csv=lambda p:[dict(self.old)],assert_integrity=Mock(),model_hash=lambda g:'frozen',ladder_candidates=Mock(return_value=([],{})),observation_id=lambda r:r['id'],registration_problem=Mock(return_value=None),build_registration=Mock(return_value={'observation_id':'new','p_model':'0.6'}),report_payload=Mock(return_value={}),write_report=Mock(),write_csv=Mock(side_effect=lambda p,rows:p.write_text(str(rows))))
 def test_existing_observations_are_not_recomputed_or_rewritten(self):
  self.mod.ladder_candidates.return_value=([{'row':{'id':'old'}}],{})
  self.assertEqual(M.capture(self.mod,self.root/'quotes.csv',datetime.now(timezone.utc)),0)
  self.mod.build_registration.assert_not_called();self.mod.write_csv.assert_not_called()
  self.assertEqual(self.ledger.read_text(),'old evidence')
  payload=self.mod.write_report.call_args.args[2]
  self.assertFalse(payload['historical_settlement_refreshed'])
 def test_new_capture_uses_frozen_registration_preserves_prior_fields(self):
  self.mod.ladder_candidates.return_value=([{'row':{'id':'new'}},{'row':{'id':'new'}}],{})
  self.assertEqual(M.capture(self.mod,self.root/'quotes.csv',datetime.now(timezone.utc)),1)
  self.mod.build_registration.assert_called_once()
  written=self.mod.write_csv.call_args.args[1]
  self.assertEqual(written[0],self.old);self.assertEqual(written[1]['p_model'],'0.6')
  self.assertEqual(self.mod.build_registration.call_args.kwargs['sha256'],'frozen')
 def test_rejected_quote_does_not_create_or_rewrite_forecast(self):
  self.mod.ladder_candidates.return_value=([{'row':{'id':'new'}}],{});self.mod.registration_problem.return_value='price_is_stale'
  self.assertEqual(M.capture(self.mod,self.root/'quotes.csv',datetime.now(timezone.utc)),0)
  self.mod.write_csv.assert_not_called();self.mod.build_registration.assert_not_called()

if __name__=='__main__':unittest.main()
