from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tennis_runtime_health as runtime
import tennis_pairing_consistency as pairing


class RecoveredHealthTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.label='Recover projections from current native pairings'
        self.script='build-tennis-props-board.py'
        self.token=runtime.begin(self.root,self.label,self.script,600)
        runtime.finish(self.root,self.token,1)
        self.path=self.root/runtime.REL/(self.token['step_id']+'.json')
        self.original=runtime.read(self.path)
        self.proof=dict(state='CURRENT',board_sha256='b'*64,board_after_exports=True,
            generation_date_current=True,player_history_current=True,native_epoch={'games':{'sha256':'a'*64}},
            missing_sides=[],unexpected_sides=[],as_of='2026-11-06',checked_at=datetime.now(timezone.utc).isoformat())

    def test_existing_fresh_board_resolves_only_its_failed_repair(self):
        other=runtime.begin(self.root,'Current odds','odds.py',60);runtime.finish(self.root,other,1)
        with patch.object(pairing,'board_state',return_value=self.proof):
            runner=lambda *a,**kw:self.fail('Verified board must not be rebuilt')
            pairing.ensure_props_board(self.root,'2026-11-06',runner=runner)
        receipt=runtime.read(self.path)
        self.assertEqual(receipt['status'],'OK')
        self.assertEqual(receipt['recovered_failure'],self.original)
        self.assertFalse(receipt['recovery_verification']['rebuild_executed'])
        self.assertEqual([x['label'] for x in runtime.summary(self.root)['issues']],['Current odds'])

    def test_incomplete_or_stale_proof_never_clears_failure(self):
        for key,bad in [('state','REBUILD_REQUIRED'),('board_sha256',None),('board_after_exports',False),
                        ('generation_date_current',False),('player_history_current',False),
                        ('native_epoch',{}),('missing_sides',['one']),('unexpected_sides',['one'])]:
            pairing._resolve_verified_board_recovery(self.root,{**self.proof,key:bad})
            self.assertEqual(runtime.read(self.path),self.original,key)

    def test_in_progress_attempt_is_not_resolved_by_old_output(self):
        runtime.begin(self.root,self.label,self.script,600)
        before=runtime.read(self.path)
        pairing._resolve_verified_board_recovery(self.root,self.proof)
        self.assertEqual(runtime.read(self.path),before)

    def test_retired_elo_remains_archived_without_hiding_active_failure(self):
        token=runtime.begin(self.root,'Elo Rebuild paper comparison','tennis_elo_shadow.py',600)
        runtime.finish(self.root,token,1)
        health=runtime.summary(self.root)
        self.assertEqual([x['label'] for x in health['archived_steps']],['Elo Rebuild paper comparison'])
        self.assertEqual([x['label'] for x in health['issues']],[self.label])


if __name__=='__main__': unittest.main()
