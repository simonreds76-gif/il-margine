from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "strict-policy-report.py"
SCRIPTS_DIR = ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def load_module():
    spec = importlib.util.spec_from_file_location("strict_policy_report_phase0", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Phase0LaneDispatchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_hard_bo3_aliases_to_strict_without_exit(self):
        profile, exit_code, message, stderr = self.module.phase0_signal_profile_dispatch("hard_bo3", False)
        self.assertEqual(profile, "strict")
        self.assertIsNone(exit_code)
        self.assertEqual(message, "")
        self.assertFalse(stderr)

    def test_clay_lane_rejects_without_internal_flag(self):
        profile, exit_code, message, stderr = self.module.phase0_signal_profile_dispatch("clay_bo3", False)
        self.assertEqual(profile, "clay_bo3")
        self.assertEqual(exit_code, 2)
        self.assertIn("requires INTERNAL_RESEARCH_LANES=1", message)
        self.assertTrue(stderr)

    def test_clay_lane_continues_with_internal_flag(self):
        profile, exit_code, message, stderr = self.module.phase0_signal_profile_dispatch("clay_bo3", True)
        self.assertEqual(profile, "clay_bo3")
        self.assertIsNone(exit_code)
        self.assertEqual(message, "")
        self.assertFalse(stderr)

    def test_grass_lane_rejects_without_internal_flag(self):
        profile, exit_code, message, stderr = self.module.phase0_signal_profile_dispatch("grass_bo3", False)
        self.assertEqual(profile, "grass_bo3")
        self.assertEqual(exit_code, 2)
        self.assertIn("requires INTERNAL_RESEARCH_LANES=1", message)
        self.assertTrue(stderr)

    def test_grass_lane_continues_with_internal_flag(self):
        profile, exit_code, message, stderr = self.module.phase0_signal_profile_dispatch("grass_bo3", True)
        self.assertEqual(profile, "grass_bo3")
        self.assertIsNone(exit_code)
        self.assertEqual(message, "")
        self.assertFalse(stderr)

    def test_phase0_stub_lane_noops_with_internal_flag(self):
        profile, exit_code, message, stderr = self.module.phase0_signal_profile_dispatch("slam_bo5", True)
        self.assertEqual(profile, "slam_bo5")
        self.assertEqual(exit_code, 0)
        self.assertIn("Phase 0 scaffold", message)
        self.assertFalse(stderr)

    def test_challenger_hc_always_disabled(self):
        profile, exit_code, message, stderr = self.module.phase0_signal_profile_dispatch("challenger_hc", True)
        self.assertEqual(profile, "challenger_hc")
        self.assertEqual(exit_code, 2)
        self.assertIn("lane disabled", message)
        self.assertTrue(stderr)


if __name__ == "__main__":
    unittest.main()
