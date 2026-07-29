#!/usr/bin/env python3
"""Build one causal canonical row per ATP Most Aces match."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = (
    ROOT / "data" / "tennis-props" / "experiments"
    / "most-aces-coverage-a1" / "a3" / "aces-dfs-v3-features.csv"
)
DEFAULT_OUTPUT = (
    ROOT / "data" / "tennis-props" / "experiments"
    / "most-aces-direct-1x2" / "pairwise-features.csv"
)
SIDE_METRICS = (
    "incumbent_aces",
    "expected_service_points",
    "opponent_return_factor",
    "player_ace_rate_blend",
    "player_l12m_ace_rate",
    "player_l24m_ace_rate",
    "player_career4y_ace_rate",
    "opponent_aces_allowed_blend",
    "opponent_l12m_aces_allowed_rate",
    "opponent_l24m_aces_allowed_rate",
    "opponent_career4y_aces_allowed_rate",
    "player_svpt_per_svg_blend",
    "player_l12m_first_win_pct",
    "player_l12m_second_win_pct",
    "player_rank",
    "player_age",
    "player_height",
    "player_activity_days_since_match_all",
    "player_activity_days_since_surface_match",
    "player_activity_matches_l90d_all",
    "player_activity_matches_l365d_all",
    "player_activity_lower_matches_l90d",
    "player_activity_lower_matches_l365d",
    "player_activity_lower_share_l365d",
    "player_activity_rank_log_change_90d",
    "player_activity_rank_log_change_365d",
)
IDENTITY = (
    "date",
    "year",
    "tour",
    "tournament",
    "surface",
    "level",
    "round",
    "best_of",
    "player1_id",
    "player1",
    "player2_id",
    "player2",
    "actual_aces1",
    "actual_aces2",
    "outcome",
    "evidence_tier",
)


def numeric(row: pd.Series, name: str, default: float = 0.0) -> float:
    try:
        value = float(row.get(name, default))
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def evidence_tier(left: pd.Series, right: pd.Series) -> str:
    recent = all(
        numeric(row, "player_l12m_matches") >= 4
        and numeric(row, "player_l12m_svpt") >= 250
        for row in (left, right)
    )
    if recent:
        return "RECENT"
    coverage = all(
        numeric(row, "player_activity_matches_l365d_all") >= 4
        for row in (left, right)
    )
    if coverage:
        return "COVERAGE_GAP"
    historical = all(
        (
            numeric(row, "player_l24m_matches") >= 12
            and numeric(row, "player_l24m_svpt") >= 800
        )
        or (
            numeric(row, "player_career4y_matches") >= 20
            and numeric(row, "player_career4y_svpt") >= 1500
        )
        for row in (left, right)
    )
    return "HISTORICAL" if historical else "INSUFFICIENT"


def canonical_pair(group: pd.DataFrame) -> tuple[pd.Series, pd.Series] | None:
    if len(group) != 2:
        return None
    rows = [row for _index, row in group.iterrows()]
    left, right = sorted(
        rows,
        key=lambda row: (
            str(row.get("player_id") or ""),
            str(row.get("player") or ""),
        ),
    )
    if str(left.get("player_id")) != str(right.get("opponent_id")):
        return None
    if str(right.get("player_id")) != str(left.get("opponent_id")):
        return None
    return left, right


def pairwise_feature_row(
    left: pd.Series,
    right: pd.Series,
    *,
    include_target: bool = True,
) -> dict[str, object]:
    """Render one ordered pair with the exact registered feature algebra."""
    actual1 = int(round(numeric(left, "actual_aces")))
    actual2 = int(round(numeric(right, "actual_aces")))
    outcome = "P1" if actual1 > actual2 else "P2" if actual2 > actual1 else "DRAW"
    row: dict[str, object] = {
        "date": str(left["date"]),
        "year": int(numeric(left, "year")),
        "tour": "ATP",
        "tournament": str(left["tournament"]),
        "surface": str(left["surface"]),
        "level": str(left.get("level") or ""),
        "round": str(left.get("round") or ""),
        "best_of": int(numeric(left, "best_of", 3)),
        "player1_id": str(left["player_id"]),
        "player1": str(left["player"]),
        "player2_id": str(right["player_id"]),
        "player2": str(right["player"]),
        "actual_aces1": actual1 if include_target else "",
        "actual_aces2": actual2 if include_target else "",
        "outcome": outcome if include_target else "",
        "evidence_tier": evidence_tier(left, right),
        "surface_prior_ace_rate": (
            numeric(left, "surface_prior_ace_rate")
            + numeric(right, "surface_prior_ace_rate")
        ) / 2.0,
        "venue_ace_factor": (
            numeric(left, "venue_ace_factor")
            + numeric(right, "venue_ace_factor")
        ) / 2.0,
        "expected_match_games": (
            numeric(left, "expected_match_games")
            + numeric(right, "expected_match_games")
        ) / 2.0,
    }
    for metric in SIDE_METRICS:
        value1 = numeric(left, metric)
        value2 = numeric(right, metric)
        row[f"{metric}_diff"] = value1 - value2
        row[f"{metric}_sum"] = value1 + value2
    row["incumbent_aces_abs_diff"] = abs(
        float(row["incumbent_aces_diff"])
    )
    return row


def pairwise_rows(frame: pd.DataFrame) -> list[dict[str, object]]:
    required = {
        "date", "year", "tour", "tournament", "surface", "round",
        "player_id", "opponent_id", "player", "opponent",
        "actual_aces", *SIDE_METRICS,
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Missing pairwise source fields: {', '.join(missing)}")
    work = frame[
        (frame["tour"].astype(str).str.upper() == "ATP")
        & (frame["surface"].astype(str).isin(("Hard", "Clay")))
    ].copy()
    work["_pair"] = work.apply(
        lambda row: "|".join(sorted((
            str(row.get("player_id") or ""),
            str(row.get("opponent_id") or ""),
        ))),
        axis=1,
    )
    output: list[dict[str, object]] = []
    keys = ["date", "tour", "tournament", "round", "_pair"]
    for _key, group in work.groupby(keys, sort=True, observed=True):
        pair = canonical_pair(group)
        if pair is None:
            continue
        left, right = pair
        output.append(pairwise_feature_row(left, right))
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    frame = pd.read_csv(args.source)
    rows = pairwise_rows(frame)
    if not rows:
        raise SystemExit("No pairwise Most Aces rows generated")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.out, index=False)
    print(f"Wrote {args.out} ({len(rows)} matches)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
