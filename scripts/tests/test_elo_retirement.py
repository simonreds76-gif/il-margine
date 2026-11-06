import json,sys,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tennis_elo_shadow as elo
import tennis_runtime_health as runtime
from tennis_step_scope import retired_research

class RetirementTests(unittest.TestCase):
    def test_capture_cannot_restart_even_via_direct_call(self):
        with patch.object(elo,'run_engine',side_effect=AssertionError('Must not price')):
            self.assertEqual(elo.capture(None,None,None),{'skipped':'retired_by_user'})

    def test_default_entry_cannot_rebuild_capture_or_settle(self):
        with tempfile.TemporaryDirectory() as d, patch.object(sys,'argv',['elo','--root',d]), \
             patch.object(elo,'rebuild',side_effect=AssertionError('Must not rebuild')), \
             patch.object(elo,'capture',side_effect=AssertionError('Must not capture')), \
             patch.object(elo,'settle',side_effect=AssertionError('Report only')), \
             patch.object(elo,'report',return_value={'status':'RETIRED','pending':8}):
            self.assertEqual(elo.main(),0)

    def test_existing_pending_settlement_still_works(self):
        with tempfile.TemporaryDirectory() as d, patch.object(sys,'argv',['elo','--root',d,'--settle-only']), \
             patch.object(elo,'rebuild',side_effect=AssertionError('Must not rebuild')), \
             patch.object(elo,'settle') as settle, \
             patch('tennis_published_elo_comparison.settle') as pub, \
             patch.object(elo,'report',return_value={'status':'RETIRED','pending':0}):
            self.assertEqual(elo.main(),0);settle.assert_called_once();pub.assert_called_once()

    def test_report_preserves_evidence_and_labels_both_arms(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d); frozen={'ledger.json':[], 'latest.json':{},'candidate.json':{},'health.json':{'status':'failed','error':'old guard'}}
            for n,v in frozen.items():(out/n).write_text(json.dumps(v))
            before={n:(out/n).read_bytes() for n in frozen}
            with patch('tennis_published_elo_comparison.report',return_value={'paired':40}), patch('tennis_published_elo_comparison.selection_rows',return_value=[]):
                r=elo.report(out)
            self.assertEqual(r['status'],'RETIRED');self.assertEqual(r['published_source']['status'],'PAUSED')
            self.assertEqual(before,{n:(out/n).read_bytes() for n in frozen})
            text=elo.weekly_text(r)
            self.assertIn('retired',text);self.assertIn('paused',text);self.assertNotIn('CAPTURE NEEDS ATTENTION',text)

    def test_failed_retired_receipt_archived_not_erased(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);now=datetime.now(timezone.utc)
            token=runtime.begin(root,'Elo Rebuild paper comparison','tennis_elo_shadow.py',600,now=now)
            runtime.finish(root,token,1,now=now)
            path=root/runtime.REL/(token['step_id']+'.json');before=path.read_bytes()
            r=runtime.summary(root,now=now)
            self.assertEqual(r['research_issues'],[]);self.assertEqual(len(r['archived_steps']),1)
            self.assertEqual(r['archived_steps'][0]['status'],'FAILED');self.assertEqual(path.read_bytes(),before)
            self.assertFalse(retired_research({'script':'tennis_elo_shadow.py','label':'settlement'}))
            self.assertFalse(retired_research({'script':'other.py','label':'Elo Rebuild paper comparison'}))

    def test_daily_capture_removed_nightly_settlement_kept(self):
        root=Path(elo.__file__).resolve().parents[1]
        daily=(root/'scripts/oncourt-daily.ps1').read_text()
        self.assertNotIn('scripts\\tennis_elo_shadow.py',daily)
        nightly=(root/'scripts/oncourt-settle-nightly.ps1').read_text()
        self.assertIn('scripts\\tennis_elo_shadow.py --settle-only',nightly)

if __name__=='__main__':unittest.main()
