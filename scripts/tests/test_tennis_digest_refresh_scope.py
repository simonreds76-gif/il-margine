import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'tennis-daily-signal-digest.py'
spec = importlib.util.spec_from_file_location('digest_refresh_scope', SCRIPT)
M = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = M
spec.loader.exec_module(M)

class RefreshScopeTests(unittest.TestCase):
    def signal(self, priority):
        return M.Signal(section='TEST', priority=priority, labels=['TEST'],
                        match='Player A vs Player B', selection='Example', edge_pct=10,
                        key=('2026-10-20', 'a', 'b', str(priority)))

    def test_pending_refresh_does_not_claim_props_have_no_signals(self):
        text = '\n'.join(M.render_messages('2026-10-19', [], ['STRICT', 'ACES/DF'], props_pending=True))
        self.assertIn('still refreshing', text)
        self.assertIn('No qualifying match winner or handicap', text)
        self.assertNotIn('No signals: STRICT, ACES/DF', text)
        self.assertNotIn('No qualifying signals today', text)

    def test_early_scope_excludes_old_props_before_saving_dispatch_ids(self):
        core, prop = self.signal(0), self.signal(45)
        signals, empty = M.scope_digest([core, prop], ['ACES/DF'], True)
        self.assertEqual(signals, [core])
        self.assertEqual(empty, [])

    def test_partial_pass_preserves_sent_props_across_midnight(self):
        prop, core = self.signal(45), self.signal(0)
        state = {"date": "2026-10-19", "signal_ids": [M.signal_id(prop)]}
        self.assertEqual(set(M.retained_signal_ids(state, "2026-10-19", [core])),
                         {M.signal_id(prop), M.signal_id(core)})
        self.assertEqual(M.retained_signal_ids(state, "2026-10-20", []), [M.signal_id(prop)])

    def test_completed_pass_keeps_props_and_normal_rendering(self):
        prop = self.signal(45)
        signals, _ = M.scope_digest([prop], [], False)
        self.assertEqual(signals, [prop])
        text = '\n'.join(M.render_messages('2026-10-19', signals, []))
        self.assertIn('Example', text)
        self.assertNotIn('still refreshing', text)

if __name__ == '__main__':
    unittest.main()
