#!/usr/bin/env python3
"""Build the ATP Hard/Clay Most Aces 1X2 fair-price shadow board."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from tennis_most_aces import (
    DEFAULT_RHO,
    fair_odds,
    most_aces_probabilities,
    pair_key,
    recent_activity,
    sample_evidence_tier,
)


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT / "data" / "tennis-props" / "shadow" / "aces-v3-projection-board.csv"
DEFAULT_OUTPUT = ROOT / "data" / "tennis-props" / "shadow" / "most-aces-1x2-board.csv"
DEFAULT_CONFIG = ROOT / "data" / "tennis-props" / "models" / "most-aces-1x2-config.json"
FIELDS = [
    "generated_at_utc", "date", "tour", "tournament", "round", "surface",
    "player1", "player2", "player1_mean", "player2_mean", "alpha1", "alpha2",
    "rho", "p_player1", "p_draw", "p_player2", "fair_player1", "fair_draw",
    "fair_player2", "player1_confidence", "player2_confidence",
    "player1_name_resolution", "player2_name_resolution",
    "player1_l12m_matches", "player2_l12m_matches",
    "player1_l12m_svpt", "player2_l12m_svpt",
    "player1_l24m_matches", "player2_l24m_matches",
    "player1_l24m_svpt", "player2_l24m_svpt",
    "player1_career4y_matches", "player2_career4y_matches",
    "player1_career4y_svpt", "player2_career4y_svpt",
    "player1_activity_l12m_matches", "player2_activity_l12m_matches",
    "player1_activity_l12m_svpt", "player2_activity_l12m_svpt",
    "player1_activity_l12m_qual_chall_matches", "player2_activity_l12m_qual_chall_matches",
    "player1_evidence_tier", "player2_evidence_tier",
    "quote_status", "quote_reason", "model", "scope", "notes",
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


def int_value(value: object) -> int:
    try:
        return int(float(str(value or "").strip()))
    except (TypeError, ValueError):
        return 0


def quote_quality(
    left: dict[str, str],
    right: dict[str, str],
) -> tuple[str, str, str, str]:
    reasons: list[str] = []
    evidence_tiers: list[str] = []
    for label, row in (("P1", left), ("P2", right)):
        resolution = str(row.get("player_name_resolution") or "").strip()
        if resolution not in {"exact", "explicit_alias", "unique_first_last"}:
            reasons.append(f"{label}_NAME_UNRESOLVED")
        performance_tier = sample_evidence_tier(
            l12m_matches=int_value(row.get("player_l12m_matches")),
            l12m_service_points=int_value(row.get("player_l12m_svpt_sample")),
            l24m_matches=int_value(row.get("player_l24m_matches")),
            l24m_service_points=int_value(row.get("player_l24m_svpt_sample")),
            career_matches=int_value(
                row.get("player_career4y_matches") or row.get("player_surface_matches")
            ),
            career_service_points=int_value(
                row.get("player_career4y_svpt_sample") or row.get("player_surface_svpt_sample")
            ),
        )
        activity_matches = int_value(
            row.get("player_activity_l12m_matches") or row.get("player_l12m_matches")
        )
        activity_svpt = int_value(
            row.get("player_activity_l12m_svpt") or row.get("player_l12m_svpt_sample")
        )
        tier = performance_tier
        if performance_tier == "HISTORICAL" and recent_activity(activity_matches, activity_svpt):
            tier = "COVERAGE_GAP"
        evidence_tiers.append(tier)
        if tier == "COVERAGE_GAP":
            reasons.append(
                f"{label}_ACTIVITY_COVERAGE_GAP_"
                f"{activity_matches}M_{activity_svpt}SVPT_L12M"
            )
        elif tier == "HISTORICAL":
            reasons.append(
                f"{label}_STALE_FORM_"
                f"{int_value(row.get('player_l12m_matches'))}M_"
                f"{int_value(row.get('player_l12m_svpt_sample'))}SVPT_L12M"
            )
        elif tier == "INSUFFICIENT":
            reasons.append(f"{label}_INSUFFICIENT_HISTORY")
        notes = str(row.get("notes") or "")
        if "NO_OPP_DATA" in notes or "OPPONENT_NAME_UNRESOLVED" in notes:
            reasons.append(f"{label}_OPPONENT_DATA_MISSING")
    hard_block = any(
        reason.endswith("_NAME_UNRESOLVED")
        or reason.endswith("_OPPONENT_DATA_MISSING")
        or reason.endswith("_INSUFFICIENT_HISTORY")
        for reason in reasons
    )
    reason = "|".join(dict.fromkeys(reasons))
    if hard_block:
        return "BLOCKED_INPUT_QUALITY", reason, evidence_tiers[0], evidence_tiers[1]
    if "COVERAGE_GAP" in evidence_tiers:
        return "COVERAGE_GAP_ESTIMATE", reason, evidence_tiers[0], evidence_tiers[1]
    if "HISTORICAL" in evidence_tiers:
        return "HISTORICAL_ESTIMATE", reason, evidence_tiers[0], evidence_tiers[1]
    return "READY", "", evidence_tiers[0], evidence_tiers[1]


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
        quote_status, quote_reason, player1_tier, player2_tier = quote_quality(left, right)
        quote_visible = quote_status in {
            "READY", "HISTORICAL_ESTIMATE", "COVERAGE_GAP_ESTIMATE",
        }
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
            "fair_player1": f"{fair_odds(p1):.3f}" if quote_visible and fair_odds(p1) else "",
            "fair_draw": f"{fair_odds(draw):.3f}" if quote_visible and fair_odds(draw) else "",
            "fair_player2": f"{fair_odds(p2):.3f}" if quote_visible and fair_odds(p2) else "",
            "player1_confidence": left.get("ace_confidence", ""),
            "player2_confidence": right.get("ace_confidence", ""),
            "player1_name_resolution": left.get("player_name_resolution", ""),
            "player2_name_resolution": right.get("player_name_resolution", ""),
            "player1_l12m_matches": left.get("player_l12m_matches", ""),
            "player2_l12m_matches": right.get("player_l12m_matches", ""),
            "player1_l12m_svpt": left.get("player_l12m_svpt_sample", ""),
            "player2_l12m_svpt": right.get("player_l12m_svpt_sample", ""),
            "player1_l24m_matches": left.get("player_l24m_matches", ""),
            "player2_l24m_matches": right.get("player_l24m_matches", ""),
            "player1_l24m_svpt": left.get("player_l24m_svpt_sample", ""),
            "player2_l24m_svpt": right.get("player_l24m_svpt_sample", ""),
            "player1_career4y_matches": left.get("player_career4y_matches", ""),
            "player2_career4y_matches": right.get("player_career4y_matches", ""),
            "player1_career4y_svpt": left.get("player_career4y_svpt_sample", ""),
            "player2_career4y_svpt": right.get("player_career4y_svpt_sample", ""),
            "player1_activity_l12m_matches": left.get("player_activity_l12m_matches", ""),
            "player2_activity_l12m_matches": right.get("player_activity_l12m_matches", ""),
            "player1_activity_l12m_svpt": left.get("player_activity_l12m_svpt", ""),
            "player2_activity_l12m_svpt": right.get("player_activity_l12m_svpt", ""),
            "player1_activity_l12m_qual_chall_matches": left.get("player_activity_l12m_qual_chall_matches", ""),
            "player2_activity_l12m_qual_chall_matches": right.get("player_activity_l12m_qual_chall_matches", ""),
            "player1_evidence_tier": player1_tier,
            "player2_evidence_tier": player2_tier,
            "quote_status": quote_status,
            "quote_reason": quote_reason,
            "model": "v3_aces_gaussian_copula_nb2_evidence_tiers_v3",
            "scope": "ATP_HARD_CLAY_SHADOW",
            "notes": "|".join(
                part
                for part in (
                    "CORRELATED_COUNTS",
                    "MOST_ACES_RESEARCH_ONLY",
                    quote_status if quote_status != "READY" else "",
                )
                if part
            ),
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
