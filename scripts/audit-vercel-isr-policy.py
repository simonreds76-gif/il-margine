#!/usr/bin/env python3
"""Fail closed when public-page caching can waste Vercel Hobby ISR writes."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# These pages are large or frequently visited. They must use on-demand
# invalidation with a long time-based fallback, not minute-level regeneration.
MIN_REVALIDATE_SECONDS = {
    "src/app/page.tsx": 86_400,
    "src/app/player-props/page.tsx": 86_400,
    "src/app/tennis-tips/page.tsx": 86_400,
    "src/app/tips/[slugId]/page.tsx": 86_400,
    "src/app/betting-tips/[slugId]/page.tsx": 86_400,
    "src/app/betting-tips/[slugId]/opengraph-image.tsx": 86_400,
    "src/app/world-cup-2026-free-picks/page.tsx": 86_400,
    "src/app/fair-odds-lab/world-cup/page.tsx": 86_400,
    "src/app/penalty-takers/page.tsx": 43_200,
    "src/app/penalty-takers/[leagueSlug]/page.tsx": 43_200,
    "src/app/penalty-takers/[leagueSlug]/[teamSlug]/page.tsx": 43_200,
}

ADMIN_BETS_ROUTE = "src/app/api/admin/bets/route.ts"
REVALIDATE_PATTERN = re.compile(r"export\s+const\s+revalidate\s*=\s*(\d+)\s*;?")


def audit_isr_policy(root: Path = ROOT) -> list[str]:
    issues: list[str] = []

    for relative_path, minimum in MIN_REVALIDATE_SECONDS.items():
        path = root / relative_path
        if not path.exists():
            issues.append(f"missing protected route: {relative_path}")
            continue
        text = path.read_text(encoding="utf-8")
        match = REVALIDATE_PATTERN.search(text)
        if not match:
            issues.append(f"missing explicit revalidate fallback: {relative_path}")
            continue
        actual = int(match.group(1))
        if actual < minimum:
            issues.append(
                f"short revalidate on {relative_path}: {actual}s (minimum {minimum}s)"
            )

    admin_path = root / ADMIN_BETS_ROUTE
    if not admin_path.exists():
        issues.append(f"missing admin invalidation route: {ADMIN_BETS_ROUTE}")
        return issues

    admin_text = admin_path.read_text(encoding="utf-8")
    forbidden_fragments = {
        'revalidatePath("/tips/[slugId]"': "broad dynamic tip-page invalidation",
        'revalidatePath("/betting-tips/[slugId]"': "broad dynamic SEO-page invalidation",
        'revalidatePath("/", "layout")': "whole-site layout invalidation",
        "revalidatePath('/', 'layout')": "whole-site layout invalidation",
    }
    for fragment, label in forbidden_fragments.items():
        if fragment in admin_text:
            issues.append(f"{label} found in {ADMIN_BETS_ROUTE}")

    required_fragments = {
        'tipPaths.add(`/tips/${slugifyTip(bet.event, bet.id)}`)': "exact public tip invalidation",
        "tipPaths.add(previewPath)": "exact SEO tip invalidation",
        'markets.has("props")': "market-scoped player-props invalidation",
        'markets.has("tennis")': "market-scoped tennis invalidation",
    }
    for fragment, label in required_fragments.items():
        if fragment not in admin_text:
            issues.append(f"missing {label} in {ADMIN_BETS_ROUTE}")

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output.")
    args = parser.parse_args()

    issues = audit_isr_policy()
    payload = {"ok": not issues, "issues": issues}
    if args.json:
        print(json.dumps(payload, separators=(",", ":")))
    elif issues:
        print("VERCEL_ISR_POLICY_FAIL")
        for issue in issues:
            print(f"- {issue}")
    else:
        print("VERCEL_ISR_POLICY_OK")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
