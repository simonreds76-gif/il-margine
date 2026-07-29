from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from tennis_props_names import resolve_baseline_name


class TennisPropsNameResolutionTests(unittest.TestCase):
    def test_unique_first_last_removes_schedule_middle_name(self) -> None:
        resolved = resolve_baseline_name(
            tour="ATP",
            value="Taylor Harry Fritz",
            available_names={"ATP": {"taylor fritz", "kamil majchrzak"}},
        )
        self.assertEqual(resolved.name, "taylor fritz")
        self.assertEqual(resolved.method, "unique_first_last")

    def test_ambiguous_first_last_is_rejected(self) -> None:
        resolved = resolve_baseline_name(
            tour="ATP",
            value="Juan Martin Cerundolo",
            available_names={
                "ATP": {
                    "juan cerundolo",
                    "juan manuel cerundolo",
                }
            },
        )
        self.assertEqual(resolved.name, "juan martin cerundolo")
        self.assertEqual(resolved.method, "unresolved")

    def test_explicit_alias_precedes_automatic_fallback(self) -> None:
        resolved = resolve_baseline_name(
            tour="ATP",
            value="Known Alias",
            available_names={"ATP": {"canonical player"}},
            aliases={("ATP", "known alias"): "canonical player"},
        )
        self.assertEqual(resolved.name, "canonical player")
        self.assertEqual(resolved.method, "explicit_alias")


if __name__ == "__main__":
    unittest.main()
