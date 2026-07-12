#!/usr/bin/env python3
"""Compare committed tennis backtests with fail-closed identity regeneration."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import math
import subprocess
import sys
from io import StringIO
from pathlib import Path

from common import ROOT


BACKTEST_DIR = ROOT / "data" / "backtest"
REPORT = BACKTEST_DIR / "tennis-identity-audit.txt"


def _load_variant_module():
    path = ROOT / "scripts" / "tennis-model-variants-shadow.py"
    spec = importlib.util.spec_from_file_location("tennis_variants_identity_audit", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _read(years: list[int], suffix: str) -> list[dict[str, str]]:
    suffix_part = f"-{suffix}" if suffix else ""
    rows = []
    for year in years:
        path = BACKTEST_DIR / f"backtest-results-{year}{suffix_part}.csv"
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def _read_git_ref(years: list[int], git_ref: str) -> list[dict[str, str]]:
    rows = []
    for year in years:
        relative = f"data/backtest/backtest-results-{year}.csv"
        text = subprocess.check_output(
            ["git", "show", f"{git_ref}:{relative}"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
        )
        rows.extend(csv.DictReader(StringIO(text.lstrip("\ufeff"))))
    return rows


def _stable_key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        row.get("date", ""),
        row.get("tournament", ""),
        row.get("round", ""),
        row.get("series", ""),
        row.get("score", ""),
        row.get("pinnacle_odds", ""),
        row.get("pinnacle_odds_loser", ""),
    )


def _fmt(value: float) -> str:
    return "n/a" if not math.isfinite(value) else f"{value:+.2f}%"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", default="2022,2023,2024,2025")
    parser.add_argument("--clean-suffix", default="vnext-idclean")
    parser.add_argument("--baseline-git-ref", default="4585e625a", help="Immutable pre-repair baseline commit.")
    parser.add_argument("--output", type=Path, default=REPORT)
    args = parser.parse_args()
    years = [int(part) for part in args.years.split(",") if part.strip()]
    old_rows = _read_git_ref(years, args.baseline_git_ref) if args.baseline_git_ref else _read(years, "")
    clean_rows = _read(years, args.clean_suffix)
    old_by_key = {_stable_key(row): row for row in old_rows}
    clean_by_key = {_stable_key(row): row for row in clean_rows}
    paired_keys = sorted(set(old_by_key) & set(clean_by_key))
    changed = []
    probability_moves = []
    for key in paired_keys:
        old = old_by_key[key]
        clean = clean_by_key[key]
        old_identity = (old.get("player1_id"), old.get("player2_id"))
        clean_identity = (clean.get("player1_id"), clean.get("player2_id"))
        if old_identity != clean_identity:
            changed.append((old, clean))
        probability_moves.append(abs(float(old["our_prob"]) - float(clean["our_prob"])))

    variants = _load_variant_module()
    current = next(item for item in variants.VARIANTS if item.name == "baseline_current")
    summaries = {}
    for label, rows in (("committed", old_rows), ("identity_clean", clean_rows)):
        picks, quality = variants._score_variant(current, rows, {})
        summaries[label] = {
            "quality": quality,
            "strict": variants._summarize_picks([pick for pick in picks if pick.profile == "strict"]),
            "volume": variants._summarize_picks([pick for pick in picks if pick.profile == "volume_200_hard"]),
        }

    examples = []
    for old, clean in sorted(changed, key=lambda pair: abs(float(pair[0]["our_prob"]) - float(pair[1]["our_prob"])), reverse=True)[:15]:
        examples.append(
            f"- {old['date']} {old['tournament']}: "
            f"{old['player1']} ({old['player1_id']}) vs {old['player2']} ({old['player2_id']}) -> "
            f"{clean['player1']} ({clean['player1_id']}) vs {clean['player2']} ({clean['player2_id']}); "
            f"p1 {float(old['our_prob']):.3f}->{float(clean['our_prob']):.3f}"
        )

    old = summaries["committed"]
    clean = summaries["identity_clean"]
    lines = [
        "Tennis Historical Identity Integrity Audit",
        f"Years: {','.join(map(str, years))}",
        f"Baseline git ref: {args.baseline_git_ref or 'working tree'}",
        "Status: historical evidence repair; stale hard-calibration routing de-promoted separately",
        "",
        "Coverage",
        f"- committed rows: {len(old_rows)}",
        f"- identity-clean rows: {len(clean_rows)}",
        f"- stable paired rows: {len(paired_keys)}",
        f"- paired rows with changed player IDs: {len(changed)} ({100.0 * len(changed) / max(1, len(paired_keys)):.1f}%)",
        f"- mean absolute probability move: {100.0 * sum(probability_moves) / max(1, len(probability_moves)):.2f}pp",
        f"- max absolute probability move: {100.0 * max(probability_moves, default=0.0):.2f}pp",
        "",
        "Probability quality (same available Pinnacle rows)",
        f"- committed log-loss: {old['quality']['logloss']:.6f}",
        f"- identity-clean log-loss: {clean['quality']['logloss']:.6f}",
        f"- committed ECE: {old['quality']['ece']:.6f}",
        f"- identity-clean ECE: {clean['quality']['ece']:.6f}",
        "",
        f"Registered policy profiles, {min(years)}-{max(years)}",
        f"- strict committed: n={int(old['strict']['bets'])} tier ROI {_fmt(old['strict']['tier_roi_pct'])}",
        f"- strict identity-clean: n={int(clean['strict']['bets'])} tier ROI {_fmt(clean['strict']['tier_roi_pct'])}",
        f"- volume_200 hard committed: n={int(old['volume']['bets'])} tier ROI {_fmt(old['volume']['tier_roi_pct'])}",
        f"- volume_200 hard identity-clean: n={int(clean['volume']['bets'])} tier ROI {_fmt(clean['volume']['tier_roi_pct'])}",
        "",
        "Decision",
        f"- Identity-clean {min(years)}-{max(years)} artifacts were generated under the '{args.clean_suffix}' suffix and copied to the canonical working-tree CSVs; the immutable comparison baseline is {args.baseline_git_ref}.",
        "- Live/local daily pricing already uses direct OnCourt IDs; this finding is primarily a historical evidence problem.",
        "- The identity-clean baseline invalidated the previously promoted hard Platt overlay, so that overlay is now research-only until it is refit and passes a new registered holdout.",
        "- Do not promote vNext from this audit; its separate registered MVE failed.",
        "",
        "Largest identity-driven probability changes",
        *examples,
    ]
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:26]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
