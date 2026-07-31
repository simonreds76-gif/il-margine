from __future__ import annotations

import runpy
import csv
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
MODULE = runpy.run_path(
    str(ROOT / "scripts" / "tennis-venue-ace-factor-v1-observations.py"),
    run_name="venue_ace_factor_v1_observations_test",
)


class VenueAceFactorV1ObservationTests(unittest.TestCase):
    def test_choose_rows_prefers_one_main_line_per_player(self) -> None:
        base = {
            "date": "2026-07-31",
            "tour": "ATP",
            "player": "Player A",
            "opponent": "Player B",
            "market": "aces",
            "event_id": "event-1",
            "matched_board": "yes",
        }
        rows = [
            {**base, "line": "7.5", "main_line": "false", "best_available_line": "false"},
            {**base, "line": "8.5", "main_line": "true", "best_available_line": "true"},
            {**base, "line": "9.5", "main_line": "false", "best_available_line": "false"},
            {**base, "market": "double_faults", "line": "2.5", "main_line": "true"},
        ]
        selected = MODULE["choose_rows"](rows)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["line"], "8.5")

    def test_no_push_probability_renormalizes_integer_line(self) -> None:
        self.assertAlmostEqual(MODULE["no_push_probability"](0.40, 0.50), 4 / 9)

    def test_main_registers_paired_control_and_candidate_probabilities(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def write(path: Path, rows: list[dict[str, str]]) -> None:
                with path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)

            base = {
                "date": "2026-07-31",
                "tour": "ATP",
                "surface": "Hard",
                "player": "Player A",
                "opponent": "Player B",
            }
            control = root / "control.csv"
            candidate = root / "candidate.csv"
            comparison = root / "comparison.csv"
            gate = root / "gate.json"
            observations = root / "observations.csv"
            write(control, [{**base, "projected_aces": "7.0"}])
            write(
                candidate,
                [
                    {
                        **base,
                        "projected_aces": "8.0",
                        "venue_v1_factor": "1.10",
                        "venue_v1_control_factor": "1.00",
                        "venue_v1_prior_svpt": "10000",
                        "venue_v1_source_seasons": "2023-2025",
                    }
                ],
            )
            write(
                comparison,
                [
                    {
                        **base,
                        "market": "aces",
                        "line": "7.5",
                        "over_odds": "1.90",
                        "event_id": "event-1",
                        "matched_board": "yes",
                        "main_line": "true",
                        "best_available_line": "true",
                        "fair_p_over": "0.55",
                        "fair_p_under": "0.45",
                        "fair_over_odds": "1.82",
                    }
                ],
            )
            gate.write_text(
                '{"deployment_safe_aces":{"ATP":{"candidate_alpha":0.18}}}',
                encoding="utf-8",
            )
            argv = [
                "script",
                "--date", "2026-07-31",
                "--comparison", str(comparison),
                "--control-board", str(control),
                "--candidate-board", str(candidate),
                "--gate", str(gate),
                "--observations", str(observations),
            ]
            with patch.object(sys, "argv", argv):
                self.assertEqual(MODULE["main"](), 0)
            rows = MODULE["read_csv"](observations)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["control_projection_mean"], "7.000")
            self.assertEqual(rows[0]["candidate_projection_mean"], "8.000")
            self.assertTrue(rows[0]["control_p_over_no_push"])
            self.assertEqual(rows[0]["candidate_p_over_no_push"], "0.550000")


if __name__ == "__main__":
    unittest.main()
