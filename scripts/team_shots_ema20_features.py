"""Frozen v3 feature summaries from 5b6fc5331; prior matches only."""
from __future__ import annotations
from typing import Any, Iterable
EMA_WINDOW = 20
EMA_DECAY = 0.93

def parse_float(value: Any, default: float = 0.0) -> float:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def numeric(row: dict[str, Any], key: str) -> float | None:
    value = parse_float(row.get(key), default=float("nan"))
    if value != value:
        return None
    return value


def avg(values: Iterable[float | None]) -> str:
    present = [value for value in values if value is not None]
    if not present:
        return ""
    return f"{sum(present) / len(present):.4f}".rstrip("0").rstrip(".")


def weighted_avg(values: Iterable[tuple[float | None, float]]) -> str:
    present = [(value, weight) for value, weight in values if value is not None and weight > 0]
    weight_sum = sum(weight for _, weight in present)
    if not present or weight_sum <= 0:
        return ""
    return f"{sum(value * weight for value, weight in present) / weight_sum:.4f}".rstrip("0").rstrip(".")


def ratio(num: float | None, den: float | None) -> str:
    if num is None or den is None or den <= 0:
        return ""
    return f"{num / den:.4f}".rstrip("0").rstrip(".")


def summarize_window(history: list[dict[str, Any]], window: int) -> dict[str, Any]:
    recent = history[-window:]
    home_rows = [row for row in recent if row.get("venue") == "home"]
    away_rows = [row for row in recent if row.get("venue") == "away"]
    xg_for_sum = sum((numeric(row, "xg_for") or 0.0) for row in recent)
    xg_against_sum = sum((numeric(row, "xg_against") or 0.0) for row in recent)
    shots_for_sum = sum((numeric(row, "shots_for") or 0.0) for row in recent)
    shots_against_sum = sum((numeric(row, "shots_against") or 0.0) for row in recent)
    return {
        f"r{window}_matches": len(recent),
        f"r{window}_home_matches": len(home_rows),
        f"r{window}_away_matches": len(away_rows),
        f"r{window}_goals_for_avg": avg(numeric(row, "goals_for") for row in recent),
        f"r{window}_goals_against_avg": avg(numeric(row, "goals_against") for row in recent),
        f"r{window}_xg_for_avg": avg(numeric(row, "xg_for") for row in recent if numeric(row, "xg_for") is not None),
        f"r{window}_xg_against_avg": avg(numeric(row, "xg_against") for row in recent if numeric(row, "xg_against") is not None),
        f"r{window}_xg_for_home_avg": avg(numeric(row, "xg_for") for row in home_rows if numeric(row, "xg_for") is not None),
        f"r{window}_xg_for_away_avg": avg(numeric(row, "xg_for") for row in away_rows if numeric(row, "xg_for") is not None),
        f"r{window}_shots_for_avg": avg(numeric(row, "shots_for") for row in recent),
        f"r{window}_shots_against_avg": avg(numeric(row, "shots_against") for row in recent),
        f"r{window}_shots_for_home_avg": avg(numeric(row, "shots_for") for row in home_rows),
        f"r{window}_shots_for_away_avg": avg(numeric(row, "shots_for") for row in away_rows),
        f"r{window}_shots_against_home_avg": avg(numeric(row, "shots_against") for row in home_rows),
        f"r{window}_shots_against_away_avg": avg(numeric(row, "shots_against") for row in away_rows),
        f"r{window}_sot_for_avg": avg(numeric(row, "sot_for") for row in recent),
        f"r{window}_sot_against_avg": avg(numeric(row, "sot_against") for row in recent),
        f"r{window}_sot_for_home_avg": avg(numeric(row, "sot_for") for row in home_rows),
        f"r{window}_sot_for_away_avg": avg(numeric(row, "sot_for") for row in away_rows),
        f"r{window}_sot_against_home_avg": avg(numeric(row, "sot_against") for row in home_rows),
        f"r{window}_sot_against_away_avg": avg(numeric(row, "sot_against") for row in away_rows),
        f"r{window}_corners_for_avg": avg(numeric(row, "corners_for") for row in recent),
        f"r{window}_corners_against_avg": avg(numeric(row, "corners_against") for row in recent),
        f"r{window}_corners_for_home_avg": avg(numeric(row, "corners_for") for row in home_rows),
        f"r{window}_corners_for_away_avg": avg(numeric(row, "corners_for") for row in away_rows),
        f"r{window}_corners_against_home_avg": avg(numeric(row, "corners_against") for row in home_rows),
        f"r{window}_corners_against_away_avg": avg(numeric(row, "corners_against") for row in away_rows),
        f"r{window}_xg_per_shot_for": ratio(xg_for_sum, shots_for_sum),
        f"r{window}_xg_per_shot_against": ratio(xg_against_sum, shots_against_sum),
        f"r{window}_opponent_market_strength_avg": avg(numeric(row, "market_opp_win_prob") for row in recent),
    }


def summarize_ema_window(history: list[dict[str, Any]]) -> dict[str, Any]:
    recent = history[-EMA_WINDOW:]
    prefix = f"ema{EMA_WINDOW}"
    weighted_rows = [
        (row, EMA_DECAY ** (len(recent) - 1 - index))
        for index, row in enumerate(recent)
    ]
    home_rows = [(row, weight) for row, weight in weighted_rows if row.get("venue") == "home"]
    away_rows = [(row, weight) for row, weight in weighted_rows if row.get("venue") == "away"]

    xg_for_sum = sum((numeric(row, "xg_for") or 0.0) * weight for row, weight in weighted_rows)
    xg_against_sum = sum((numeric(row, "xg_against") or 0.0) * weight for row, weight in weighted_rows)
    shots_for_sum = sum((numeric(row, "shots_for") or 0.0) * weight for row, weight in weighted_rows)
    shots_against_sum = sum((numeric(row, "shots_against") or 0.0) * weight for row, weight in weighted_rows)

    return {
        f"{prefix}_matches": len(recent),
        f"{prefix}_home_matches": len(home_rows),
        f"{prefix}_away_matches": len(away_rows),
        f"{prefix}_goals_for_avg": weighted_avg((numeric(row, "goals_for"), weight) for row, weight in weighted_rows),
        f"{prefix}_goals_against_avg": weighted_avg((numeric(row, "goals_against"), weight) for row, weight in weighted_rows),
        f"{prefix}_xg_for_avg": weighted_avg((numeric(row, "xg_for"), weight) for row, weight in weighted_rows),
        f"{prefix}_xg_against_avg": weighted_avg((numeric(row, "xg_against"), weight) for row, weight in weighted_rows),
        f"{prefix}_xg_for_home_avg": weighted_avg((numeric(row, "xg_for"), weight) for row, weight in home_rows),
        f"{prefix}_xg_for_away_avg": weighted_avg((numeric(row, "xg_for"), weight) for row, weight in away_rows),
        f"{prefix}_shots_for_avg": weighted_avg((numeric(row, "shots_for"), weight) for row, weight in weighted_rows),
        f"{prefix}_shots_against_avg": weighted_avg((numeric(row, "shots_against"), weight) for row, weight in weighted_rows),
        f"{prefix}_shots_for_home_avg": weighted_avg((numeric(row, "shots_for"), weight) for row, weight in home_rows),
        f"{prefix}_shots_for_away_avg": weighted_avg((numeric(row, "shots_for"), weight) for row, weight in away_rows),
        f"{prefix}_shots_against_home_avg": weighted_avg((numeric(row, "shots_against"), weight) for row, weight in home_rows),
        f"{prefix}_shots_against_away_avg": weighted_avg((numeric(row, "shots_against"), weight) for row, weight in away_rows),
        f"{prefix}_sot_for_avg": weighted_avg((numeric(row, "sot_for"), weight) for row, weight in weighted_rows),
        f"{prefix}_sot_against_avg": weighted_avg((numeric(row, "sot_against"), weight) for row, weight in weighted_rows),
        f"{prefix}_sot_for_home_avg": weighted_avg((numeric(row, "sot_for"), weight) for row, weight in home_rows),
        f"{prefix}_sot_for_away_avg": weighted_avg((numeric(row, "sot_for"), weight) for row, weight in away_rows),
        f"{prefix}_sot_against_home_avg": weighted_avg((numeric(row, "sot_against"), weight) for row, weight in home_rows),
        f"{prefix}_sot_against_away_avg": weighted_avg((numeric(row, "sot_against"), weight) for row, weight in away_rows),
        f"{prefix}_corners_for_avg": weighted_avg((numeric(row, "corners_for"), weight) for row, weight in weighted_rows),
        f"{prefix}_corners_against_avg": weighted_avg((numeric(row, "corners_against"), weight) for row, weight in weighted_rows),
        f"{prefix}_corners_for_home_avg": weighted_avg((numeric(row, "corners_for"), weight) for row, weight in home_rows),
        f"{prefix}_corners_for_away_avg": weighted_avg((numeric(row, "corners_for"), weight) for row, weight in away_rows),
        f"{prefix}_corners_against_home_avg": weighted_avg((numeric(row, "corners_against"), weight) for row, weight in home_rows),
        f"{prefix}_corners_against_away_avg": weighted_avg((numeric(row, "corners_against"), weight) for row, weight in away_rows),
        f"{prefix}_xg_per_shot_for": ratio(xg_for_sum, shots_for_sum),
        f"{prefix}_xg_per_shot_against": ratio(xg_against_sum, shots_against_sum),
        f"{prefix}_opponent_market_strength_avg": weighted_avg(
            (numeric(row, "market_opp_win_prob"), weight) for row, weight in weighted_rows
        ),
    }
