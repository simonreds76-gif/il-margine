#!/usr/bin/env python3
"""Build the ATP Hard/Clay Most Aces 1X2 fair-price shadow board."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from tennis_most_aces import DEFAULT_RHO, fair_odds, most_aces_probabilities, pair_key


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT / "data" / "tennis-props" / "shadow" / "aces-v3-projection-board.csv"
DEFAULT_OUTPUT = ROOT / "data" / "tennis-props" / "shadow" / "most-aces-1x2-board.csv"
DEFAULT_CONFIG = ROOT / "data" / "tennis-props" / "models" / "most-aces-1x2-config.json"
FIELDS = [
    "generated_at_utc", "date", "tour", "tournament", "round", "surface",
    "player1", "player2", "player1_mean", "player2_mean", "alpha1", "alpha2",
    "rho", "p_player1", "p_draw", "p_player2", "fair_player1", "fair_draw",
    "fair_player2", "player1_confidence", "player2_confidence", "model",
    "scope", "notes",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def load_rho(path: Path) -> float:
    if not path.exists():
        return DEFAULT_RHO
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return float(payload.get("rho", DEFAULT_RHO))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return DEFAULT_RHO


def reciprocal_pair(left: dict[str, str], right: dict[str, str]) -> bool:
    return (
        pair_key(left.get("player"), left.get("opponent"))
        == pair_key(right.get("player"), right.get("opponent"))
        and str(left.get("player") or "").strip().casefold()
        == str(right.get("opponent") or "").strip().casefold()
    )


def build_rows(source_rows: list[dict[str, str]], rho: float) -> list[dict[str, str]]:
    eligible = [
        row for row in source_rows
        if (row.get("tour") or "").upper() == "ATP"
        and row.get("surface") in {"Hard", "Clay"}
        and truthy(row.get("v3_eligible"))
    ]
    grouped: dict[tuple[object, ...], list[dict[str, str]]] = {}
    for row in eligible:
        key = (
            row.get("date"), row.get("tour"), row.get("tournament"), row.get("round"),
            pair_key(row.get("player"), row.get("opponent")),
        )
        grouped.setdefault(key, []).append(row)

    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    output: list[dict[str, str]] = []
    for rows in grouped.values():
        if len(rows) != 2 or not reciprocal_pair(rows[0], rows[1]):
            continue
        left, right = rows
        try:
            mean1 = float(left["projected_aces"])
            mean2 = float(right["projected_aces"])
            alpha1 = float(left.get("aces_alpha") or 0.180034)
            alpha2 = float(right.get("aces_alpha") or 0.180034)
        except (KeyError, TypeError, ValueError):
            continue
        p1, draw, p2 = most_aces_probabilities(
            mean1, mean2, alpha1=alpha1, alpha2=alpha2, rho=rho
        )
        output.append({
            "generated_at_utc": generated,
            "date": left.get("date", ""),
            "tour": "ATP",
            "tournament": left.get("tournament", ""),
            "round": left.get("round", ""),
            "surface": left.get("surface", ""),
            "player1": left.get("player", ""),
            "player2": right.get("player", ""),
            "player1_mean": f"{mean1:.3f}",
            "player2_mean": f"{mean2:.3f}",
            "alpha1": f"{alpha1:.6f}",
            "alpha2": f"{alpha2:.6f}",
            "rho": f"{rho:.4f}",
            "p_player1": f"{p1:.6f}",
            "p_draw": f"{draw:.6f}",
            "p_player2": f"{p2:.6f}",
            "fair_player1": f"{fair_odds(p1):.3f}" if fair_odds(p1) else "",
            "fair_draw": f"{fair_odds(draw):.3f}" if fair_odds(draw) else "",
            "fair_player2": f"{fair_odds(p2):.3f}" if fair_odds(p2) else "",
            "player1_confidence": left.get("ace_confidence", ""),
            "player2_confidence": right.get("ace_confidence", ""),
            "model": "v3_aces_gaussian_copula_nb2",
            "scope": "ATP_HARD_CLAY_SHADOW",
            "notes": "CORRELATED_COUNTS|MOST_ACES_RESEARCH_ONLY",
        })
    return sorted(output, key=lambda row: (
        row["date"], row["tournament"], row["player1"], row["player2"]
    ))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    rho = load_rho(Path(args.config))
    rows = build_rows(read_csv(Path(args.source)), rho)
    write_csv(Path(args.output), rows)
    print(f"Most Aces 1X2 fair board: {len(rows)} matches -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

