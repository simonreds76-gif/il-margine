from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
VNEXT = ROOT / "scripts" / "vnext"
SCRIPTS = ROOT / "scripts"
if str(VNEXT) not in sys.path:
    sys.path.insert(0, str(VNEXT))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from fit_residual_v02 import score
from model_spec import DynamicResiduals, ProcessModel, sigmoid


def _load_backtest_module():
    import importlib.util

    path = ROOT / "scripts" / "backtest-fair-odds.py"
    spec = importlib.util.spec_from_file_location("backtest_fair_odds_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_strict_policy_module():
    import importlib.util

    path = ROOT / "scripts" / "strict-policy-report.py"
    spec = importlib.util.spec_from_file_location("strict_policy_report_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class VNextModelSpecTests(unittest.TestCase):
    def test_sigmoid_is_monotone(self) -> None:
        values = np.asarray(sigmoid(np.asarray([-2.0, 0.0, 2.0])))
        self.assertTrue(np.all(np.diff(values) > 0))

    def test_server_and_return_effect_orientation(self) -> None:
        model = ProcessModel(
            name="first_win",
            intercept=0.5,
            player_ids=np.asarray([1, 2]),
            server_effects=np.asarray([0.3, -0.3]),
            return_effects=np.asarray([0.2, -0.2]),
            pooling_strength=75.0,
            iterations=1,
            max_delta=0.0,
        )
        self.assertGreater(model.probability(1, 2), model.probability(2, 1))

    def test_dynamic_state_decays(self) -> None:
        state = DynamicResiduals(half_life_days=100.0, prior_precision=100.0)
        state.update("first_in", "server", 1, 1000, gradient=10.0, information=10.0)
        initial = state.value("first_in", "server", 1, 1000)
        later = state.value("first_in", "server", 1, 1100)
        self.assertGreater(initial, later)
        self.assertGreater(later, 0.0)

    def test_process_precision_defaults_to_pooling(self) -> None:
        model = ProcessModel(
            name="first_in",
            intercept=0.0,
            player_ids=np.asarray([1]),
            server_effects=np.asarray([0.0]),
            return_effects=None,
            pooling_strength=25.0,
            iterations=1,
            max_delta=0.0,
        )
        self.assertEqual(model.precision(999, "server"), 25.0)

    def test_residual_zero_recovers_incumbent(self) -> None:
        row = {
            "match_key": "2024-01-01:1:2",
            "date": "2024-01-01",
            "tournament": "Test",
            "winner_id": "1",
            "loser_id": "2",
            "incumbent_prob_winner": "0.63",
            "uncertainty_weighted_serve_logit_differential": "0.2",
        }
        scored = score([row], theta=0.0, cap=0.35)[0]
        self.assertAlmostEqual(float(scored["incumbent_prob_winner_scored"]), float(scored["residual_prob_winner_scored"]))

    def test_cpi_gate_requires_identity_clean_provenance(self) -> None:
        module = _load_strict_policy_module()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "gates.csv"
            path.write_text(
                "status,segment,value,identity_basis\n"
                "PASS_SHADOW,model_surface,SpeedFast,legacy\n",
                encoding="utf-8",
            )
            self.assertEqual(module.load_cpi_speed_pass_gates(path), set())
            path.write_text(
                "status,segment,value,identity_basis\n"
                "PASS_SHADOW,model_surface,SpeedFast,idclean_v1\n",
                encoding="utf-8",
            )
            self.assertEqual(module.load_cpi_speed_pass_gates(path), {("model_surface", "SpeedFast")})

    def test_short_name_candidate_must_share_surname(self) -> None:
        module = _load_backtest_module()
        parsed = module._parse_tennis_data_short_name("Gomez F.")
        meta = {
            1: module._player_name_meta("Alejandro Pascacio F."),
            2: module._player_name_meta("Federico Agustin Gomez"),
        }
        self.assertFalse(module._candidate_matches_short_surname(1, parsed, meta))
        self.assertTrue(module._candidate_matches_short_surname(2, parsed, meta))

    def test_inactive_namesake_is_rejected(self) -> None:
        module = _load_backtest_module()
        players = [
            {"id": 1, "name": "Pablo Martinez"},
            {"id": 2, "name": "Pedro Martinez Portero"},
        ]
        indexes = module.idmap._build_oncourt_indexes(players)
        meta = {int(row["id"]): module._player_name_meta(row["name"]) for row in players}
        pid, _method = module._resolve_short_name_to_oncourt_id(
            "Martinez P.",
            indexes,
            meta,
            {1: 100, 2: 80},
            {1: {2002}, 2: {2024, 2025}},
            {2025},
        )
        self.assertEqual(pid, 2)

    def test_oncourt_rank_four_slam_is_supported(self) -> None:
        module = _load_backtest_module()
        self.assertTrue(module._is_supported_tour("Wimbledon - London", 4))


if __name__ == "__main__":
    unittest.main()
