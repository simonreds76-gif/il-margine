from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "audit-vercel-isr-policy.py"
SPEC = importlib.util.spec_from_file_location("vercel_isr_policy", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class VercelIsrPolicyTests(unittest.TestCase):
    def make_fixture(self, root: Path, *, homepage_revalidate: int = 86_400) -> None:
        for relative_path, minimum in MODULE.MIN_REVALIDATE_SECONDS.items():
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            value = homepage_revalidate if relative_path == "src/app/page.tsx" else minimum
            path.write_text(f"export const revalidate = {value};\n", encoding="utf-8")

        admin_path = root / MODULE.ADMIN_BETS_ROUTE
        admin_path.parent.mkdir(parents=True, exist_ok=True)
        admin_path.write_text(
            "\n".join(
                [
                    'tipPaths.add(`/tips/${slugifyTip(bet.event, bet.id)}`);',
                    "tipPaths.add(previewPath);",
                    'if (markets.has("props")) revalidatePath("/player-props");',
                    'if (markets.has("tennis")) revalidatePath("/tennis-tips");',
                ]
            ),
            encoding="utf-8",
        )

    def test_current_event_driven_policy_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_fixture(root)
            self.assertEqual(MODULE.audit_isr_policy(root), [])

    def test_short_homepage_revalidation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_fixture(root, homepage_revalidate=60)
            issues = MODULE.audit_isr_policy(root)
            self.assertTrue(any("short revalidate on src/app/page.tsx" in issue for issue in issues))

    def test_broad_dynamic_tip_invalidation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_fixture(root)
            admin_path = root / MODULE.ADMIN_BETS_ROUTE
            admin_path.write_text(
                admin_path.read_text(encoding="utf-8")
                + '\nrevalidatePath("/tips/[slugId]", "page");\n',
                encoding="utf-8",
            )
            issues = MODULE.audit_isr_policy(root)
            self.assertTrue(any("broad dynamic tip-page invalidation" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
