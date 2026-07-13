"""Shared closing-snapshot selection and freshness helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any


TRUE_CLOSE_MAX_LAG_MINUTES = 120.0


def snapshot_at_or_before(
    items: list[dict[str, Any]],
    target: datetime | None,
) -> dict[str, Any] | None:
    if not items:
        return None
    if target is None:
        return items[-1]
    candidates = [item for item in items if item["captured_at"] <= target]
    return candidates[-1] if candidates else None


def snapshot_price(snapshot: dict[str, Any] | None) -> float | None:
    return float(snapshot["odds"]) if snapshot and snapshot.get("odds") is not None else None


def close_lag_minutes(snapshot: dict[str, Any] | None, kickoff: datetime | None) -> float | None:
    if not snapshot or kickoff is None:
        return None
    lag = (kickoff - snapshot["captured_at"]).total_seconds() / 60.0
    return round(lag, 3) if lag >= 0.0 else None


def is_true_close(lag_minutes: float | None, *, max_lag: float = TRUE_CLOSE_MAX_LAG_MINUTES) -> bool:
    return lag_minutes is not None and 0.0 <= lag_minutes <= max_lag
