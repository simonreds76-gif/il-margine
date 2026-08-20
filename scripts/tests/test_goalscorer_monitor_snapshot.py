from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_snapshot_module():
    spec = importlib.util.spec_from_file_location(
        "build_goalscorer_monitor_snapshot_test",
        SCRIPTS / "build-goalscorer-monitor-snapshot.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


snapshot = load_snapshot_module()


class GoalscorerMonitorSnapshotTests(unittest.TestCase):
    def test_extreme_gap_summary_uses_evaluation_stakes_only(self) -> None:
        rows = [
            {
                "settled": "1",
                "bet_outcome": "won",
                "evaluation_stake_units": "1.00",
                "recommended_stake_units": "0.00",
                "pnl_units": "1.40",
            },
            {
                "settled": "1",
                "bet_outcome": "lost",
                "evaluation_stake_units": "1.00",
                "recommended_stake_units": "0.00",
                "pnl_units": "-1.00",
            },
            {
                "settled": "",
                "bet_outcome": "",
                "evaluation_stake_units": "1.00",
                "recommended_stake_units": "0.00",
                "pnl_units": "",
            },
        ]
        summary = snapshot.compute_evidence_summary(rows, "evaluation_stake_units")
        self.assertEqual(summary["registered"], 3)
        self.assertEqual(summary["settled"], 2)
        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary["wins"], 1)
        self.assertEqual(summary["losses"], 1)
        self.assertAlmostEqual(summary["staked_units"], 2.0)
        self.assertAlmostEqual(summary["pnl_units"], 0.4)
        self.assertAlmostEqual(summary["roi"], 20.0)

    def test_unsettled_cohort_has_no_fake_zero_roi(self) -> None:
        summary = snapshot.compute_evidence_summary(
            [{"settled": "", "evaluation_stake_units": "1.00"}],
            "evaluation_stake_units",
        )
        self.assertIsNone(summary["roi"])

    def test_snapshot_configs_include_every_quarantine_ledger(self) -> None:
        paths = {config["quarantine_signals_csv"] for config in snapshot.LEAGUE_CONFIGS}
        self.assertEqual(
            paths,
            {
                "data/goalscorer/fair-odds-lab-serie-a-quarantine.csv",
                "data/goalscorer/fair-odds-lab-epl-quarantine.csv",
                "data/goalscorer/fair-odds-lab-la-liga-quarantine.csv",
                "data/goalscorer/fair-odds-lab-bundesliga-quarantine.csv",
                "data/goalscorer/fair-odds-lab-ligue-1-quarantine.csv",
            },
        )

    def test_research_status_compares_beta_with_raw_holdout_metrics(self) -> None:
        research = snapshot.build_research_status()
        calibration = research["calibration"]
        self.assertEqual(calibration["candidate"], "beta")
        self.assertGreater(calibration["n"], 0)
        self.assertIsNotNone(calibration["raw_brier"])
        self.assertIsNotNone(calibration["brier"])
        self.assertLess(calibration["brier"], calibration["raw_brier"])
        self.assertLess(calibration["ece"], calibration["raw_ece"])
        self.assertEqual(calibration["decision"], "KEEP_RESEARCH")


if __name__ == "__main__":
    unittest.main()
