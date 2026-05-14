"""Internal tennis lane registry helpers.

Phase 0 keeps this module deliberately passive: it reads the declarative lane
config, but no live fair-odds path imports it yet.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LANE_CONFIG_PATH = PROJECT_ROOT / "data" / "backtest" / "lane-config.json"


@lru_cache(maxsize=4)
def load_lane_config(path: str | Path = DEFAULT_LANE_CONFIG_PATH) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    with config_path.open("r", encoding="utf-8") as f:
        config = json.load(f)
    lanes = config.get("lanes")
    if not isinstance(lanes, dict):
        raise ValueError(f"Lane config missing lanes object: {config_path}")
    return config


def lane_ids(config: dict[str, Any] | None = None) -> list[str]:
    cfg = config or load_lane_config()
    return list((cfg.get("lanes") or {}).keys())


def lane_config(lane_id: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or load_lane_config()
    lanes = cfg.get("lanes") or {}
    try:
        lane = lanes[lane_id]
    except KeyError as exc:
        raise KeyError(f"Unknown tennis lane: {lane_id}") from exc
    if not isinstance(lane, dict):
        raise ValueError(f"Lane entry is not an object: {lane_id}")
    return lane


def lane_overlay(lane_id: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    lane = lane_config(lane_id, config)
    overlay = lane.get("overlay") or {}
    if not isinstance(overlay, dict):
        raise ValueError(f"Lane overlay is not an object: {lane_id}")
    return dict(overlay)


def lane_calibration_path(lane_id: str, config: dict[str, Any] | None = None) -> str | None:
    lane = lane_config(lane_id, config)
    calibration = lane.get("calibration")
    if not isinstance(calibration, dict):
        return None
    path = calibration.get("path")
    return str(path) if path else None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _fixture_value(fixture: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in fixture and fixture[name] not in (None, ""):
            return fixture[name]
    return None


def _matches_filter(fixture_value: Any, allowed: Any) -> bool:
    allowed_values = _as_list(allowed)
    if not allowed_values:
        return True
    return _norm(fixture_value) in {_norm(item) for item in allowed_values}


def lane_for(fixture: dict[str, Any], config: dict[str, Any] | None = None) -> str | None:
    """Return the first configured lane matching a fixture-like dict.

    This is a Phase 0 scaffold helper for future lane work. It intentionally
    avoids clever inference; callers can pass explicit fixture keys such as
    league, surface, series, best_of, and is_doubles.
    """

    cfg = config or load_lane_config()
    lanes = cfg.get("lanes") or {}
    league = _fixture_value(fixture, "league", "tour_level")
    surface = _fixture_value(fixture, "surface")
    series = _fixture_value(fixture, "series", "category")
    best_of = _fixture_value(fixture, "best_of", "bestOf")
    is_doubles = bool(_fixture_value(fixture, "is_doubles", "doubles"))

    for lane_id, lane in lanes.items():
        if not isinstance(lane, dict) or lane.get("state") == "disabled":
            continue
        filters = lane.get("filters") or {}
        if not _matches_filter(league, filters.get("league")):
            continue
        if not _matches_filter(surface, filters.get("surface")):
            continue
        if not _matches_filter(series, filters.get("series")):
            continue
        if filters.get("best_of") and str(best_of) not in {str(item) for item in _as_list(filters.get("best_of"))}:
            continue
        if filters.get("singles_only") and is_doubles:
            continue
        return lane_id
    return None


if __name__ == "__main__":
    cfg = load_lane_config()
    for lane_id in lane_ids(cfg):
        lane = lane_config(lane_id, cfg)
        print(f"{lane_id}: {lane.get('state', 'unknown')}")
