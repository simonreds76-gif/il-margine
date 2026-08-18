from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("goalkeeper_saves_v1", SCRIPTS / "goalkeeper-saves-v1-backtest.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

from football_counts import total_probs  # noqa: E402
from model_experiment_integrity import assert_variable_columns, verify_locked_input  # noqa: E402


class GoalkeeperSavesV1Tests(unittest.TestCase):
    def test_reconstructs_and_drops_entire_anomalous_fixture(self) -> None:
        rows = [
            {
                "Date": "01/08/2025",
                "season": "2025-2026",
                "league": "epl",
                "HomeTeam": "Home",
                "AwayTeam": "Away",
                "HST": "5",
                "AST": "4",
                "FTHG": "2",
                "FTAG": "1",
            },
            {
                "Date": "02/08/2025",
                "season": "2025-2026",
                "league": "epl",
                "HomeTeam": "Bad",
                "AwayTeam": "Data",
                "HST": "1",
                "AST": "0",
                "FTHG": "0",
                "FTAG": "1",
            },
        ]
        targets, audit = module.reconstruct_targets(rows)
        self.assertEqual([row.saves for row in targets], [3, 3])
        self.assertEqual(audit["anomalous_fixtures"], 1)
        self.assertEqual(audit["valid_team_observations"], 2)

    def test_integer_line_has_explicit_push_mass(self) -> None:
        over, under, push = total_probs(3.0, 3.1, distribution="negative_binomial", alpha=0.08)
        self.assertGreater(push, 0.0)
        self.assertAlmostEqual(over + under + push, 1.0, places=9)

    def test_registered_historical_target_is_stable(self) -> None:
        historical = ROOT / "data" / "corners-ou" / "historical" / "all-historical-matches.csv"
        targets, audit = module.reconstruct_targets(module.load_csv(historical))
        self.assertEqual(len(targets), 42_958)
        self.assertAlmostEqual(audit["mean"], 3.0242, places=4)
        self.assertAlmostEqual(audit["variance_to_mean"], 1.3569, places=4)
        self.assertAlmostEqual(audit["zero_rate"], 0.0741, places=4)

    def test_constant_features_fail_closed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "constant"):
            assert_variable_columns([(1.0, 2.0), (1.0, 3.0)], ("constant", "variable"))

    def test_input_hash_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data = root / "input.csv"
            data.write_text("value\n1\n", encoding="utf-8")
            lock = root / "lock.json"
            lock.write_text(
                '{"input_files":{"registered":{"sha256":"deadbeef"}}}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "mismatch"):
                verify_locked_input(lock, "registered", data)


if __name__ == "__main__":
    unittest.main()
