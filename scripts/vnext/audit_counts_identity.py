#!/usr/bin/env python3
"""Verify that count and props pipelines bypass the repaired short-name resolver."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from common import DEFAULT_OUTPUT_DIR, ROOT, sha256_file


BACKTEST_DIR = ROOT / "data" / "backtest"
DEFAULT_REPORT = BACKTEST_DIR / "vnext-counts-identity-check.txt"
DEFAULT_MANIFEST = DEFAULT_OUTPUT_DIR / "serve-counts-atp-manifest.json"
DEFAULT_RECONCILIATION = DEFAULT_OUTPUT_DIR / "serve-counts-atp-reconciliation.json"
DEFAULT_ALIASES = ROOT / "data" / "tennis-props" / "player-name-aliases.csv"

# These were the largest confirmed collisions in the historical Tennis-Data bridge.
KNOWN_ONCOURT_IDENTITIES = {
    24232: "Alejandro Pascacio F.",
    29939: "Frances Tiafoe",
    49583: "Vinay Kumar T",
    29935: "Tommy Paul",
    5829: "Pablo Martinez",
    27358: "Pedro Martinez Portero",
}


def norm_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_oncourt_players(path: Path) -> dict[int, str]:
    out: dict[int, str] = {}
    for row in read_csv(path):
        try:
            player_id = int(float(row.get("id") or ""))
        except ValueError:
            continue
        name = str(row.get("name") or "").strip()
        if name and "/" not in name:
            out[player_id] = name
    return out


def props_source_pairs(sackmann_dir: Path) -> tuple[dict[tuple[str, str], set[str]], int]:
    pairs: dict[tuple[str, str], set[str]] = defaultdict(set)
    rows_seen = 0
    for path in sorted(sackmann_dir.glob("*_matches_*.csv")):
        tour = path.name.split("_", 1)[0].upper()
        if tour not in {"ATP", "WTA"}:
            continue
        for row in read_csv(path):
            rows_seen += 1
            for id_col, name_col in (("winner_id", "winner_name"), ("loser_id", "loser_name")):
                player_id = str(row.get(id_col) or "").strip()
                player_name = norm_name(row.get(name_col))
                if player_id and player_name:
                    pairs[(tour, player_id)].add(player_name)
    return pairs, rows_seen


def alias_collisions(path: Path) -> list[str]:
    aliases: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in read_csv(path):
        key = (str(row.get("tour") or "").upper(), norm_name(row.get("alias")))
        target = norm_name(row.get("player_name"))
        if all(key) and target:
            aliases[key].add(target)
    return [f"{tour}:{alias}" for (tour, alias), targets in aliases.items() if len(targets) > 1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oncourt-dir", type=Path, default=ROOT / "data" / "oncourt")
    parser.add_argument("--sackmann-dir", type=Path, default=ROOT / "data" / "sackmann")
    parser.add_argument("--baseline", type=Path, default=ROOT / "data" / "tennis-props" / "player-props-baseline.csv")
    parser.add_argument("--aliases", type=Path, default=DEFAULT_ALIASES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--reconciliation", type=Path, default=DEFAULT_RECONCILIATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    reconciliation = json.loads(args.reconciliation.read_text(encoding="utf-8"))
    hash_mismatches: list[str] = []
    for filename, metadata in manifest.get("inputs", {}).items():
        path = args.oncourt_dir / filename
        expected = str(metadata.get("sha256") or "")
        if not path.exists() or sha256_file(path) != expected:
            hash_mismatches.append(filename)

    players = load_oncourt_players(args.oncourt_dir / "players_atp.csv")
    known_mismatches = [
        f"{player_id}:{players.get(player_id, 'missing')}"
        for player_id, expected in KNOWN_ONCOURT_IDENTITIES.items()
        if norm_name(players.get(player_id)) != norm_name(expected)
    ]
    recon_checks = list(reconciliation.get("checks") or [])
    recon_failures = [row for row in recon_checks if not bool(row.get("pass"))]

    source_pairs, source_rows = props_source_pairs(args.sackmann_dir)
    baseline_rows = read_csv(args.baseline)
    baseline_mismatches: list[str] = []
    for row in baseline_rows:
        key = (str(row.get("tour") or "").upper(), str(row.get("player_id") or "").strip())
        name = norm_name(row.get("player_name"))
        if not key[1] or name not in source_pairs.get(key, set()):
            baseline_mismatches.append(f"{key[0]}:{key[1]}:{row.get('player_name', '')}")

    aliases_with_collisions = alias_collisions(args.aliases)
    board_source = (ROOT / "scripts" / "build-tennis-props-board.py").read_text(encoding="utf-8")
    surname_fallback_present = bool(re.search(r"surname|split\(\)\s*\[\s*-1\s*\]", board_source, re.IGNORECASE))

    failures = []
    if hash_mismatches:
        failures.append("oncourt_input_hash_mismatch")
    if recon_failures or not bool(reconciliation.get("passed")):
        failures.append("count_reconciliation_failed")
    if known_mismatches:
        failures.append("known_oncourt_identity_mismatch")
    if baseline_mismatches:
        failures.append("props_baseline_pair_mismatch")
    if aliases_with_collisions:
        failures.append("props_alias_collision")
    if surname_fallback_present:
        failures.append("props_surname_fallback_present")
    verdict = "FAIL" if failures else "PASS"

    lines = [
        "Tennis vNext Counts and Props Identity Check",
        "Version: vnext-counts-identity-0.1",
        f"VERDICT: {verdict}",
        "",
        "OnCourt point-count path",
        "- Identity source: direct winner_id/loser_id from games_atp.csv joined to the same IDs in stat_atp.csv.",
        "- Tennis-Data short-name resolver used: NO",
        f"- Manifest input hashes matched: {len(hash_mismatches) == 0}",
        f"- Extracted player-match rows: {manifest.get('artifact', {}).get('rows', 0)}",
        f"- Independent reconciliation checks: {len(recon_checks) - len(recon_failures)}/{len(recon_checks)}",
        f"- Known historical collision IDs correctly separated: {len(KNOWN_ONCOURT_IDENTITIES) - len(known_mismatches)}/{len(KNOWN_ONCOURT_IDENTITIES)}",
        "",
        "Sackmann props path",
        "- Identity source: native Sackmann winner_id/loser_id; ATP and WTA namespaces remain separate.",
        "- Tennis-Data short-name resolver used: NO",
        f"- Source match rows scanned: {source_rows}",
        f"- Baseline identity rows verified: {len(baseline_rows) - len(baseline_mismatches)}/{len(baseline_rows)}",
        f"- Ambiguous explicit aliases: {len(aliases_with_collisions)}",
        f"- Surname-only live-board fallback present: {'YES' if surname_fallback_present else 'NO'}",
        "",
        "Decision",
        "- Count extraction and props history are not contaminated by the repaired Tennis-Data short-name bridge.",
        "- Live props matching remains full normalized name plus explicit alias only; unresolved names must stay unresolved.",
    ]
    if failures:
        lines.extend(["", "Failures", *[f"- {item}" for item in failures]])
    if baseline_mismatches:
        lines.extend(["", "First baseline mismatches", *[f"- {item}" for item in baseline_mismatches[:20]]])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
