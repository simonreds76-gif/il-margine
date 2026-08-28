from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


policy = load_script("strict_policy_report_bo5_test", "strict-policy-report.py")


class SlamBo5EvidenceLaneTests(unittest.TestCase):
    def test_lane_requires_internal_research_switch(self) -> None:
        self.assertEqual(
            policy.phase0_signal_profile_dispatch("slam_bo5", False)[1],
            2,
        )
        profile, exit_code, _, _ = policy.phase0_signal_profile_dispatch("slam_bo5", True)
        self.assertEqual(profile, "slam_bo5")
        self.assertIsNone(exit_code)

    def test_lane_is_grand_slam_atp_only(self) -> None:
        self.assertIsNone(policy.spread_bo5_scope_reason("Hard", "Grand Slam", "ATP", "high", 4))
        self.assertEqual(
            policy.spread_bo5_scope_reason("Hard", "Grand Slam", "ATP", "high", 3),
            "qualifying_bo3",
        )
        self.assertEqual(
            policy.spread_bo5_scope_reason("Hard", "Grand Slam", "ATP", "high", None),
            "round_unknown",
        )
        self.assertEqual(
            policy.spread_bo5_scope_reason("Hard", "Masters 1000", "ATP", "high", 4),
            "not_grand_slam",
        )
        self.assertEqual(policy.spread_bo5_scope_reason("Hard", "Grand Slam", "WTA", "high", 4), "league")

    def test_lane_is_always_zero_stake(self) -> None:
        self.assertEqual(
            policy.apply_profile_stake_policy("slam_bo5", 2.0, 200.0, "flat_spread"),
            (0.0, 0.0, "prospective_evidence_no_stake"),
        )

    def test_generation_settlement_and_reporting_are_wired(self) -> None:
        root = SCRIPTS.parent
        expected = {
            "oncourt-am-refresh.ps1": "--signal-profile slam_bo5",
            "oncourt-daily.ps1": "--signal-profile slam_bo5",
            "oncourt-settle-nightly.ps1": "strict-signals-slam-bo5-archive.csv",
        }
        for filename, fragment in expected.items():
            self.assertIn(fragment, (root / "scripts" / filename).read_text(encoding="utf-8"), filename)

        weekly = (root / "scripts" / "oncourt-weekly.ps1").read_text(encoding="utf-8")
        self.assertIn("strict-clv-audit-slam-bo5-2026.csv", weekly)
        report = (root / "scripts" / "weekly-research-report.py").read_text(encoding="utf-8")
        self.assertIn('"slam_bo5"', report)
        monitor = (root / "src" / "lib" / "tennis-monitor-files.ts").read_text(encoding="utf-8")
        self.assertIn("strict-signals-slam-bo5-live.csv", monitor)
        self.assertNotIn("strict-signals-slam_bo5-live.csv", monitor)


if __name__ == "__main__":
    unittest.main()
