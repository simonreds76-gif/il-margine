from __future__ import annotations

import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "strict-policy-report.py"
if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))


def load_script():
    spec = importlib.util.spec_from_file_location("strict_hard_side_flip_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class HardMastersSideFlipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_script()

    def allowed(self, **overrides) -> bool:
        values = {
            "detected": True,
            "league": "ATP",
            "surface": "Hard",
            "series_bucket": "Masters 1000",
            "confidence": "high",
            "model_market_fav_gap": 0.08,
        }
        values.update(overrides)
        return self.module.allow_hard_masters_side_flip(**values)

    def test_registered_cohort_is_allowed(self) -> None:
        self.assertTrue(self.allowed())

    def test_safety_boundaries_remain_blocked(self) -> None:
        self.assertFalse(self.allowed(confidence="medium"))
        self.assertFalse(self.allowed(surface="Clay"))
        self.assertFalse(self.allowed(series_bucket="ATP500"))
        self.assertFalse(self.allowed(league="Challenger"))
        self.assertFalse(self.allowed(model_market_fav_gap=0.1001))

    def test_local_snapshot_keeps_latest_same_day_pair(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            old_root = self.module.ROOT
            self.module.ROOT = Path(folder)
            history = self.module.ROOT / "data" / "pinnacle-history"
            history.mkdir(parents=True)
            fields = ["captured_at", "bookmaker", "league", "player1_name", "player2_name", "odds1", "odds2"]
            for stamp, odds in [("090000", "2.40"), ("100000", "2.63")]:
                path = history / f"pinnacle-history-20260801-{stamp}.csv"
                with path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields)
                    writer.writeheader()
                    writer.writerow({
                        "captured_at": f"2026-08-01T{stamp[:2]}:{stamp[2:4]}:00Z",
                        "bookmaker": "Pinnacle",
                        "league": "ATP",
                        "player1_name": "Jaime Faria",
                        "player2_name": "Christopher O'Connell",
                        "odds1": odds,
                        "odds2": "1.60",
                    })
            try:
                rows = self.module.load_local_pinnacle_snapshot("2026-08-01")
            finally:
                self.module.ROOT = old_root
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["odds1"], 2.63)


if __name__ == "__main__":
    unittest.main()
