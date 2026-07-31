from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
MODULE_PATH = SCRIPTS / "sackmann-compute-slam-venue-factors.py"
SPEC = importlib.util.spec_from_file_location("sackmann_venue_factors", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def totals(*, matches: int, aces: int, svpt: int) -> dict[str, float]:
    row = MODULE.empty_totals()
    row.update({"matches": matches, "aces": aces, "svpt": svpt})
    return row


class VenueAceFactorV1Tests(unittest.TestCase):
    def test_candidate_name_preserves_known_alias_and_falls_back_to_location(self) -> None:
        self.assertEqual(MODULE.candidate_tournament_name("ATP 250 - Swiss Open Gstaad"), "Gstaad")
        self.assertEqual(MODULE.candidate_tournament_name("ATP 500 - Washington"), "Washington")
        self.assertEqual(MODULE.venue_key("Kitzbühel"), "kitzbuhel")

    def test_factor_uses_only_three_prior_seasons_and_shrinks_by_service_points(self) -> None:
        event = {
            ("atp", "Gstaad", "Clay", 2023): totals(matches=20, aces=180, svpt=2000),
            ("atp", "Gstaad", "Clay", 2024): totals(matches=20, aces=180, svpt=2000),
            ("atp", "Gstaad", "Clay", 2025): totals(matches=20, aces=180, svpt=2000),
            # This target-season outlier must never enter the 2026 factor.
            ("atp", "Gstaad", "Clay", 2026): totals(matches=20, aces=0, svpt=2000),
        }
        surface = {
            ("atp", "Clay", 2023): totals(matches=200, aces=1000, svpt=20000),
            ("atp", "Clay", 2024): totals(matches=200, aces=1000, svpt=20000),
            ("atp", "Clay", 2025): totals(matches=200, aces=1000, svpt=20000),
            ("atp", "Clay", 2026): totals(matches=200, aces=6000, svpt=20000),
        }

        rows = MODULE.candidate_factor_rows(event, surface, target_season=2026)
        row = next(item for item in rows if item["tournament"] == "Gstaad")
        self.assertEqual(row["source_start_season"], "2023")
        self.assertEqual(row["source_end_season"], "2025")
        self.assertEqual(row["n_prior_svpt"], "6000")
        # Raw factor 1.8, shrunk with 6000/(6000+1500) -> 1.64.
        self.assertAlmostEqual(float(row["raw_ace_factor"]), 1.8, places=6)
        self.assertAlmostEqual(float(row["ace_factor"]), 1.64, places=6)

    def test_insufficient_sample_is_neutral(self) -> None:
        event = {("wta", "Example", "Hard", 2025): totals(matches=5, aces=100, svpt=1000)}
        surface = {("wta", "Hard", 2025): totals(matches=100, aces=500, svpt=10000)}
        row = MODULE.candidate_factor_rows(event, surface, target_season=2026)[0]
        self.assertEqual(row["eligible"], "false")
        self.assertEqual(float(row["ace_factor"]), 1.0)


if __name__ == "__main__":
    unittest.main()
