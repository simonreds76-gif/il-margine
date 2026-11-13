import unittest,sys,json,tempfile,shutil,hashlib
from pathlib import Path
from unittest.mock import patch
W=Path(__file__).resolve().parents[2]
sys.dont_write_bytecode=True;sys.path.insert(0,str(W/'scripts'))
import admin_active_models as a

class ActiveDisplayTests(unittest.TestCase):
 def test_reconcile(self):
  h=a.history([('a','2026-11-01',-1),('b','2026-11-02',2)],{'settled':2,'profit':1})
  self.assertEqual(h['profit'],1);self.assertEqual(h['settled'],2)
 def test_duplicate(self):
  self.assertIn('message',a.history([('a','2026-11-01',1),('a','2026-11-02',1)],{'settled':2,'profit':2}))
 def test_mismatch(self):
  self.assertIn('message',a.history([('a','2026-11-01',1)],{'settled':5,'profit':1}))
 def test_missing_date(self):
  self.assertIn('message',a.history([('a',None,1)],{'settled':1,'profit':1}))
 def test_missing_profit(self):
  self.assertIn('message',a.history([('a','2026-11-01',None)],{'settled':1,'profit':1}))
 def test_pending_excluded(self):
  self.assertEqual(a.selection_entries([{'status':'pending','pnl_units':2}]),[])

if __name__=='__main__':unittest.main()
