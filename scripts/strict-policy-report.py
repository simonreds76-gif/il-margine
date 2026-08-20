"""
Strict policy report for today's signals.

Default behavior (production mode = base):
- Uses strict policy (Hard|Masters 1000, confidence high, value >= 10% public / 5% internal)
- Optionally appends to data/backtest/strict-signals.csv

Overlay behavior (production mode = overlay):
- Applies tournament side-policy overlay from tournament-segment-roi.csv
  after strict policy/value filtering

Side-by-side tracking:
- Use --compare-overlay to evaluate both base and overlay in one run
- Optionally append comparison rows to a separate CSV (default:
  data/backtest/strict-signals-overlay-compare.csv)

Usage:
  python scripts/strict-policy-report.py
  python scripts/strict-policy-report.py --append
  python scripts/strict-policy-report.py --policy-mode overlay --append
  python scripts/strict-policy-report.py --compare-overlay --append
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from bisect import bisect_left

import requests

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from injury_overlay import env_bool, load_recent_injury_index
from signal_storage import (
    CLAY_BO3_NEARMISS_PATH,
    CHALLENGER_ML_NEARMISS_PATH,
    CPI_SPEED_NEARMISS_PATH,
    GRASS_BO3_NEARMISS_PATH,
    SIGNAL_PROFILE_PATHS,
    SIGNALS_CURRENT_JSON,
    STRICT_INTERNAL_SIGNAL_PATHS,
    STRICT_SIGNAL_PATHS,
    SignalCsvPaths,
    derive_signal_csv_paths,
)
from src.lib.tennis_prob import prob_match_best_of_3


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "backtest"
DEFAULT_OUTPUT = STRICT_SIGNAL_PATHS.live
DEFAULT_INTERNAL_OUTPUT = STRICT_INTERNAL_SIGNAL_PATHS.live
DEFAULT_COMPARE_OUTPUT = DATA_DIR / "strict-signals-overlay-compare.csv"
DEFAULT_CLAY_CALIBRATION_FILE = DATA_DIR / "clay-prob-calibration.json"
DEFAULT_SPREAD_V1_CALIBRATION_FILE = DATA_DIR / "spread-v1-calibration-params.json"
DEFAULT_SPREAD_V1_CLAY_CALIBRATION_FILE = DATA_DIR / "spread-v1-clay-calibration-params.json"
DEFAULT_HARD_CALIBRATION_FILE = DATA_DIR / "calibration-params-2022-2026-review.json"
DEFAULT_SURFACE_SPEED_FILE = DATA_DIR / "tennisabstract-atp-surface-speed.csv"
DEFAULT_CPI_SPEED_GATES_FILE = DATA_DIR / "cpi-regime-shadow-gates.csv"

STRICT_MIN_VALUE_PCT = 10.0  # Public-facing high-conviction signals
INTERNAL_TRACK_MIN_VALUE_PCT = 5.0  # Internal tracking for 200-bet confirmation
HANDICAP_MIN_EDGE_PCT = 20.0  # Handicap signal: model edge vs Pinnacle spread
SPREAD_SHADOW_MIN_EDGE_PCT = 20.0  # Separate shadow lane for handicaps outside current strict match policy


def env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def fetch_rest_paged(base_url: str, table: str, headers: dict[str, str], params: dict[str, Any], *, page_size: int = 1000, timeout: int = 30) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    rest_base = base_url.rstrip("/")
    if not rest_base.endswith("/rest/v1"):
        rest_base = f"{rest_base}/rest/v1"
    while True:
        page_params = {**params, "limit": page_size, "offset": offset}
        response = requests.get(
            f"{rest_base}/{table}",
            headers=headers,
            params=page_params,
            timeout=timeout,
        )
        response.raise_for_status()
        page = response.json() or []
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += len(page)
    return rows


# Spread-v1 is a bounded research lane. The live audit showed weak 5-6% edges
# and huge 20%+ overclaims are both unstable, so keep it inside a controlled
# window unless an explicit research run overrides these envs.
SPREAD_V1_MIN_EDGE_PCT = max(10.0, env_float("SPREAD_V1_MIN_EDGE_PCT", 10.0))
SPREAD_V1_MAX_EDGE_PCT = env_float("SPREAD_V1_MAX_EDGE_PCT", 18.0)
SPREAD_V1_CLAY_FAV_MIN_EDGE_PCT = max(5.0, env_float("SPREAD_V1_CLAY_FAV_MIN_EDGE_PCT", 8.0))
SPREAD_V1_CLAY_FAV_MAX_EDGE_PCT = env_float("SPREAD_V1_CLAY_FAV_MAX_EDGE_PCT", 18.0)
CHALLENGER_ML_ENABLE = env_bool(os.environ.get("CHALLENGER_ML_ENABLE"), False)
CHALLENGER_ML_MIN_EDGE_PCT = env_float("CHALLENGER_ML_MIN_EDGE_PCT", 10.0)
CHALLENGER_ML_MAX_EDGE_PCT = env_float("CHALLENGER_ML_MAX_EDGE_PCT", 15.0)
CHALLENGER_ML_ALLOWED_SURFACES = {"Hard", "Clay", "Grass", "Indoor"}
CHALLENGER_ML_ALLOWED_CONFIDENCE = {"high"}
CHALLENGER_ML_REQUIRE_COVERAGE_TAG = "HIGH"
CLAY_BO3_MIN_EDGE_PCT = env_float("CLAY_BO3_MIN_EDGE_PCT", 5.0)
CLAY_BO3_MAX_EDGE_PCT = env_float("CLAY_BO3_MAX_EDGE_PCT", 13.0)
CLAY_BO3_DOG_HC_MIN_EDGE_PCT = env_float("CLAY_BO3_DOG_HC_MIN_EDGE_PCT", 6.0)
CLAY_BO3_DOG_HC_MAX_EDGE_PCT = env_float("CLAY_BO3_DOG_HC_MAX_EDGE_PCT", 25.0)
CLAY_BO3_ML_ENABLE = env_bool(os.environ.get("CLAY_BO3_ML_ENABLE"), False)
CLAY_BO3_ALLOWED_SERIES = {"ATP250", "ATP500", "Masters 1000", "Masters Cup"}
CLAY_BO3_ALLOWED_CONFIDENCE = {"high"}
GRASS_BO3_MIN_EDGE_PCT = env_float("GRASS_BO3_MIN_EDGE_PCT", 10.0)
GRASS_BO3_MAX_EDGE_PCT = env_float("GRASS_BO3_MAX_EDGE_PCT", 30.0)
GRASS_BO3_ALLOWED_SERIES = {"ATP250", "ATP500"}
GRASS_BO3_ALLOWED_CONFIDENCE = {"high", "medium"}
GRASS_BO3_REQUIRE_FAV_AGREEMENT = env_bool(os.environ.get("GRASS_BO3_REQUIRE_FAV_AGREEMENT"), True)
GRASS_BO3_FAST_CPI_GATE = env_bool(os.environ.get("GRASS_BO3_FAST_CPI_GATE"), True)
GRASS_BO3_SLOW_CPI_MAX = env_float("GRASS_BO3_SLOW_CPI_MAX", 1.05)
GRASS_BO3_FAST_CPI_MIN = env_float("GRASS_BO3_FAST_CPI_MIN", 1.15)
GRASS_BO3_CPI_LAG_YEARS = max(1, env_int("GRASS_BO3_CPI_LAG_YEARS", 3))
GRASS_BO3_CPI_LAG_ONLY = env_bool(os.environ.get("GRASS_BO3_CPI_LAG_ONLY"), True)
CPI_SPEED_MIN_EDGE_PCT = env_float("CPI_SPEED_MIN_EDGE_PCT", 10.0)
CPI_SPEED_MAX_EDGE_PCT = env_float("CPI_SPEED_MAX_EDGE_PCT", 30.0)
CPI_SPEED_CPI_LAG_YEARS = max(1, env_int("CPI_SPEED_CPI_LAG_YEARS", 3))
CPI_SPEED_CPI_LAG_ONLY = env_bool(os.environ.get("CPI_SPEED_CPI_LAG_ONLY"), True)
CPI_SPEED_Z_FAST = env_float("CPI_SPEED_Z_FAST", 0.50)
CPI_SPEED_Z_SLOW = env_float("CPI_SPEED_Z_SLOW", -0.50)
CPI_SPEED_Z_CAP = env_float("CPI_SPEED_Z_CAP", 3.0)
CPI_SPEED_ALLOWED_CONFIDENCE = {"high", "medium"}
CPI_SPEED_ALLOWED_STATUSES = {"PASS_SHADOW"}
CPI_SPEED_REQUIRED_IDENTITY_BASIS = "idclean_v1"
SPREAD_V1_CLAY_FAV_STALE_DAYS = env_int("SPREAD_V1_CLAY_FAV_STALE_DAYS", 14)
ALLOWED_SEGMENT = "Hard|Masters 1000"
ALLOWED_CONFIDENCE = {"high"}
SPREAD_SHADOW_CONFIDENCE = {"high", "medium"}
SPREAD_V1_ENABLE_CLAY = env_bool(os.environ.get("SPREAD_V1_ENABLE_CLAY"), False)
SPREAD_V1_ALLOWED_SURFACES = {"Hard"} | ({"Clay"} if SPREAD_V1_ENABLE_CLAY else set())
SPREAD_V1_EXCLUDED_SERIES = {"Grand Slam"}
SPREAD_V1_CLAY_ALLOWED_SERIES = {"ATP250", "ATP500"}
SPREAD_V1_CLAY_ALLOWED_CONFIDENCE = {"high"}
EXCLUDE_ATP500_HARD_SHORT_FAVORITES = True
EXCLUDE_SHORT_FAV_MAX_ODDS = 1.8
EXCLUDE_SHORT_FAV_CONFIDENCE = {"high"}

# Suppress signals when model and Pinnacle disagree on favourite pricing by >10pp.
# Phantom underdog edges (model 1.15 vs Pin 1.02) cause guaranteed losses.
# Skip matches where model favourite odds < 1.25.
# The model cannot price extreme mismatches â€” both sides are unreliable.
MISPRICE_MODEL_MARKET_FAV_GAP_MAX = 0.10
MISPRICE_MODEL_MARKET_FAV_SIDE_FLIP_BUFFER = 0.03
MISPRICE_MODEL_FAV_ODDS_MIN = 1.25
POINT_PROB_MATCH_PROB_GAP_MAX = 0.08
HEAVY_FAV_DOG_GUARD_MIN_FAV_PROB = 0.74

DEFAULT_OVERLAY_POLICY_FILE = DATA_DIR / "tournament-segment-roi.csv"
DEFAULT_OVERLAY_WINDOW = "prior_editions"
DEFAULT_OVERLAY_FAMILY = "seed"
DEFAULT_OVERLAY_MIN_N = 50
DEFAULT_OVERLAY_MIN_ROI_PCT = -5.0
DEFAULT_OVERLAY_MISSING_MODE = "skip"
DEFAULT_INJURY_CSV = ROOT / "data" / "injured-players-tennisexplorer.csv"
DEFAULT_STRICT_INJURY_LOOKBACK_DAYS = 14

STRICT_UNIT_GBP = float(os.environ.get("STRICT_UNIT_GBP", "100"))
MANDATORY_APPEND_FIELDS = ["stake_units", "stake_gbp", "stake_model", "signal_profile"]
ACTIVE_LIVE_SIGNAL_STATUSES = {"", "pending", "open", "unsettled"}

# Legacy volume profile kept for comparison.
VOLUME_275_RULES: list[dict[str, Any]] = [
    {"surface": "Hard", "series": "Masters 1000", "confidence": {"high"}, "min_value_pct": 15.0},
    {"surface": "Hard", "series": "Masters 1000", "confidence": {"medium"}, "min_value_pct": 30.0},
    {"surface": "Clay", "series": "Masters 1000", "confidence": {"high"}, "min_value_pct": 20.0},
    {"surface": "Hard", "series": "Grand Slam", "confidence": {"high", "medium"}, "min_value_pct": 5.0},
    {"surface": "Grass", "series": "ATP500", "confidence": {"high", "medium"}, "min_value_pct": 10.0},
    {"surface": "Hard", "series": "ATP250", "confidence": {"high", "medium"}, "min_value_pct": 20.0},
]

# Active shadow candidate: ATP main-tour ML expansion only.
VOLUME_200_RULES: list[dict[str, Any]] = [
    {"surface": "Hard", "series": "Masters 1000", "confidence": {"high"}, "min_value_pct": 15.0},
    {"surface": "Hard", "series": "Masters 1000", "confidence": {"medium"}, "min_value_pct": 30.0},
    {"surface": "Hard", "series": "Grand Slam", "confidence": {"high", "medium"}, "min_value_pct": 5.0},
    {"surface": "Hard", "series": "ATP500", "confidence": {"high", "medium"}, "min_value_pct": 10.0},
    {"surface": "Clay", "series": "ATP500", "confidence": {"high", "medium"}, "min_value_pct": 10.0},
    # Grass is split into grass_bo3 so it can carry its own fav-agreement guard
    # and promotion/kill criteria instead of hiding inside volume_200.
]

MATCH_ONLY_SIGNAL_PROFILES = {"volume_200", "challenger_ml_shadow", "grass_bo3", "cpi_speed_shadow"}
SPREAD_V1_SIGNAL_PROFILES = {"spread_v1_shadow", "spread_v1_clay_fav"}
SPREAD_ONLY_SIGNAL_PROFILES = SPREAD_V1_SIGNAL_PROFILES

SHADOW_PROFILE_RULES: dict[str, list[dict[str, Any]]] = {
    "volume_275": VOLUME_275_RULES,
    "volume_200": VOLUME_200_RULES,
}

SHADOW_PROFILE_LABELS: dict[str, str] = {
    "volume_275": "Volume 275 (legacy shadow; includes Clay Masters)",
    "volume_200": "ATP-only ML research lane (main-tour only, no ATP250 shadow expansion, no spreads)",
    "spread_shadow": "Spread shadow (20%+ handicap edges; Clay + non-policy tournaments)",
    "spread_v1_shadow": "Spread v1 shadow (strict-first ATP bo3 hard-only research lane; real-market calibration required)",
    "spread_v1_clay_fav": "Clay favourite handicap shadow (fav HC 2.0-3.5 games, 8-18% edge, clay-only calibration required)",
    "challenger_ml_shadow": "Challenger ML v2 prospective evidence (HIGH coverage, 10-15% edge, zero stake)",
    "clay_bo3": "Clay bo3 internal shadow (ATP clay ML 5-13% edge + dog HC 6-25%)",
    "grass_bo3": "Grass bo3 internal shadow (ATP grass warm-up ML, high/medium, 10-30% edge, favourite agreement)",
    "cpi_speed_shadow": "CPI speed-regime ML shadow (ATP only, passed train/holdout CPI cells, 10-30% edge)",
}
SHADOW_PROFILE_ALLOWED_LEAGUES: dict[str, set[str]] = {
    # Shadow lanes have not held up in Challenger samples; keep production-facing
    # shadow research on main-tour ATP only unless we explicitly revisit it.
    "volume_275": {"ATP"},
    "volume_200": {"ATP"},
    "spread_shadow": {"ATP"},
    "spread_v1_shadow": {"ATP"},
    "spread_v1_clay_fav": {"ATP"},
    "challenger_ml_shadow": {"Challenger"},
    "clay_bo3": {"ATP"},
    "grass_bo3": {"ATP"},
    "cpi_speed_shadow": {"ATP"},
}
HOUSTON_SHADOW_MIN_VALUE_PCT = 20.0
HOUSTON_SHADOW_CONFIDENCE = {"high", "medium"}
CLAY_CALIBRATED_MIN_VALUE_PCT = 5.0
CLAY_CALIBRATED_PROB_MIN = 0.55
CLAY_CALIBRATED_PROB_MAX = 0.65
CLAY_CALIBRATED_CONFIDENCE = {"high"}


def _append_key_value(field: str, value: Any) -> str:
    if field == "policy_mode":
        return str(value or "base").strip().lower()
    if field == "bet_type":
        return str(value or "match").strip().lower()
    if field == "signal_profile":
        return str(value or "strict").strip().lower()
    if field == "spread_line":
        txt = str(value or "").strip()
        if not txt:
            return ""
        try:
            return f"{float(txt):g}"
        except ValueError:
            return txt.lower()
    return str(value or "").strip().lower()


def _clean_fieldnames(fieldnames: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in fieldnames:
        name = str(raw or "").lstrip("\ufeff")
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


SPREAD_LOGICAL_KEY_FIELDS = ["date", "player1", "player2", "bet_type", "side", "policy_mode", "signal_profile"]


def _float_for_rank(value: Any, default: float = float("-inf")) -> float:
    try:
        text = str(value or "").strip()
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def _spread_signal_rank(row: dict[str, Any]) -> tuple[float, float, float]:
    # Keep one handicap quote per player/match/side. Prefer the strongest edge,
    # then the better takeable price, then the later refresh if edge/price tie.
    time_text = str(row.get("time_utc") or "").strip()
    seconds = 0.0
    parts = time_text.split(":")
    if len(parts) == 3:
        try:
            seconds = (int(parts[0]) * 3600) + (int(parts[1]) * 60) + int(float(parts[2]))
        except ValueError:
            seconds = 0.0
    return (
        _float_for_rank(row.get("value_pct")),
        _float_for_rank(row.get("spread_odds")),
        seconds,
    )


def collapse_duplicate_spread_signals(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse alternate handicap lines into one logical signal.

    Pinnacle often exposes +7.5 and +8 (or refreshed odds on the same line) for
    the same player/match. Those are alternate quotes for one research decision,
    not separate bets in the monitor or archive.
    """
    collapsed: list[dict[str, Any]] = []
    spread_index: dict[tuple[str, ...], int] = {}
    for row in rows:
        if (row.get("bet_type") or "match") != "spread":
            collapsed.append(row)
            continue
        key = tuple(_append_key_value(field, row.get(field)) for field in SPREAD_LOGICAL_KEY_FIELDS)
        existing_idx = spread_index.get(key)
        if existing_idx is None:
            spread_index[key] = len(collapsed)
            collapsed.append(row)
            continue
        if _spread_signal_rank(row) > _spread_signal_rank(collapsed[existing_idx]):
            collapsed[existing_idx] = row
    return collapsed


def load_env() -> None:
    for name in [".env.local", "env.local"]:
        path = ROOT / name
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip().replace("\r", "")
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def series_bucket_from_tour(tour_name: str | None, tour_rank: int | None) -> str:
    u = (tour_name or "").upper()
    if any(x in u for x in ["AUSTRALIAN OPEN", "FRENCH OPEN", "ROLAND GARROS", "WIMBLEDON", "US OPEN", "U.S. OPEN", "GRAND SLAM"]):
        return "Grand Slam"
    if "MASTERS CUP" in u or "ATP FINALS" in u or "TOUR FINALS" in u:
        return "Masters Cup"
    if "MASTERS" in u or "1000" in u:
        return "Masters 1000"
    if "ATP 500" in u or "500" in u:
        return "ATP500"
    if "CHALLENGER" in u:
        return "Challenger"
    if "ATP 250" in u or "250" in u:
        return "ATP250"
    if tour_rank in {1, 4}:
        return "Grand Slam"
    if tour_rank == 3:
        return "Masters 1000"
    if tour_rank == 2:
        return "ATP500"
    return "ATP250"


def league_bucket_from_tour(tour_name: str | None, pin_league: str | None = None) -> str:
    league = (pin_league or "").strip()
    if league in {"ATP", "Challenger"}:
        return league
    u = (tour_name or "").upper()
    return "Challenger" if "CHALLENGER" in u else "ATP"


def tour_key(name: str | None) -> str:
    core = (name or "").strip().lower()
    if not core:
        return ""
    core = re.sub(r"\b\d{4}\b", " ", core)
    core = re.sub(r"\b(challenger|qualifiers?|qualifying|qualification|atp|wta)\b", " ", core)
    core = re.sub(r"[^a-z0-9]+", " ", core)
    return " ".join(core.split())


def tour_key_candidates(name: str | None) -> list[str]:
    raw = (name or "").strip().lower()
    if not raw:
        return []
    parts = [p.strip() for p in re.split(r"\s*-\s*", raw) if p.strip()]
    cands: list[str] = []
    # Try full name first.
    cands.append(tour_key(raw))
    # Then commonly useful sub-parts for sponsor/city naming variants.
    if parts:
        cands.append(tour_key(parts[0]))
        cands.append(tour_key(parts[-1]))
    # Optional two-part merges for names like "Foo Open - City".
    if len(parts) >= 2:
        cands.append(tour_key(f"{parts[0]} {parts[-1]}"))
    seen = set()
    out: list[str] = []
    for c in cands:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


GRASS_SPEED_TOUR_ALIASES = {
    "cinch championships": "queen s club",
    "london queens club": "queen s club",
    "queens club championships": "queen s club",
    "queen s club championships": "queen s club",
    "terra wortmann open": "halle",
    "noventi open": "halle",
    "halle open": "halle",
    "b oss open": "stuttgart",
    "boss open": "stuttgart",
    "mercedes cup": "stuttgart",
    "stuttgart open": "stuttgart",
    "libema open": "s hertogenbosch",
    "rosmalen grass court championships": "s hertogenbosch",
    "s hertogenbosch": "s hertogenbosch",
    "hertogenbosch": "s hertogenbosch",
    "eastbourne international": "eastbourne",
    "mallorca championships": "mallorca",
    "hall of fame championships": "newport",
}


def surface_speed_key_candidates(name: str | None) -> list[str]:
    keys = tour_key_candidates(name)
    expanded: list[str] = []
    for key in keys:
        expanded.append(key)
        alias = GRASS_SPEED_TOUR_ALIASES.get(key)
        if alias:
            expanded.append(alias)
        # Sponsor names change often; keep a conservative city-token fallback
        # for the established grass warm-up venues.
        if "queen" in key and "club" in key:
            expanded.append("queen s club")
        if "hertogenbosch" in key or "rosmalen" in key:
            expanded.append("s hertogenbosch")
        for token in ("halle", "stuttgart", "eastbourne", "mallorca", "newport", "wimbledon"):
            if token in key:
                expanded.append(token)
    seen = set()
    out: list[str] = []
    for key in expanded:
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def load_surface_speed_lookup(path: Path) -> dict[tuple[str, str], dict[int, float]]:
    lookup: dict[tuple[str, str], dict[int, float]] = defaultdict(dict)
    if not path.exists():
        return lookup
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            surface = (row.get("surface") or "").strip().title()
            key = tour_key(row.get("tournament_key") or row.get("tournament_name"))
            try:
                year = int(row.get("season_year") or 0)
                cpi = float(row.get("cpi") or row.get("ta_surface_speed") or "")
            except (TypeError, ValueError):
                continue
            if not surface or not key or year <= 0 or not math.isfinite(cpi):
                continue
            lookup[(surface, key)][year] = cpi
    return lookup


def _mean_std(values: list[float]) -> tuple[float, float]:
    clean = [float(v) for v in values if math.isfinite(float(v))]
    if not clean:
        return 0.0, 1.0
    mu = sum(clean) / len(clean)
    if len(clean) < 2:
        return mu, 1.0
    var = sum((v - mu) ** 2 for v in clean) / (len(clean) - 1)
    return mu, max(math.sqrt(var), 1e-9)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def load_surface_speed_context(
    path: Path,
) -> tuple[dict[tuple[int, str, str], float], dict[tuple[int, str], tuple[float, float]], dict[str, tuple[float, float]]]:
    lookup: dict[tuple[int, str, str], float] = {}
    by_year_surface: dict[tuple[int, str], list[float]] = defaultdict(list)
    by_surface: dict[str, list[float]] = defaultdict(list)
    if not path.exists():
        return lookup, {}, {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            surface = (row.get("surface") or "").strip().title()
            if surface == "I.Hard":
                surface = "Hard"
            key = tour_key(row.get("tournament_key") or row.get("tournament_name"))
            try:
                year = int(row.get("season_year") or 0)
                cpi = float(row.get("cpi") or row.get("ta_surface_speed") or "")
            except (TypeError, ValueError):
                continue
            if surface not in {"Hard", "Clay", "Grass"} or not key or year <= 0 or not math.isfinite(cpi):
                continue
            idx = (year, surface, key)
            if idx in lookup:
                continue
            lookup[idx] = cpi
            by_year_surface[(year, surface)].append(cpi)
            by_surface[surface].append(cpi)
    return (
        lookup,
        {key: _mean_std(values) for key, values in by_year_surface.items()},
        {key: _mean_std(values) for key, values in by_surface.items()},
    )


def resolve_surface_speed_z(
    lookup: dict[tuple[int, str, str], float],
    year_surface_stats: dict[tuple[int, str], tuple[float, float]],
    surface_stats: dict[str, tuple[float, float]],
    *,
    surface: str,
    tournament_name: str,
    season_year: int,
    lag_only: bool = True,
    lag_years: int = 3,
    z_cap: float = 3.0,
) -> tuple[float | None, int | None, float, str, str]:
    surface_key = (surface or "").strip().title()
    if surface_key == "I.Hard":
        surface_key = "Hard"
    if surface_key not in {"Hard", "Clay", "Grass"}:
        return None, None, 0.0, "", "unsupported_surface"
    start_yr_back = 1 if lag_only else 0
    for yr_back in range(start_yr_back, max(0, int(lag_years)) + 1):
        year = season_year - yr_back
        for tkey in surface_speed_key_candidates(tournament_name):
            cpi = lookup.get((year, surface_key, tkey))
            if cpi is None:
                continue
            mu, sd = year_surface_stats.get((year, surface_key), surface_stats.get(surface_key, (0.0, 1.0)))
            sd = sd if sd > 1e-9 else 1.0
            z = _clamp((cpi - mu) / sd, -abs(z_cap), abs(z_cap))
            return cpi, year, z, tkey, f"prior_lag_{yr_back}y"
    return None, None, 0.0, "", "missing"


def cpi_speed_bucket(cpi_z: float | None) -> str:
    if cpi_z is None:
        return "missing"
    if cpi_z <= CPI_SPEED_Z_SLOW:
        return "slow"
    if cpi_z >= CPI_SPEED_Z_FAST:
        return "fast"
    return "neutral"


def resolve_surface_speed(
    lookup: dict[tuple[str, str], dict[int, float]],
    *,
    surface: str,
    tournament_name: str,
    season_year: int,
    lag_only: bool = True,
    lag_years: int = 3,
) -> tuple[float | None, int | None, str, str]:
    surface_key = (surface or "").strip().title()
    for tkey in surface_speed_key_candidates(tournament_name):
        years = lookup.get((surface_key, tkey))
        if not years:
            continue
        lagged_years = sorted((y for y in years if y <= season_year - 1), reverse=True)[: max(1, lag_years)]
        if lagged_years:
            value = sum(years[y] for y in lagged_years) / len(lagged_years)
            return value, max(lagged_years), tkey, f"prior_lag_{len(lagged_years)}y"
        if not lag_only and season_year in years:
            return years[season_year], season_year, tkey, "exact"
        prior_years = [y for y in years if y <= season_year]
        if prior_years:
            year = max(prior_years)
            return years[year], year, tkey, "prior"
        if lag_only:
            continue
        year = max(years)
        return years[year], year, tkey, "latest"
    return None, None, "", "missing"


def _safe_prob(p: float) -> float:
    return max(1e-6, min(1.0 - 1e-6, float(p)))


def _parse_point_prob(value: Any) -> float | None:
    try:
        p = float(value)
    except (TypeError, ValueError):
        return None
    if not (0.0 < p < 1.0):
        return None
    return p

def _load_hard_calibration_params(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8").replace("NaN", "null"))
    except Exception:
        return None
    hard = (payload.get("surfaces") or {}).get("Hard") if isinstance(payload, dict) else None
    if not isinstance(hard, dict):
        return None
    try:
        a = float(hard.get("A"))
        b = float(hard.get("B"))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(a) or not math.isfinite(b) or b <= 0:
        return None
    blend_by_series = hard.get("blend_by_series") if isinstance(hard.get("blend_by_series"), dict) else {}
    return {
        "A": a,
        "B": b,
        "blend_by_series": {
            str(k): float(v)
            for k, v in blend_by_series.items()
            if isinstance(k, str) and isinstance(v, (int, float)) and math.isfinite(float(v))
        },
    }


def _logit_prob(p: float) -> float:
    q = _safe_prob(p)
    return math.log(q / (1.0 - q))


def _sigmoid_prob(z: float) -> float:
    z = max(-20.0, min(20.0, float(z)))
    return 1.0 / (1.0 + math.exp(-z))


HARD_OVERLAY_FAVORITE_PROB_CAP: dict[str, dict[str, float]] = {
    "ATP250": {"high": 0.89, "medium": 0.85, "low": 0.82},
    "ATP500": {"high": 0.91, "medium": 0.87, "low": 0.84},
    "Masters 1000": {"high": 0.93, "medium": 0.90, "low": 0.87},
    "Grand Slam": {"high": 0.95, "medium": 0.92, "low": 0.89},
    "Masters Cup": {"high": 0.94, "medium": 0.91, "low": 0.88},
}


def _apply_hard_overlay_guard(p1_win_prob: float, series_bucket: str, confidence: str) -> float:
    caps = HARD_OVERLAY_FAVORITE_PROB_CAP.get(series_bucket)
    if not caps:
        return _safe_prob(p1_win_prob)
    cap = float(caps.get((confidence or "").lower(), 0.90))
    if series_bucket == "ATP500":
        cap -= 0.02
    cap = max(0.78, min(0.93, cap))
    p = _safe_prob(p1_win_prob)
    fav_is_p1 = p >= 0.5
    fav_prob = min(p if fav_is_p1 else 1.0 - p, cap)
    return fav_prob if fav_is_p1 else 1.0 - fav_prob


def _hard_overlay_prob(
    p1_win_prob: float,
    series_bucket: str,
    confidence: str,
    params: dict[str, Any] | None,
) -> float | None:
    if not params:
        return None
    raw = _safe_prob(p1_win_prob)
    fav_is_p1 = raw >= 0.5
    q_raw = raw if fav_is_p1 else 1.0 - raw
    q_cal = _sigmoid_prob(float(params["A"]) + float(params["B"]) * _logit_prob(q_raw))
    blend = max(0.0, min(1.0, float((params.get("blend_by_series") or {}).get(series_bucket, 0.0))))
    q = _safe_prob((1.0 - blend) * q_raw + blend * q_cal)
    p = q if fav_is_p1 else 1.0 - q
    return _apply_hard_overlay_guard(p, series_bucket, confidence)


def _load_piecewise_prob_map(path: Path) -> list[tuple[float, float]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    raw_points = payload.get("favorite_prob_map") if isinstance(payload, dict) else payload
    if not isinstance(raw_points, list):
        return []
    points: list[tuple[float, float]] = []
    last_x = -1.0
    last_y = -1.0
    for item in raw_points:
        try:
            x = _safe_prob(float(item.get("raw_prob")))
            y = _safe_prob(float(item.get("cal_prob")))
        except (AttributeError, TypeError, ValueError):
            continue
        if x < 0.5 or x <= last_x or y < last_y:
            continue
        points.append((x, y))
        last_x = x
        last_y = y
    return points


def _load_spread_v1_calibration_status(path: Path) -> dict[str, Any]:
    status: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "valid": False,
        "reason": "missing" if not path.exists() else "unreadable",
        "line_source_used": "",
        "fit_timestamp": "",
        "usable_scope": {},
        "base_calibration_valid": False,
        "base_calibration_reason": "missing",
        "correction_valid": False,
        "correction_reason": "missing",
    }
    if not path.exists():
        return status
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return status
    if not isinstance(payload, dict):
        status["reason"] = "invalid-payload"
        return status
    line_source = str(payload.get("line_source_used") or "").strip().lower()
    fit_timestamp = str(
        payload.get("correction_fit_timestamp")
        or payload.get("fit_timestamp")
        or payload.get("generated_at")
        or payload.get("fitted_at")
        or payload.get("created_at")
        or ""
    ).strip()
    usable_scope = payload.get("usable_scope")
    if not isinstance(usable_scope, dict):
        status["reason"] = "missing-usable-scope"
        status["line_source_used"] = line_source
        status["fit_timestamp"] = fit_timestamp
        return status

    leagues = {str(item).strip() for item in usable_scope.get("leagues") or [] if str(item).strip()}
    surfaces = {str(item).strip() for item in usable_scope.get("surfaces") or [] if str(item).strip()}
    best_of = str(usable_scope.get("best_of") or "").strip().lower()

    status["line_source_used"] = line_source
    status["fit_timestamp"] = fit_timestamp
    status["usable_scope"] = usable_scope
    status["train_sample_size"] = payload.get("train_sample_size")
    status["test_sample_size"] = payload.get("test_sample_size")
    status["surface_eval"] = payload.get("surface_eval")
    status["base_calibration_valid"] = payload.get("calibration_valid") is not False
    status["base_calibration_reason"] = str(
        payload.get("calibration_reason") or ("ok" if status["base_calibration_valid"] else "invalid-calibration")
    )
    status["correction_valid"] = bool(payload.get("correction_valid"))
    status["correction_reason"] = str(payload.get("correction_reason") or "missing")

    if line_source != "snapshot":
        status["reason"] = f"invalid-line-source:{line_source or 'missing'}"
        return status
    if best_of != "bo3":
        status["reason"] = f"invalid-best-of:{best_of or 'missing'}"
        return status
    if not {"ATP"}.issubset(leagues):
        status["reason"] = "invalid-leagues"
        return status
    if not SPREAD_V1_ALLOWED_SURFACES.issubset(surfaces):
        status["reason"] = "invalid-surfaces"
        return status
    if not status["base_calibration_valid"] and not status["correction_valid"]:
        status["reason"] = f"base:{status['base_calibration_reason']};correction:{status['correction_reason']}"
        return status

    status["valid"] = True
    if status["base_calibration_valid"] and not status["correction_valid"]:
        status["reason"] = "ok-base-only"
        status["warning"] = f"correction:{status['correction_reason']}"
    elif status["base_calibration_valid"]:
        status["reason"] = "ok"
    else:
        status["reason"] = "ok-correction-only"
    if not status["base_calibration_valid"]:
        status["warning"] = f"base-calibration:{status['base_calibration_reason']}"
    return status


def _parse_datetime_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _spread_v1_fit_age_days(status: dict[str, Any]) -> int | None:
    parsed = _parse_datetime_utc(status.get("fit_timestamp"))
    if parsed is None:
        return None
    return max(0, int((datetime.now(timezone.utc) - parsed).total_seconds() // 86400))


def _profile_audit_row(reason: str, signal_profile: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "date": now.date().isoformat(),
        "time_utc": now.strftime("%H:%M:%S"),
        "player1": "",
        "player2": "",
        "surface": "",
        "league": "",
        "series": "",
        "confidence": "",
        "side": "",
        "value_pct": "",
        "bet_type": "audit",
        "policy_mode": "base",
        "signal_profile": signal_profile,
        "threshold_tier": "audit",
        "shadow_reason": "lane_skipped",
        "skip_reason": reason,
        "settlement_status": "void",
    }


def _interp_piecewise(points: list[tuple[float, float]], x: float) -> float:
    if not points:
        return x
    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]
    xs = [pt[0] for pt in points]
    idx = bisect_left(xs, x)
    x0, y0 = points[idx - 1]
    x1, y1 = points[idx]
    if abs(x1 - x0) <= 1e-9:
        return y1
    if abs(y1 - y0) <= 1e-9:
        start = idx - 1
        end = idx
        while start > 0 and abs(points[start - 1][1] - y0) <= 1e-9:
            start -= 1
        while end < len(points) - 1 and abs(points[end + 1][1] - y1) <= 1e-9:
            end += 1
        prev = start - 1 if start > 0 else start
        nxt = end + 1 if end < len(points) - 1 else end
        xa, ya = points[prev]
        xb, yb = points[nxt]
        if abs(xb - xa) <= 1e-9 or abs(yb - ya) <= 1e-9:
            return y0
        t = max(0.0, min(1.0, (x - xa) / (xb - xa)))
        return ya + t * (yb - ya)
    t = (x - x0) / (x1 - x0)
    return y0 + t * (y1 - y0)


def _apply_piecewise_favorite_remap(p: float, points: list[tuple[float, float]]) -> float:
    p = _safe_prob(p)
    fav_is_p1 = p >= 0.5
    q = p if fav_is_p1 else (1.0 - p)
    q_cal = _safe_prob(_interp_piecewise(points, q))
    return q_cal if fav_is_p1 else (1.0 - q_cal)


def norm_name(s: str | None) -> str:
    return (s or "").strip().lower().replace(".", "").replace("-", " ").replace(",", " ")


def tokenize(s: str | None) -> list[str]:
    return [x for x in norm_name(s).split() if len(x) > 1]


def _norm_pinnacle_name(s: str) -> str:
    if not s:
        return ""
    t = (s or "").strip().lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = t.replace("-", "").replace("'", "")
    return t


def _tokenise_pinnacle_name(name: str) -> list[str]:
    cleaned = (name or "").replace(",", " ").replace("-", " ")
    cleaned = re.sub(r"\s*\([^)]*\)", " ", cleaned)
    cleaned = re.sub(r"\s*\[[^\]]*\]", " ", cleaned)
    return [
        _norm_pinnacle_name(t)
        for t in cleaned.split()
        if t and not re.match(r"^[a-z]$", _norm_pinnacle_name(t))
    ]


def _surname_keys(name: str) -> list[str]:
    t = _tokenise_pinnacle_name(name)
    if not t:
        return []
    out = set()
    n = len(t)
    out.add(t[n - 1])
    if n >= 2:
        out.add(t[n - 2])
        out.add(f"{t[n - 2]} {t[n - 1]}")
        out.add(f"{t[n - 2]}{t[n - 1]}")
    return list(out)


def _make_pair_keys(a: str, b: str) -> list[str]:
    a_keys = _surname_keys(a)
    b_keys = _surname_keys(b)
    out = set()
    for ka in a_keys:
        for kb in b_keys:
            out.add(f"{ka}|{kb}")
    return list(out)


def _first_word(name: str) -> str:
    t = _tokenise_pinnacle_name(name)
    return t[0] if t else ""


def _full_name(name: str) -> str:
    return " ".join(_tokenise_pinnacle_name(name))


def _is_doubles_name(name: str | None) -> bool:
    return "/" in (name or "") or "&" in (name or "")


def match_pinnacle_rows(
    fair_rows: list[dict[str, Any]],
    pin_rows: list[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    pin_lookup: dict[str, list[tuple[dict[str, Any], bool]]] = {}
    for pin in pin_rows:
        p1 = (pin.get("player1_name") or "").strip()
        p2 = (pin.get("player2_name") or "").strip()
        if _is_doubles_name(p1) or _is_doubles_name(p2):
            continue
        for key in _make_pair_keys(p1, p2):
            pin_lookup.setdefault(key, []).append((pin, False))
        for key in _make_pair_keys(p2, p1):
            pin_lookup.setdefault(key, []).append((pin, True))

    matched: dict[int, dict[str, Any]] = {}
    used_pin_keys: set[tuple[str, str]] = set()

    for fo in fair_rows:
        fo_id = fo.get("id")
        if fo_id is None:
            continue
        p1 = (fo.get("p1_name") or "").strip()
        p2 = (fo.get("p2_name") or "").strip()
        if _is_doubles_name(p1) or _is_doubles_name(p2):
            continue

        candidate_map: dict[str, tuple[dict[str, Any], bool, int]] = {}
        for key in _make_pair_keys(p1, p2):
            for pin, reversed_for_fair in pin_lookup.get(key, []):
                ident = f"{pin.get('player1_name','')}|{pin.get('player2_name','')}|{'R' if reversed_for_fair else 'N'}"
                if ident in candidate_map:
                    existing = candidate_map[ident]
                    candidate_map[ident] = (existing[0], existing[1], existing[2] + 1)
                else:
                    candidate_map[ident] = (pin, reversed_for_fair, 1)

        if not candidate_map:
            continue

        fo_p1_first = _first_word(p1)
        fo_p2_first = _first_word(p2)
        fo_p1_full = _full_name(p1)
        fo_p2_full = _full_name(p2)

        for ident, (pin, reversed_for_fair, score) in list(candidate_map.items()):
            pin_p1 = (pin.get("player2_name") if reversed_for_fair else pin.get("player1_name")) or ""
            pin_p2 = (pin.get("player1_name") if reversed_for_fair else pin.get("player2_name")) or ""
            if fo_p1_first and fo_p1_first == _first_word(pin_p1):
                score += 2
            if fo_p2_first and fo_p2_first == _first_word(pin_p2):
                score += 2
            if fo_p1_full and fo_p1_full == _full_name(pin_p1):
                score += 4
            if fo_p2_full and fo_p2_full == _full_name(pin_p2):
                score += 4
            candidate_map[ident] = (pin, reversed_for_fair, score)

        ranked = [
            (pin, reversed_for_fair, score)
            for (pin, reversed_for_fair, score) in sorted(candidate_map.values(), key=lambda x: -x[2])
            if ((pin.get("player1_name") or ""), (pin.get("player2_name") or "")) not in used_pin_keys
        ]
        if not ranked:
            continue
        if len(ranked) > 1 and ranked[0][2] == ranked[1][2]:
            continue

        pin, reversed_for_fair, _ = ranked[0]
        used_pin_keys.add(((pin.get("player1_name") or ""), (pin.get("player2_name") or "")))
        o1 = pin.get("odds1")
        o2 = pin.get("odds2")
        if o1 is None or o2 is None:
            continue
        matched[int(fo_id)] = (
            {"odds1": float(o2), "odds2": float(o1), "league": (pin.get("league") or "").strip()}
            if reversed_for_fair
            else {"odds1": float(o1), "odds2": float(o2), "league": (pin.get("league") or "").strip()}
        )

    return matched


def load_local_pinnacle_snapshot(snapshot_date: str) -> list[dict[str, Any]]:
    """Load the latest local capture for each same-day Pinnacle pairing.

    The fair-odds API already merges these files with the database snapshot.
    Signal generation must use the same source or it silently misses matches
    captured after the morning database snapshot.
    """
    history_dir = ROOT / "data" / "pinnacle-history"
    token = snapshot_date.replace("-", "")
    latest: dict[tuple[str, str, str], tuple[str, dict[str, Any]]] = {}
    for csv_path in sorted(history_dir.glob(f"pinnacle-history-{token}-*.csv")):
        try:
            with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    if str(row.get("bookmaker") or "").strip().lower() != "pinnacle":
                        continue
                    league = str(row.get("league") or "").strip()
                    if league not in {"ATP", "Challenger"}:
                        continue
                    p1 = str(row.get("player1_name") or "").strip()
                    p2 = str(row.get("player2_name") or "").strip()
                    if not p1 or not p2 or _is_doubles_name(p1) or _is_doubles_name(p2):
                        continue
                    try:
                        odds1 = float(row.get("odds1") or 0)
                        odds2 = float(row.get("odds2") or 0)
                    except (TypeError, ValueError):
                        continue
                    if odds1 <= 1 or odds2 <= 1:
                        continue
                    pair_key = tuple(sorted((_full_name(p1), _full_name(p2)))) + (league,)
                    captured_at = str(row.get("captured_at") or "")
                    candidate = {
                        "player1_name": p1,
                        "player2_name": p2,
                        "odds1": odds1,
                        "odds2": odds2,
                        "league": league,
                    }
                    current = latest.get(pair_key)
                    if current is None or captured_at >= current[0]:
                        latest[pair_key] = (captured_at, candidate)
        except (OSError, csv.Error):
            continue
    return [item[1] for item in latest.values()]


def allow_hard_masters_side_flip(
    *,
    detected: bool,
    league: str,
    surface: str,
    series_bucket: str,
    confidence: str,
    model_market_fav_gap: float,
) -> bool:
    """Allow only the registered strict Hard/Masters/high side-flip cohort."""
    return (
        detected
        and league == "ATP"
        and surface == "Hard"
        and series_bucket == "Masters 1000"
        and confidence == "high"
        and model_market_fav_gap <= MISPRICE_MODEL_MARKET_FAV_GAP_MAX
    )


def is_excluded_short_favorite(surface: str, series_bucket: str, confidence: str, our_odds1: float, our_odds2: float) -> bool:
    if not EXCLUDE_ATP500_HARD_SHORT_FAVORITES:
        return False
    if surface != "Hard" or series_bucket != "ATP500":
        return False
    if confidence not in EXCLUDE_SHORT_FAV_CONFIDENCE:
        return False
    return min(our_odds1, our_odds2) < EXCLUDE_SHORT_FAV_MAX_ODDS


def is_excluded_heavy_favorite_dog(
    surface: str,
    series_bucket: str,
    favorite_prob: float,
    side: str,
    favorite_side: str,
) -> bool:
    if surface != "Hard" or series_bucket != "Masters 1000":
        return False
    if side == favorite_side:
        return False
    return float(favorite_prob or 0.0) >= HEAVY_FAV_DOG_GUARD_MIN_FAV_PROB


def is_short_favorite_dog_spread_guarded(side: str, spread_line: float | None, model_ml_excluded: bool, pin_ml_excluded: bool) -> bool:
    if not model_ml_excluded and not pin_ml_excluded:
        return False
    if spread_line is None:
        return False
    # P1+ uses the stored line as displayed; P2- is the opposite side. When
    # ML is extremely short, dog-side plus-games edges are usually the same
    # favourite-compression bug that creates bad dog ML value.
    if side == "P1+":
        return spread_line > 0
    if side == "P2-":
        return spread_line < 0
    return False


def is_spread_v1_segment_guarded(side: str, spread_line: float | None) -> bool:
    if spread_line is None:
        return False
    display_line = spread_line if side == "P1+" else -spread_line if side == "P2-" else spread_line
    # Live segment audit 2026-04-24: favorite-side handicaps are carrying the
    # spread-v1 record, while dog/scratch, sub-2-game, and very wide lines leak.
    if display_line >= 0:
        return True
    return abs(display_line) < 2.0 or abs(display_line) > 3.5


def has_favorite_spread_conflict(
    favorite_side: str,
    spread_line: float | None,
    handicap_edge_p1: float | None,
    handicap_edge_p2: float | None,
) -> bool:
    if spread_line is None or handicap_edge_p1 is None or handicap_edge_p2 is None:
        return False
    if favorite_side == "P1":
        return spread_line < 0 and handicap_edge_p1 >= HANDICAP_MIN_EDGE_PCT
    return spread_line > 0 and handicap_edge_p2 >= HANDICAP_MIN_EDGE_PCT


def strict_min_value_for(surface: str, series_bucket: str, confidence: str) -> float | None:
    segment_key = f"{surface}|{series_bucket}"
    if segment_key != ALLOWED_SEGMENT:
        return None
    if confidence not in ALLOWED_CONFIDENCE:
        return None
    return INTERNAL_TRACK_MIN_VALUE_PCT


def shadow_profile_min_value_for(
    profile_name: str,
    surface: str,
    series_bucket: str,
    confidence: str,
    tournament_name: str = "",
) -> float | None:
    vals: list[float] = []
    if (
        profile_name in {"volume_275", "volume_200"}
        and is_houston_clay_shadow_exception(surface, tournament_name)
        and confidence in HOUSTON_SHADOW_CONFIDENCE
    ):
        vals.append(HOUSTON_SHADOW_MIN_VALUE_PCT)
    for rule in SHADOW_PROFILE_RULES.get(profile_name, []):
        if surface != rule["surface"] or series_bucket != rule["series"]:
            continue
        if confidence not in rule["confidence"]:
            continue
        vals.append(float(rule["min_value_pct"]))
    if not vals:
        return None
    return min(vals)


def spread_shadow_reason_for(surface: str, series_bucket: str, confidence: str, tournament_name: str = "") -> str | None:
    conf = (confidence or "").strip().lower()
    if conf not in SPREAD_SHADOW_CONFIDENCE:
        return None
    if is_houston_clay_shadow_exception(surface, tournament_name):
        return None

    in_strict_match_segment = strict_min_value_for(surface, series_bucket, conf) is not None
    is_clay = surface == "Clay"
    if is_clay and not in_strict_match_segment:
        return "clay_non_policy"
    if is_clay:
        return "clay"
    if not in_strict_match_segment:
        return "non_policy"
    return None


def spread_v1_scope_reason(surface: str, series_bucket: str, league: str, confidence: str) -> str | None:
    if league != "ATP":
        return "league"
    if surface not in SPREAD_V1_ALLOWED_SURFACES:
        return "surface"
    if series_bucket in SPREAD_V1_EXCLUDED_SERIES:
        return "best_of_five"
    if surface == "Clay":
        if series_bucket not in SPREAD_V1_CLAY_ALLOWED_SERIES:
            return "clay_series"
        if (confidence or "").strip().lower() not in SPREAD_V1_CLAY_ALLOWED_CONFIDENCE:
            return "clay_confidence"
    return None


def spread_v1_clay_fav_scope_reason(surface: str, series_bucket: str, league: str, confidence: str) -> str | None:
    if league != "ATP":
        return "league"
    if surface != "Clay":
        return "surface"
    if series_bucket in SPREAD_V1_EXCLUDED_SERIES:
        return "best_of_five"
    if (confidence or "").strip().lower() not in SPREAD_V1_CLAY_ALLOWED_CONFIDENCE:
        return "clay_confidence"
    return None


def clay_bo3_scope_reason(surface: str, series_bucket: str, league: str, confidence: str) -> str | None:
    if league != "ATP":
        return "league"
    if surface != "Clay":
        return "surface"
    if series_bucket == "Grand Slam":
        return "best_of_five"
    if series_bucket not in CLAY_BO3_ALLOWED_SERIES:
        return "series_blocked"
    if (confidence or "").strip().lower() not in CLAY_BO3_ALLOWED_CONFIDENCE:
        return "confidence_low"
    return None


def grass_bo3_scope_reason(surface: str, series_bucket: str, league: str, confidence: str) -> str | None:
    if league != "ATP":
        return "league"
    if surface != "Grass":
        return "surface"
    if series_bucket == "Grand Slam":
        return "best_of_five"
    if series_bucket not in GRASS_BO3_ALLOWED_SERIES:
        return "series_blocked"
    if (confidence or "").strip().lower() not in GRASS_BO3_ALLOWED_CONFIDENCE:
        return "confidence_low"
    return None


def shadow_profile_league_allowed(profile_name: str, league: str) -> bool:
    allowed = SHADOW_PROFILE_ALLOWED_LEAGUES.get(profile_name)
    if not allowed:
        return True
    return league in allowed


def load_cpi_speed_pass_gates(path: Path) -> set[tuple[str, str]]:
    gates: set[tuple[str, str]] = set()
    if not path.exists():
        return gates
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                status = (row.get("status") or "").strip()
                identity_basis = (row.get("identity_basis") or "").strip()
                segment = (row.get("segment") or "").strip()
                value = (row.get("value") or "").strip()
                if (
                    status in CPI_SPEED_ALLOWED_STATUSES
                    and identity_basis == CPI_SPEED_REQUIRED_IDENTITY_BASIS
                    and segment
                    and value
                ):
                    gates.add((segment, value))
    except Exception:
        return set()
    return gates


def cpi_speed_model_surface(cpi_bucket: str) -> str:
    return {
        "slow": "SpeedSlow",
        "neutral": "SpeedNeutral",
        "fast": "SpeedFast",
    }.get(cpi_bucket, "")


def cpi_speed_value_band(value_pct: float | None) -> str:
    value = float(value_pct or 0.0)
    if value >= 25:
        return "25+"
    if value >= 15:
        return "15-25"
    if value >= 10:
        return "10-15"
    if value >= 5:
        return "5-10"
    return "<5"


def cpi_speed_segments(
    *,
    surface: str,
    cpi_bucket: str,
    confidence: str,
    series_bucket: str,
    value_pct: float | None,
    model_favorite_side: str,
    pin_favorite_side: str,
) -> list[tuple[str, str]]:
    model_surface = cpi_speed_model_surface(cpi_bucket)
    if not model_surface:
        return []
    conf = (confidence or "unknown").strip().lower() or "unknown"
    alignment = "same_fav" if model_favorite_side == pin_favorite_side else "side_flip"
    surface_cpi = f"{surface}:{cpi_bucket}"
    value_band = cpi_speed_value_band(value_pct)
    return [
        ("model_surface", model_surface),
        ("surface_cpi_bucket", surface_cpi),
        ("model_surface_confidence", f"{model_surface}:{conf}"),
        ("surface_cpi_bucket_confidence", f"{surface_cpi}:{conf}"),
        ("model_surface_alignment", f"{model_surface}:{alignment}"),
        ("surface_cpi_bucket_alignment", f"{surface_cpi}:{alignment}"),
        ("model_surface_value_band", f"{model_surface}:{value_band}"),
        ("surface_cpi_bucket_value_band", f"{surface_cpi}:{value_band}"),
        ("model_surface_series", f"{model_surface}:{series_bucket}"),
    ]


def cpi_speed_gate_match(
    gates: set[tuple[str, str]],
    *,
    surface: str,
    cpi_bucket: str,
    confidence: str,
    series_bucket: str,
    value_pct: float | None,
    model_favorite_side: str,
    pin_favorite_side: str,
) -> tuple[bool, str, list[str]]:
    segments = cpi_speed_segments(
        surface=surface,
        cpi_bucket=cpi_bucket,
        confidence=confidence,
        series_bucket=series_bucket,
        value_pct=value_pct,
        model_favorite_side=model_favorite_side,
        pin_favorite_side=pin_favorite_side,
    )
    labels = [f"{segment}={value}" for segment, value in segments]
    for segment, value in segments:
        if (segment, value) in gates:
            return True, f"{segment}={value}", labels
    return False, "", labels


def compute_stake_units(
    *,
    our_odds1: float,
    our_odds2: float,
    pin_odds1: float,
    pin_odds2: float,
    side: str,
    bet_type: str,
    value_pct: float | None = None,
) -> tuple[float, float, str]:
    """
    Compute stake units and GBP amount.
    - Match bets: flat 1u.
    - Spread bets: flat 2u.
    """
    if (bet_type or "").strip().lower() == "spread":
        return 2.0, 2.0 * STRICT_UNIT_GBP, "flat_spread"

    return 1.0, 1.0 * STRICT_UNIT_GBP, "flat_match"


def apply_profile_stake_policy(
    signal_profile: str,
    stake_units: float,
    stake_gbp: float,
    stake_model: str,
) -> tuple[float, float, str]:
    """Force research-only cohorts to remain non-actionable."""
    if signal_profile == "challenger_ml_shadow":
        return 0.0, 0.0, "prospective_evidence_no_stake"
    return stake_units, stake_gbp, stake_model


def format_signed_line(v: float | None) -> str:
    if v is None:
        return "â€”"
    abs_v = abs(v)
    body = str(int(abs_v)) if float(abs_v).is_integer() else f"{abs_v:.1f}"
    return f"{'+' if v >= 0 else '-'}{body}"


def load_overlay_policy(
    policy_path: Path,
    window_type: str,
    segment_family: str,
) -> tuple[dict[tuple[int, str, str], dict[str, float]], dict[tuple[str, str], list[int]]]:
    if not policy_path.exists():
        return {}, {}
    with policy_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {}, {}
    req = {"tournament_key", "window_type", "target_season_year", "bet_side", "segment_family", "n", "roi_pct_shrunk"}
    if not req.issubset(set(rows[0].keys())):
        return {}, {}

    agg: dict[tuple[int, str, str], dict[str, float]] = defaultdict(lambda: {"w_roi": 0.0, "w_n": 0.0})
    years_by_key_side: dict[tuple[str, str], set[int]] = defaultdict(set)
    for r in rows:
        if (r.get("window_type") or "") != window_type:
            continue
        if (r.get("segment_family") or "") != segment_family:
            continue
        ts = (r.get("target_season_year") or "").strip()
        tkey = (r.get("tournament_key") or "").strip()
        bside = (r.get("bet_side") or "").strip()
        if not ts or not tkey or bside not in {"fav", "dog"}:
            continue
        try:
            year = int(ts)
            n = float(r.get("n") or 0.0)
            roi = float(r.get("roi_pct_shrunk") or 0.0)
        except ValueError:
            continue
        if n <= 0:
            continue
        k = (year, tkey, bside)
        agg[k]["w_roi"] += roi * n
        agg[k]["w_n"] += n
        years_by_key_side[(tkey, bside)].add(year)

    out: dict[tuple[int, str, str], dict[str, float]] = {}
    for k, v in agg.items():
        if v["w_n"] <= 0:
            continue
        out[k] = {"n": v["w_n"], "roi_pct_shrunk": v["w_roi"] / v["w_n"]}
    years_sorted = {k: sorted(v) for k, v in years_by_key_side.items() if v}
    return out, years_sorted


def resolve_overlay_policy(
    season_year: int,
    tournament_name: str,
    bet_side: str,
    overlay_lookup: dict[tuple[int, str, str], dict[str, float]],
    overlay_years: dict[tuple[str, str], list[int]],
) -> tuple[dict[str, float] | None, str, int | None, str]:
    cands = tour_key_candidates(tournament_name)
    if not cands:
        return None, "", None, "missing"

    # Exact season-year match first.
    for tkey in cands:
        pol = overlay_lookup.get((season_year, tkey, bet_side))
        if pol is not None:
            return pol, tkey, season_year, "exact"

    # Fallback: latest available <= season_year, else latest available.
    for tkey in cands:
        years = overlay_years.get((tkey, bet_side), [])
        if not years:
            continue
        prior = [y for y in years if y <= season_year]
        resolved_year = max(prior) if prior else max(years)
        pol = overlay_lookup.get((resolved_year, tkey, bet_side))
        if pol is not None:
            return pol, tkey, resolved_year, "fallback_year"

    return None, cands[0], None, "missing"


def is_houston_clay_shadow_exception(surface: str, tournament_name: str) -> bool:
    if surface != "Clay":
        return False
    return "houston" in tour_key_candidates(tournament_name)


def _int_or_blank(value: Any) -> int | str:
    try:
        if value in ("", None):
            return ""
        return int(float(value))
    except (TypeError, ValueError):
        return ""


def challenger_coverage_fields(row: dict[str, Any], tour_name: str, tour_id: Any) -> dict[str, Any]:
    return {
        "tour_id": tour_id if tour_id is not None else "",
        "tour_name": tour_name,
        "challenger_event": True,
        "data_coverage_tag": str(row.get("data_coverage_tag") or "").strip().upper(),
        "match_count_12m_p1": _int_or_blank(row.get("match_count_12m_p1")),
        "match_count_12m_p2": _int_or_blank(row.get("match_count_12m_p2")),
        "matches_total_p1": _int_or_blank(row.get("matches_total_p1")),
        "matches_total_p2": _int_or_blank(row.get("matches_total_p2")),
        "recent_challenger_plus_p1": _int_or_blank(row.get("recent_challenger_plus_p1")),
        "recent_challenger_plus_p2": _int_or_blank(row.get("recent_challenger_plus_p2")),
        "last_match_days_p1": _int_or_blank(row.get("last_match_days_p1")),
        "last_match_days_p2": _int_or_blank(row.get("last_match_days_p2")),
    }


def challenger_skip_reason(
    *,
    coverage_tag: str,
    confidence: str,
    surface: str,
    value_pct: float | None,
    model_ml_excluded: bool,
    pin_ml_excluded: bool,
    model_market_gap_excluded: bool,
    atp500_short_favorite_ml_excluded: bool,
) -> str | None:
    if surface not in CHALLENGER_ML_ALLOWED_SURFACES:
        return "surface_blocked"
    if coverage_tag != CHALLENGER_ML_REQUIRE_COVERAGE_TAG:
        return "coverage_thin"
    if confidence not in CHALLENGER_ML_ALLOWED_CONFIDENCE:
        return "confidence_low"
    if model_market_gap_excluded:
        return "model_market_gap"
    if model_ml_excluded:
        return "model_ml_excluded"
    if pin_ml_excluded:
        return "pin_ml_excluded"
    if atp500_short_favorite_ml_excluded:
        return "short_favorite_ml_excluded"
    if value_pct is None:
        return "edge_missing"
    if value_pct < CHALLENGER_ML_MIN_EDGE_PCT:
        return "edge_below_floor"
    if value_pct > CHALLENGER_ML_MAX_EDGE_PCT:
        return "edge_above_cap"
    return None


def clay_bo3_skip_reason(
    *,
    ml_enabled: bool,
    scope_reason: str | None,
    value_pct: float | None,
    model_ml_excluded: bool,
    pin_ml_excluded: bool,
    model_market_gap_excluded: bool,
    atp500_short_favorite_ml_excluded: bool,
    heavy_favorite_dog_excluded: bool,
) -> str | None:
    if scope_reason:
        return scope_reason
    if not ml_enabled:
        return "ml_disabled_backtest_failed"
    if model_market_gap_excluded:
        return "model_market_gap"
    if model_ml_excluded:
        return "model_ml_excluded"
    if pin_ml_excluded:
        return "pin_ml_excluded"
    if atp500_short_favorite_ml_excluded:
        return "short_favorite_ml_excluded"
    if heavy_favorite_dog_excluded:
        return "heavy_favorite_dog_excluded"
    if value_pct is None:
        return "edge_missing"
    if value_pct < CLAY_BO3_MIN_EDGE_PCT:
        return "edge_below_floor"
    if value_pct > CLAY_BO3_MAX_EDGE_PCT:
        return "edge_above_cap"
    return None


def grass_bo3_skip_reason(
    *,
    scope_reason: str | None,
    speed_reason: str | None,
    value_pct: float | None,
    model_ml_excluded: bool,
    pin_ml_excluded: bool,
    model_market_gap_excluded: bool,
    atp500_short_favorite_ml_excluded: bool,
    heavy_favorite_dog_excluded: bool,
    favorite_agreement: bool,
) -> str | None:
    if scope_reason:
        return scope_reason
    if speed_reason:
        return speed_reason
    if GRASS_BO3_REQUIRE_FAV_AGREEMENT and not favorite_agreement:
        return "favorite_disagreement"
    if model_market_gap_excluded:
        return "model_market_gap"
    if model_ml_excluded:
        return "model_ml_excluded"
    if pin_ml_excluded:
        return "pin_ml_excluded"
    if atp500_short_favorite_ml_excluded:
        return "short_favorite_ml_excluded"
    if heavy_favorite_dog_excluded:
        return "heavy_favorite_dog_excluded"
    if value_pct is None:
        return "edge_missing"
    if value_pct < GRASS_BO3_MIN_EDGE_PCT:
        return "edge_below_floor"
    if value_pct > GRASS_BO3_MAX_EDGE_PCT:
        return "edge_above_cap"
    return None


def append_rows_dedup(path: Path, rows: list[dict[str, Any]], key_fields: list[str]) -> int:
    # spread_shadow (and similar) often appends 0/0 until a qualifying 20%+ handicap exists.
    # Old behavior: skip writing â†’ file never created â†’ settle-strict-signals.py and
    # strict-policy-performance.py report "file not found" forever. Seed header-only CSV.
    if not path.exists() and not rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames: list[str] = []
        if DEFAULT_OUTPUT.exists():
            with DEFAULT_OUTPUT.open("r", encoding="utf-8-sig", newline="") as f:
                fieldnames = _clean_fieldnames(list(csv.DictReader(f).fieldnames or []))
        for k in MANDATORY_APPEND_FIELDS:
            if k not in fieldnames:
                fieldnames.append(k)
        if not fieldnames:
            fieldnames = [
                "date",
                "time_utc",
                "player1",
                "player2",
                "surface",
                "series",
                "confidence",
                "side",
                "value_pct",
                "bet_type",
                "spread_line",
                "spread_odds",
                "policy_mode",
                "signal_profile",
                "shadow_reason",
                "settlement_status",
            ]
        with path.open("w", encoding="utf-8", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=fieldnames)
            wr.writeheader()
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_by_key: dict[tuple[str, ...], dict[str, str]] = {}
    existing_fields: list[str] = []
    if path.exists():
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            rd = csv.DictReader(f)
            existing_fields = _clean_fieldnames(list(rd.fieldnames or []))
            for r in rd:
                row = dict(r)
                key = tuple(_append_key_value(k, row.get(k)) for k in key_fields)
                existing = existing_by_key.get(key)
                if existing is not None:
                    for k, v in row.items():
                        if (existing.get(k, "") == "") and v not in ("", None):
                            existing[k] = v
                    continue
                existing_by_key[key] = row

    out_rows = list(existing_by_key.values())
    added = 0
    for r in rows:
        key = tuple(_append_key_value(k, r.get(k)) for k in key_fields)
        normalized = {k: ("" if v is None else str(v)) for k, v in r.items()}
        normalized.setdefault("settlement_status", "pending")
        if normalized.get("settlement_status") == "":
            normalized["settlement_status"] = "pending"
        if key in existing_by_key:
            existing = existing_by_key[key]
            for k, v in normalized.items():
                if (k not in existing or existing.get(k, "") == "") and v != "":
                    existing[k] = v
            continue
        existing_by_key[key] = normalized
        out_rows.append(normalized)
        added += 1

    fieldnames = list(existing_fields)
    for r in rows:
        for k in r.keys():
            if k not in fieldnames:
                fieldnames.append(k)
    for r in out_rows:
        for k in r.keys():
            if k not in fieldnames:
                fieldnames.append(k)
    for k in MANDATORY_APPEND_FIELDS:
        if k not in fieldnames:
            fieldnames.append(k)
    if not fieldnames and rows:
        fieldnames = list(rows[0].keys())
    fieldnames = _clean_fieldnames(fieldnames)

    with path.open("w", encoding="utf-8", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=fieldnames)
        wr.writeheader()
        wr.writerows(out_rows)
    return added


def write_live_snapshot(
    path: Path,
    rows: list[dict[str, Any]],
    dedup_key_fields: list[str],
    lane_key_fields: list[str],
) -> int:
    # Live signal files drive the monitor/current board. Keep them as a fresh
    # recalculation snapshot only; the archive remains the append-only queue for
    # settlement and CLV. Otherwise stale pending rows look like today's picks.
    existing_fields: list[str] = []

    def absorb_existing_fields(source_path: Path) -> None:
        nonlocal existing_fields
        if not source_path.exists():
            return
        with source_path.open("r", encoding="utf-8-sig", newline="") as f:
            rd = csv.DictReader(f)
            for field in _clean_fieldnames(list(rd.fieldnames or [])):
                if field not in existing_fields:
                    existing_fields.append(field)

    archive_path = derive_signal_csv_paths(path).archive
    if archive_path != path:
        absorb_existing_fields(archive_path)
    absorb_existing_fields(path)

    incoming_rows_by_lane: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        lane_key = tuple(_append_key_value(k, row.get(k)) for k in lane_key_fields)
        normalized = {k: ("" if v is None else str(v)) for k, v in row.items()}
        normalized.setdefault("settlement_status", "pending")
        if normalized.get("settlement_status") == "":
            normalized["settlement_status"] = "pending"
        incoming_rows_by_lane[lane_key] = normalized

    ordered_rows: list[dict[str, str]] = []
    seen_keys: dict[tuple[str, ...], int] = {}
    for row in incoming_rows_by_lane.values():
        key = tuple(_append_key_value(k, row.get(k)) for k in dedup_key_fields)
        if key in seen_keys:
            ordered_rows[seen_keys[key]] = row
            continue
        seen_keys[key] = len(ordered_rows)
        ordered_rows.append(row)

    fieldnames = list(existing_fields)
    for row in ordered_rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    for key in MANDATORY_APPEND_FIELDS:
        if key not in fieldnames:
            fieldnames.append(key)
    if not fieldnames:
        fieldnames = [
            "date",
            "time_utc",
            "player1",
            "player2",
            "surface",
            "series",
            "confidence",
            "side",
            "value_pct",
            "bet_type",
            "spread_line",
            "spread_odds",
            "policy_mode",
            "signal_profile",
            "shadow_reason",
            "settlement_status",
        ]
    fieldnames = _clean_fieldnames(fieldnames)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=fieldnames)
        wr.writeheader()
        wr.writerows(ordered_rows)

    return len(ordered_rows)


def mirror_live_snapshot(paths: SignalCsvPaths) -> None:
    if paths.legacy == paths.live:
        return
    paths.legacy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(paths.live, paths.legacy)


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def write_signals_current_artifact() -> None:
    payload: dict[str, Any] = {
        "generated_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "profiles": {},
        "signals": [],
    }
    for profile, (public_paths, _) in SIGNAL_PROFILE_PATHS.items():
        live_rows = _load_csv_rows(public_paths.live)
        payload["profiles"][profile] = {
            "live_file": str(public_paths.live.relative_to(ROOT)),
            "legacy_file": str(public_paths.legacy.relative_to(ROOT)),
            "archive_file": str(public_paths.archive.relative_to(ROOT)),
            "row_count": len(live_rows),
        }
        for row in live_rows:
            payload["signals"].append(
                {
                    "date": row.get("date", ""),
                    "time_utc": row.get("time_utc", ""),
                    "player1": row.get("player1", ""),
                    "player2": row.get("player2", ""),
                    "side": row.get("side", ""),
                    "bet_type": row.get("bet_type") or "match",
                    "spread_line": row.get("spread_line", ""),
                    "value_pct": row.get("value_pct", ""),
                    "signal_profile": row.get("signal_profile") or profile,
                    "policy_mode": row.get("policy_mode") or "base",
                    "stake_units": row.get("stake_units", ""),
                    "stake_gbp": row.get("stake_gbp", ""),
                    "pin_odds1": row.get("pin_odds1", ""),
                    "pin_odds2": row.get("pin_odds2", ""),
                    "spread_odds": row.get("spread_odds", ""),
                    "shadow_reason": row.get("shadow_reason", ""),
                }
            )
    SIGNALS_CURRENT_JSON.parent.mkdir(parents=True, exist_ok=True)
    SIGNALS_CURRENT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")


PHASE0_RESEARCH_LANE_STUBS = {"slam_bo5", "challenger_ml", "indoor_bo3"}


def phase0_signal_profile_dispatch(
    signal_profile: str,
    internal_research_lanes: bool,
) -> tuple[str, int | None, str, bool]:
    """Normalize or short-circuit Phase 0 research-lane signal profiles.

    Returns (normalized_profile, exit_code, message, message_to_stderr).
    exit_code=None means the caller should continue with normalized_profile.
    """

    if signal_profile == "hard_bo3":
        return "strict", None, "", False
    if signal_profile == "challenger_hc":
        return signal_profile, 2, "lane disabled: awaiting Pinnacle HC coverage + challenger_ml proof", True
    if signal_profile in {"clay_bo3", "grass_bo3", "cpi_speed_shadow"} and not internal_research_lanes:
        return signal_profile, 2, f"lane {signal_profile} requires INTERNAL_RESEARCH_LANES=1", True
    if signal_profile in PHASE0_RESEARCH_LANE_STUBS:
        if not internal_research_lanes:
            return signal_profile, 2, f"lane {signal_profile} requires INTERNAL_RESEARCH_LANES=1", True
        return signal_profile, 0, f"lane {signal_profile}: Phase 0 scaffold (no-op)", False
    return signal_profile, None, "", False


def main() -> int:
    load_env()

    parser = argparse.ArgumentParser(description="Strict policy signals report with optional tournament-overlay mode.")
    parser.add_argument("--date", default="", help="UTC date YYYY-MM-DD (default: today)")
    parser.add_argument("--append", action="store_true", help="Write live snapshot CSVs and append archive CSVs")
    parser.add_argument(
        "--signal-profile",
        choices=(
            "strict",
            "volume_275",
            "volume_200",
            "spread_shadow",
            "spread_v1_shadow",
            "spread_v1_clay_fav",
            "challenger_ml_shadow",
            "hard_bo3",
            "clay_bo3",
            "slam_bo5",
            "challenger_ml",
            "indoor_bo3",
            "grass_bo3",
            "cpi_speed_shadow",
            "challenger_hc",
        ),
        default=(os.environ.get("STRICT_SIGNAL_PROFILE", "strict") or "strict").strip().lower(),
        help="Signal profile to evaluate/write (strict live policy or one of the shadow volume profiles).",
    )
    parser.add_argument("--output", default="", help="Live output CSV path for profile signals (auto by profile if omitted)")
    parser.add_argument("--internal-output", default="", help="Internal live CSV path (auto by profile if omitted)")
    parser.add_argument("--policy-mode", choices=("base", "overlay"), default="base", help="Production mode")
    parser.add_argument("--hard-calibration-file", default=os.environ.get("HARD_CALIBRATION_PARAMS_FILE", str(DEFAULT_HARD_CALIBRATION_FILE)))
    parser.add_argument(
        "--hard-calibration-live",
        action="store_true",
        default=False,
        help="Research override only: use hard-court calibration for strict/volume ML values (default off after identity-clean audit)",
    )
    parser.add_argument("--compare-overlay", action="store_true", help="Compute and print base vs overlay side-by-side")
    parser.add_argument("--compare-output", default=str(DEFAULT_COMPARE_OUTPUT), help="CSV path for side-by-side tracking")

    parser.add_argument("--overlay-policy-file", default=str(DEFAULT_OVERLAY_POLICY_FILE))
    parser.add_argument("--overlay-window", default=DEFAULT_OVERLAY_WINDOW)
    parser.add_argument("--overlay-family", choices=("seed", "entry"), default=DEFAULT_OVERLAY_FAMILY)
    parser.add_argument("--overlay-min-n", type=int, default=DEFAULT_OVERLAY_MIN_N)
    parser.add_argument("--overlay-min-roi-pct", type=float, default=DEFAULT_OVERLAY_MIN_ROI_PCT)
    parser.add_argument("--overlay-missing-mode", choices=("skip", "allow"), default=DEFAULT_OVERLAY_MISSING_MODE)
    parser.add_argument(
        "--injury-overlay-enabled",
        dest="injury_overlay_enabled",
        action="store_true",
        default=env_bool(os.environ.get("STRICT_INJURY_OVERLAY_ENABLED"), False),
        help="Exclude strict candidates when either player has a recent injured-list row",
    )
    parser.add_argument(
        "--no-injury-overlay-enabled",
        dest="injury_overlay_enabled",
        action="store_false",
        help="Disable injury exclusion overlay (default)",
    )
    parser.add_argument(
        "--injury-lookback-days",
        type=int,
        default=int(os.environ.get("STRICT_INJURY_LOOKBACK_DAYS", str(DEFAULT_STRICT_INJURY_LOOKBACK_DAYS))),
    )
    parser.add_argument(
        "--injury-csv",
        default=os.environ.get("INJURED_PLAYERS_CSV", str(DEFAULT_INJURY_CSV)),
    )
    parser.add_argument(
        "--clay-calibration-file",
        default=str(DEFAULT_CLAY_CALIBRATION_FILE),
        help="Clay-only favorite-probability remap JSON for the calibrated shadow lane.",
    )
    parser.add_argument(
        "--spread-v1-calibration-file",
        default=str(DEFAULT_SPREAD_V1_CALIBRATION_FILE),
        help="Versioned real-market spread calibration JSON for spread_v1_shadow.",
    )
    parser.add_argument(
        "--cpi-speed-gates-file",
        default=os.environ.get("CPI_SPEED_GATES_FILE", str(DEFAULT_CPI_SPEED_GATES_FILE)),
        help="PASS_SHADOW gate CSV for cpi_speed_shadow.",
    )
    args = parser.parse_args()
    args.signal_profile, phase0_exit_code, phase0_message, phase0_stderr = phase0_signal_profile_dispatch(
        args.signal_profile,
        os.environ.get("INTERNAL_RESEARCH_LANES") == "1",
    )
    if phase0_exit_code is not None:
        print(phase0_message, file=sys.stderr if phase0_stderr else sys.stdout)
        return phase0_exit_code

    if (
        args.signal_profile == "spread_v1_clay_fav"
        and args.spread_v1_calibration_file == str(DEFAULT_SPREAD_V1_CALIBRATION_FILE)
    ):
        args.spread_v1_calibration_file = str(DEFAULT_SPREAD_V1_CLAY_CALIBRATION_FILE)

    profile_public_paths, profile_internal_paths = SIGNAL_PROFILE_PATHS[args.signal_profile]
    if not args.output:
        args.output = str(profile_public_paths.live)
    if not args.internal_output:
        if args.signal_profile in {"spread_shadow", "challenger_ml_shadow", "clay_bo3", "grass_bo3", "cpi_speed_shadow", *SPREAD_V1_SIGNAL_PROFILES}:
            args.internal_output = ""
        else:
            args.internal_output = str((profile_internal_paths or STRICT_INTERNAL_SIGNAL_PATHS).live)
    if args.signal_profile != "strict" and args.policy_mode == "overlay":
        print(f"WARNING: overlay mode applies to strict profile only; forcing policy-mode=base for {args.signal_profile}.")
        args.policy_mode = "base"
    if args.signal_profile != "strict" and args.compare_overlay:
        print(f"WARNING: --compare-overlay applies to strict profile only; disabling for {args.signal_profile}.")
        args.compare_overlay = False
    clay_prob_map = _load_piecewise_prob_map(Path(args.clay_calibration_file))
    if args.signal_profile == "clay_calibrated" and not clay_prob_map:
        print(f"Clay calibrated profile requested but no valid remap points loaded from {args.clay_calibration_file}", file=sys.stderr)
        return 1
    hard_calibration_params = _load_hard_calibration_params(Path(args.hard_calibration_file)) if args.hard_calibration_live else None
    hard_calibration_live_profiles = {
        part.strip()
        for part in os.environ.get("STRICT_HARD_CALIBRATION_PROFILES", "strict").split(",")
        if part.strip()
    }
    hard_calibration_live = bool(args.hard_calibration_live and args.signal_profile in hard_calibration_live_profiles and hard_calibration_params)
    if args.hard_calibration_live and args.signal_profile not in hard_calibration_live_profiles:
        print(f"WARNING: hard calibration live applies to {sorted(hard_calibration_live_profiles)} only; disabled for {args.signal_profile}.")
    elif args.hard_calibration_live and not hard_calibration_params:
        print(f"WARNING: hard calibration live requested but params missing/invalid at {args.hard_calibration_file}; using base probabilities.")
    if args.signal_profile == "challenger_ml_shadow" and not CHALLENGER_ML_ENABLE:
        print("challenger_ml_shadow disabled: CHALLENGER_ML_ENABLE=0")
        if args.append:
            out_paths = derive_signal_csv_paths(Path(args.output))
            live_count = write_live_snapshot(
                out_paths.live,
                [],
                dedup_key_fields=["date", "player1", "player2", "bet_type", "side", "policy_mode", "signal_profile"],
                lane_key_fields=["date", "player1", "player2", "bet_type", "policy_mode", "signal_profile"],
            )
            archive_added = append_rows_dedup(
                out_paths.archive,
                [],
                key_fields=["date", "player1", "player2", "bet_type", "side", "policy_mode", "signal_profile"],
            )
            mirror_live_snapshot(out_paths)
            print(
                f"Wrote {live_count}/0 public live rows to {out_paths.live} "
                f"and appended {archive_added} archive rows to {out_paths.archive}."
            )
            write_signals_current_artifact()
            print(f"Updated signals artifact at {SIGNALS_CURRENT_JSON}.")
        return 0
    spread_v1_calibration_status = _load_spread_v1_calibration_status(Path(args.spread_v1_calibration_file))
    if args.signal_profile == "spread_v1_clay_fav":
        stale_days = _spread_v1_fit_age_days(spread_v1_calibration_status)
        stale_reason = None
        if not spread_v1_calibration_status.get("valid", False):
            stale_reason = f"calibration_{spread_v1_calibration_status.get('reason', 'invalid')}"
        elif stale_days is None:
            stale_reason = "calibration_timestamp_missing"
        elif stale_days > SPREAD_V1_CLAY_FAV_STALE_DAYS:
            stale_reason = f"calibration_stale_{stale_days}d"
        if stale_reason:
            print(
                f"spread_v1_clay_fav disabled: {stale_reason} "
                f"path={args.spread_v1_calibration_file}"
            )
            if args.append:
                out_paths = derive_signal_csv_paths(Path(args.output))
                live_count = write_live_snapshot(
                    out_paths.live,
                    [],
                    dedup_key_fields=["player1", "player2", "bet_type", "side", "policy_mode", "signal_profile"],
                    lane_key_fields=["player1", "player2", "bet_type", "side", "policy_mode", "signal_profile"],
                )
                audit_row = _profile_audit_row(stale_reason, "spread_v1_clay_fav")
                archive_added = append_rows_dedup(
                    out_paths.archive,
                    [audit_row],
                    key_fields=["date", "signal_profile", "skip_reason"],
                )
                mirror_live_snapshot(out_paths)
                print(
                    f"Wrote {live_count}/0 public live rows to {out_paths.live} "
                    f"and appended {archive_added} audit rows to {out_paths.archive}."
                )
                write_signals_current_artifact()
                print(f"Updated signals artifact at {SIGNALS_CURRENT_JSON}.")
            return 0
    if args.signal_profile in SPREAD_V1_SIGNAL_PROFILES and not spread_v1_calibration_status.get("valid", False):
        print(
            f"{args.signal_profile} disabled: "
            f"calibration invalid ({spread_v1_calibration_status.get('reason', 'unknown')}) "
            f"path={args.spread_v1_calibration_file}"
        )
        if args.append:
            if args.signal_profile in SPREAD_V1_SIGNAL_PROFILES:
                # One spread-v1 pick per fixture/side. Line refreshes are price
                # updates, not separate bets.
                live_dedup_fields = ["player1", "player2", "bet_type", "side", "policy_mode", "signal_profile"]
                lane_key_fields = live_dedup_fields
                archive_key_fields = live_dedup_fields
            else:
                live_dedup_fields = ["date", "player1", "player2", "bet_type", "side", "spread_line", "policy_mode", "signal_profile"]
                lane_key_fields = ["date", "player1", "player2", "bet_type", "spread_line", "policy_mode", "signal_profile"]
                archive_key_fields = ["date", "player1", "player2", "bet_type", "side", "spread_line", "policy_mode", "signal_profile"]
            out_paths = derive_signal_csv_paths(Path(args.output))
            live_count = write_live_snapshot(
                out_paths.live,
                [],
                dedup_key_fields=live_dedup_fields,
                lane_key_fields=lane_key_fields,
            )
            archive_added = append_rows_dedup(
                out_paths.archive,
                [],
                key_fields=archive_key_fields,
            )
            mirror_live_snapshot(out_paths)
            print(
                f"Wrote {live_count}/0 public live rows to {out_paths.live} "
                f"and appended {archive_added} archive rows to {out_paths.archive}."
            )
            write_signals_current_artifact()
            print(f"Updated signals artifact at {SIGNALS_CURRENT_JSON}.")
        return 0

    url = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env.local", file=sys.stderr)
        return 1

    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    base = f"{url}/rest/v1"

    today = datetime.now(timezone.utc).date().isoformat()
    if args.date:
        today = args.date
    try:
        season_year = int(today[:4])
    except ValueError:
        print(f"Invalid date format: {today}", file=sys.stderr)
        return 1
    try:
        report_day = date.fromisoformat(today)
    except ValueError:
        print(f"Invalid date format: {today}", file=sys.stderr)
        return 1
    surface_speed_lookup = load_surface_speed_lookup(DEFAULT_SURFACE_SPEED_FILE)
    surface_speed_context_lookup: dict[tuple[int, str, str], float] = {}
    surface_speed_year_stats: dict[tuple[int, str], tuple[float, float]] = {}
    surface_speed_surface_stats: dict[str, tuple[float, float]] = {}
    cpi_speed_pass_gates: set[tuple[str, str]] = set()
    if args.signal_profile == "cpi_speed_shadow":
        cpi_speed_pass_gates = load_cpi_speed_pass_gates(Path(args.cpi_speed_gates_file))
        (
            surface_speed_context_lookup,
            surface_speed_year_stats,
            surface_speed_surface_stats,
        ) = load_surface_speed_context(DEFAULT_SURFACE_SPEED_FILE)
        if not cpi_speed_pass_gates:
            print(
                "WARNING: no identity-clean CPI speed PASS_SHADOW gates loaded from "
                f"{args.cpi_speed_gates_file}; required identity_basis={CPI_SPEED_REQUIRED_IDENTITY_BASIS}; "
                "lane will be empty."
            )

    injury_index = load_recent_injury_index(
        Path(args.injury_csv),
        lookback_days=max(0, int(args.injury_lookback_days)),
        today=report_day,
        include_sources=("injured",),
    )
    injury_flagged_matches = 0
    injury_skipped_matches = 0

    base_daily_select = "id,tour_id,player1_id,player2_id,surface,p1_win_prob,p2_win_prob,odds1,odds2,p_a,p_b,confidence,spread_line,spread_odds1,spread_odds2,handicap_edge_p1,handicap_edge_p2"
    raw_daily_select = "id,tour_id,player1_id,player2_id,surface,p1_win_prob_raw,p2_win_prob_raw,p1_win_prob,p2_win_prob,odds1,odds2,p_a,p_b,confidence,spread_line,spread_odds1,spread_odds2,handicap_edge_p1,handicap_edge_p2"
    coverage_daily_select = (
        raw_daily_select
        + ",match_count_12m_p1,match_count_12m_p2,matches_total_p1,matches_total_p2,"
        + "recent_challenger_plus_p1,recent_challenger_plus_p2,last_match_days_p1,last_match_days_p2,data_coverage_tag"
    )
    r = requests.get(
        f"{base}/daily_fair_odds",
        headers=headers,
        params={
            "select": coverage_daily_select,
            "limit": 2000,
        },
        timeout=30,
    )
    if r.status_code >= 400 and any(tok in r.text.lower() for tok in ("schema cache", "unknown column", "could not find", "does not exist", "42703")):
        print("WARNING: daily_fair_odds coverage columns missing; Challenger coverage gates will stay dark until SQL migration is applied.")
        r = requests.get(
            f"{base}/daily_fair_odds",
            headers=headers,
            params={"select": base_daily_select, "limit": 2000},
            timeout=30,
        )
    r.raise_for_status()
    rows = r.json() or []
    if not rows:
        print("No rows in daily_fair_odds. Run oncourt-compute-fair-odds.py first.")
        return 0

    try:
        today_rows = fetch_rest_paged(
            base,
            "oncourt_today",
            headers,
            {
                "select": "tour_id,player1_id,player2_id,result",
                "order": "tour_id.asc,round_id.asc,draw.asc,player1_id.asc,player2_id.asc",
            },
            timeout=30,
        )
        open_pair_keys: set[tuple[int, int, int]] = set()
        for today_row in today_rows:
            if str(today_row.get("result") or "").strip():
                continue
            try:
                tid = int(today_row["tour_id"])
                p1 = int(today_row["player1_id"])
                p2 = int(today_row["player2_id"])
            except (KeyError, TypeError, ValueError):
                continue
            open_pair_keys.add((tid, p1, p2))
            open_pair_keys.add((tid, p2, p1))
        if open_pair_keys:
            before = len(rows)
            rows = [
                row
                for row in rows
                if (
                    row.get("tour_id") is not None
                    and row.get("player1_id") is not None
                    and row.get("player2_id") is not None
                    and (
                        int(row["tour_id"]),
                        int(row["player1_id"]),
                        int(row["player2_id"]),
                    )
                    in open_pair_keys
                )
            ]
            print(f"Filtered daily_fair_odds to open OnCourt rows: {len(rows)}/{before}")
    except Exception as exc:
        print(f"WARNING: oncourt_today open-row filter skipped: {exc}")

    tour_ids = list({r["tour_id"] for r in rows if r.get("tour_id") is not None})
    tours: dict[int, dict[str, Any]] = {}
    if tour_ids:
        for i in range(0, len(tour_ids), 100):
            chunk = tour_ids[i : i + 100]
            tr = requests.get(
                f"{base}/oncourt_tours",
                headers=headers,
                params={"select": "id,name,rank", "id": f"in.({','.join(str(x) for x in chunk)})"},
                timeout=30,
            )
            if tr.status_code == 200 and tr.json():
                for t in tr.json():
                    tid = t.get("id")
                    if tid is not None:
                        tours[int(tid)] = {"name": t.get("name") or "", "rank": t.get("rank")}

    player_ids = list(
        {r["player1_id"] for r in rows if r.get("player1_id") is not None}
        | {r["player2_id"] for r in rows if r.get("player2_id") is not None}
    )
    players: dict[int, str] = {}
    for i in range(0, len(player_ids), 100):
        chunk = player_ids[i : i + 100]
        pr = requests.get(
            f"{base}/oncourt_players",
            headers=headers,
            params={"select": "id,name", "id": f"in.({','.join(str(x) for x in chunk)})"},
            timeout=30,
        )
        if pr.status_code == 200 and pr.json():
            for p in pr.json():
                pid = p.get("id")
                if pid is not None:
                    players[int(pid)] = p.get("name") or ""

    def fetch_pinnacle_snapshot(snapshot_date: str) -> list[dict[str, Any]]:
        snap = requests.get(
            f"{base}/bookmaker_odds_snapshot",
            headers=headers,
            params={
                "select": "player1_name,player2_name,odds1,odds2,league",
                "bookmaker": "eq.Pinnacle",
                "capture_date": "eq." + snapshot_date,
                "league": "in.(ATP,Challenger)",
            },
            timeout=30,
        )
        snap.raise_for_status()
        return snap.json() or []

    snapshot_date_used = today
    pin_rows = fetch_pinnacle_snapshot(snapshot_date_used)
    local_pin_rows = load_local_pinnacle_snapshot(snapshot_date_used)
    if local_pin_rows:
        # Local rows come first so exact duplicate pairings keep the freshest
        # capture when match_pinnacle_rows collapses candidates by identity.
        pin_rows = local_pin_rows + pin_rows
        print(
            f"Merged {len(local_pin_rows)} latest local Pinnacle pairings "
            f"with {len(pin_rows) - len(local_pin_rows)} database snapshot rows."
        )
    if not pin_rows:
        # The evening pipeline often crosses midnight UTC after scraping odds.
        # Reuse the previous snapshot instead of publishing a false empty lane.
        yesterday = (report_day - timedelta(days=1)).isoformat()
        fallback_rows = fetch_pinnacle_snapshot(yesterday)
        if fallback_rows:
            snapshot_date_used = yesterday
            pin_rows = fallback_rows
            print(f"No Pinnacle snapshot for {today}; using {snapshot_date_used} snapshot.")

    fair_rows_for_match = [
        {
            "id": r.get("id"),
            "p1_name": players.get(r.get("player1_id") or 0) or "",
            "p2_name": players.get(r.get("player2_id") or 0) or "",
        }
        for r in rows
    ]
    matched_pinnacle = match_pinnacle_rows(fair_rows_for_match, pin_rows)

    candidates: list[dict[str, Any]] = []
    challenger_nearmiss_rows: list[dict[str, Any]] = []
    clay_bo3_nearmiss_rows: list[dict[str, Any]] = []
    grass_bo3_nearmiss_rows: list[dict[str, Any]] = []
    cpi_speed_nearmiss_rows: list[dict[str, Any]] = []
    for r in rows:
        surface = (r.get("surface") or "").strip()
        confidence = (r.get("confidence") or "").strip().lower()
        tournament_speed_signal = float(r.get("tournament_speed_signal") or 0.0)
        clay_speed_tier = (
            "fast" if surface == "Clay" and tournament_speed_signal >= 0.10 else "normal" if surface == "Clay" else ""
        )
        tour_id = r.get("tour_id")
        tour_meta = tours.get(tour_id, {}) if tour_id is not None else {}
        tournament_name = tour_meta.get("name") or ""
        series_bucket = series_bucket_from_tour(tour_meta.get("name"), tour_meta.get("rank"))
        strict_min_value = strict_min_value_for(surface, series_bucket, confidence)
        volume_min_value = (
            shadow_profile_min_value_for(args.signal_profile, surface, series_bucket, confidence, tournament_name)
            if args.signal_profile not in {"strict", "spread_shadow", *SPREAD_V1_SIGNAL_PROFILES}
            else None
        )
        if args.signal_profile == "clay_calibrated":
            strict_min_value = None
            volume_min_value = None
        spread_shadow_reason = spread_shadow_reason_for(surface, series_bucket, confidence, tournament_name)
        spread_shadow_eligible = args.signal_profile == "spread_shadow" and spread_shadow_reason is not None
        clay_calibrated_enabled = args.signal_profile == "clay_calibrated" and surface == "Clay"
        challenger_ml_requested = args.signal_profile == "challenger_ml_shadow"
        clay_bo3_requested = args.signal_profile == "clay_bo3"
        grass_bo3_requested = args.signal_profile == "grass_bo3"
        cpi_speed_requested = args.signal_profile == "cpi_speed_shadow"
        spread_v1_requested = args.signal_profile in SPREAD_V1_SIGNAL_PROFILES
        spread_v1_clay_fav_requested = args.signal_profile == "spread_v1_clay_fav"
        if (
            strict_min_value is None
            and volume_min_value is None
            and not spread_shadow_eligible
            and not clay_calibrated_enabled
            and not challenger_ml_requested
            and not clay_bo3_requested
            and not grass_bo3_requested
            and not cpi_speed_requested
            and not spread_v1_requested
        ):
            continue

        our_odds1 = r.get("odds1")
        our_odds2 = r.get("odds2")
        if our_odds1 is None or our_odds2 is None:
            continue
        our_odds1 = float(our_odds1)
        our_odds2 = float(our_odds2)
        p1_win_prob = float(r.get("p1_win_prob") or 0.0)
        p2_win_prob = float(r.get("p2_win_prob") or 0.0)
        hard_calibration_live_for_row = False
        hard_p1_win_prob = None
        if hard_calibration_live and surface == "Hard" and args.signal_profile in hard_calibration_live_profiles:
            hard_input_prob = _parse_point_prob(r.get("p1_win_prob_raw"))
            if hard_input_prob is not None:
                hard_p1_win_prob = _hard_overlay_prob(hard_input_prob, series_bucket, confidence, hard_calibration_params)
                hard_calibration_live_for_row = hard_p1_win_prob is not None
        policy_p1_win_prob = hard_p1_win_prob if hard_calibration_live_for_row and hard_p1_win_prob is not None else p1_win_prob
        policy_p2_win_prob = 1.0 - policy_p1_win_prob if hard_calibration_live_for_row else p2_win_prob
        policy_odds1 = 1.0 / _safe_prob(policy_p1_win_prob)
        policy_odds2 = 1.0 / _safe_prob(policy_p2_win_prob)
        model_favorite_prob = max(policy_p1_win_prob, policy_p2_win_prob)
        model_favorite_side = "P1" if policy_p1_win_prob >= policy_p2_win_prob else "P2"
        # ML only: skip matches where model favourite odds < 1.25.
        # Keep spreads eligible; this filter is for dog-moneyline distortions.
        model_fav_odds = min(policy_odds1, policy_odds2)
        model_ml_excluded = model_fav_odds < MISPRICE_MODEL_FAV_ODDS_MIN
        atp500_short_favorite_ml_excluded = is_excluded_short_favorite(
            surface,
            series_bucket,
            confidence,
            policy_odds1,
            policy_odds2,
        )

        p1_name = players.get(r.get("player1_id") or 0) or ""
        p2_name = players.get(r.get("player2_id") or 0) or ""
        p1_inj, p1_inj_mode = injury_index.match_name(p1_name)
        p2_inj, p2_inj_mode = injury_index.match_name(p2_name)
        inj_any = p1_inj or p2_inj
        if inj_any:
            injury_flagged_matches += 1
        row_id = r.get("id")
        pin = matched_pinnacle.get(int(row_id)) if row_id is not None else None
        if not pin or (pin["odds1"] or 0) <= 0 or (pin["odds2"] or 0) <= 0:
            continue
        league = league_bucket_from_tour(tournament_name, pin.get("league"))
        if args.signal_profile != "strict" and not shadow_profile_league_allowed(args.signal_profile, league):
            volume_min_value = None
            spread_shadow_eligible = False
            clay_calibrated_enabled = False
            cpi_speed_requested = False
            if strict_min_value is None:
                continue
        spread_v1_scope = (
            spread_v1_clay_fav_scope_reason(surface, series_bucket, league, confidence)
            if spread_v1_clay_fav_requested
            else spread_v1_scope_reason(surface, series_bucket, league, confidence)
            if spread_v1_requested
            else None
        )
        spread_v1_eligible = (
            spread_v1_requested
            and spread_v1_scope is None
            and spread_v1_calibration_status.get("valid") is True
        )
        clay_bo3_scope = clay_bo3_scope_reason(surface, series_bucket, league, confidence) if clay_bo3_requested else None
        clay_bo3_scope_ok = clay_bo3_requested and clay_bo3_scope is None
        clay_bo3_spread_eligible = clay_bo3_scope_ok
        grass_bo3_scope = grass_bo3_scope_reason(surface, series_bucket, league, confidence) if grass_bo3_requested else None
        grass_cpi: float | None = None
        grass_cpi_year: int | None = None
        grass_cpi_key = ""
        grass_cpi_mode = ""
        grass_speed_tier = ""
        grass_speed_reason: str | None = None
        if grass_bo3_requested and surface == "Grass":
            grass_cpi, grass_cpi_year, grass_cpi_key, grass_cpi_mode = resolve_surface_speed(
                surface_speed_lookup,
                surface=surface,
                tournament_name=tournament_name,
                season_year=season_year,
                lag_only=GRASS_BO3_CPI_LAG_ONLY,
                lag_years=GRASS_BO3_CPI_LAG_YEARS,
            )
            if grass_cpi is None:
                grass_speed_reason = "grass_speed_missing" if GRASS_BO3_FAST_CPI_GATE else None
                grass_speed_tier = "missing"
            elif grass_cpi < GRASS_BO3_SLOW_CPI_MAX:
                grass_speed_tier = "slow"
                grass_speed_reason = "grass_slow_court" if GRASS_BO3_FAST_CPI_GATE else None
            elif grass_cpi >= GRASS_BO3_FAST_CPI_MIN:
                grass_speed_tier = "fast"
            else:
                grass_speed_tier = "neutral"
        grass_bo3_speed_ok = grass_speed_reason is None
        grass_bo3_scope_ok = grass_bo3_requested and grass_bo3_scope is None and grass_bo3_speed_ok

        # ML only: skip when Pinnacle favourite odds < 1.25. Keep spreads eligible.
        pin_fav_odds = min(float(pin["odds1"] or 0), float(pin["odds2"] or 0))
        pin_ml_excluded = pin_fav_odds > 0 and pin_fav_odds < MISPRICE_MODEL_FAV_ODDS_MIN
        pin_inv1 = 1.0 / float(pin["odds1"] or 1.0)
        pin_inv2 = 1.0 / float(pin["odds2"] or 1.0)
        pin_total_inv = pin_inv1 + pin_inv2
        pin_p1_no_vig = pin_inv1 / pin_total_inv if pin_total_inv > 0 else 0.5
        pin_favorite_side = "P1" if pin_p1_no_vig >= 0.5 else "P2"
        model_market_fav_gap = abs(model_favorite_prob - max(pin_p1_no_vig, 1.0 - pin_p1_no_vig))
        model_market_side_flip_excluded = (
            model_favorite_side != pin_favorite_side
            and abs(pin_p1_no_vig - 0.5) >= MISPRICE_MODEL_MARKET_FAV_SIDE_FLIP_BUFFER
            and abs(policy_p1_win_prob - 0.5) >= MISPRICE_MODEL_MARKET_FAV_SIDE_FLIP_BUFFER
        )
        hard_masters_side_flip_allowed = allow_hard_masters_side_flip(
            detected=model_market_side_flip_excluded,
            league=league,
            surface=surface,
            series_bucket=series_bucket,
            confidence=confidence,
            model_market_fav_gap=model_market_fav_gap,
        )
        model_market_side_flip_excluded = (
            model_market_side_flip_excluded and not hard_masters_side_flip_allowed
        )
        model_market_gap_excluded = (
            model_market_fav_gap > MISPRICE_MODEL_MARKET_FAV_GAP_MAX
            or model_market_side_flip_excluded
        )
        grass_bo3_favorite_agreement = model_favorite_side == pin_favorite_side
        cpi_speed_cpi: float | None = None
        cpi_speed_year: int | None = None
        cpi_speed_z: float | None = None
        cpi_speed_key = ""
        cpi_speed_mode = ""
        cpi_speed_bucket_value = "missing"
        if cpi_speed_requested:
            cpi_speed_cpi, cpi_speed_year, cpi_z_value, cpi_speed_key, cpi_speed_mode = resolve_surface_speed_z(
                surface_speed_context_lookup,
                surface_speed_year_stats,
                surface_speed_surface_stats,
                surface=surface,
                tournament_name=tournament_name,
                season_year=season_year,
                lag_only=CPI_SPEED_CPI_LAG_ONLY,
                lag_years=CPI_SPEED_CPI_LAG_YEARS,
                z_cap=CPI_SPEED_Z_CAP,
            )
            cpi_speed_z = cpi_z_value if cpi_speed_cpi is not None else None
            cpi_speed_bucket_value = cpi_speed_bucket(cpi_speed_z)

        stored_pa = _parse_point_prob(r.get("p_a"))
        stored_pb = _parse_point_prob(r.get("p_b"))
        stored_match_prob = prob_match_best_of_3(stored_pa, stored_pb) if stored_pa is not None and stored_pb is not None else None
        handicap_point_prob_gap = stored_match_prob - p1_win_prob if stored_match_prob is not None else None
        handicap_shape_trusted = (
            handicap_point_prob_gap is not None
            and abs(handicap_point_prob_gap) <= POINT_PROB_MATCH_PROB_GAP_MAX
        )

        value_p1 = (float(pin["odds1"]) * policy_p1_win_prob - 1) * 100 if policy_odds1 > 1 else None
        value_p2 = (float(pin["odds2"]) * policy_p2_win_prob - 1) * 100 if policy_odds2 > 1 else None
        calibrated_p1_win_prob = _apply_piecewise_favorite_remap(p1_win_prob, clay_prob_map) if surface == "Clay" and clay_prob_map else p1_win_prob
        calibrated_p2_win_prob = _safe_prob(1.0 - calibrated_p1_win_prob)
        calibrated_odds1 = 1.0 / _safe_prob(calibrated_p1_win_prob)
        calibrated_odds2 = 1.0 / _safe_prob(calibrated_p2_win_prob)
        calibrated_value_p1 = (pin["odds1"] / calibrated_odds1 - 1) * 100 if calibrated_odds1 > 1 else None
        calibrated_value_p2 = (pin["odds2"] / calibrated_odds2 - 1) * 100 if calibrated_odds2 > 1 else None
        calibrated_side = "P1" if (calibrated_value_p1 or 0) >= (calibrated_value_p2 or 0) else "P2"
        calibrated_value_pct = calibrated_value_p1 if calibrated_side == "P1" else calibrated_value_p2
        calibrated_selected_prob = calibrated_p1_win_prob if calibrated_side == "P1" else calibrated_p2_win_prob
        raw_value_same_side = value_p1 if calibrated_side == "P1" else value_p2
        raw_side = "P1" if (value_p1 or 0) >= (value_p2 or 0) else "P2"
        raw_favorite_side = "P1" if p1_win_prob >= 0.5 else "P2"
        calibrated_favorite_side = "P1" if calibrated_p1_win_prob >= 0.5 else "P2"
        clay_calibration_side_flip = calibrated_side != raw_side
        clay_calibration_favorite_flip = calibrated_favorite_side != raw_favorite_side
        if args.injury_overlay_enabled and inj_any:
            injury_skipped_matches += 1
            continue

        spread_line = r.get("spread_line")
        spread_o1 = r.get("spread_odds1")
        spread_o2 = r.get("spread_odds2")
        he_p1 = r.get("handicap_edge_p1")
        he_p2 = r.get("handicap_edge_p2")
        sl = float(spread_line) if spread_line is not None else None
        so1 = float(spread_o1) if spread_o1 is not None else None
        so2 = float(spread_o2) if spread_o2 is not None else None
        he1 = float(he_p1) if he_p1 is not None else None
        he2 = float(he_p2) if he_p2 is not None else None

        side = raw_side
        value_pct = value_p1 if side == "P1" else value_p2
        fav_side = "P1" if policy_odds1 <= policy_odds2 else "P2"
        has_internal_ml_value = (
            (value_p1 is not None and value_p1 >= INTERNAL_TRACK_MIN_VALUE_PCT)
            or (value_p2 is not None and value_p2 >= INTERNAL_TRACK_MIN_VALUE_PCT)
        )
        strict_favorite_spread_conflict = (
            strict_min_value is not None
            and not inj_any
            and has_favorite_spread_conflict(model_favorite_side, sl, he1, he2)
            and side != model_favorite_side
        )
        heavy_favorite_dog_excluded = is_excluded_heavy_favorite_dog(
            surface,
            series_bucket,
            model_favorite_prob,
            side,
            model_favorite_side,
        )
        cpi_speed_gate_ok = False
        cpi_speed_gate_label = ""
        cpi_speed_gate_labels: list[str] = []
        if cpi_speed_requested and value_pct is not None:
            cpi_speed_gate_ok, cpi_speed_gate_label, cpi_speed_gate_labels = cpi_speed_gate_match(
                cpi_speed_pass_gates,
                surface=surface,
                cpi_bucket=cpi_speed_bucket_value,
                confidence=confidence,
                series_bucket=series_bucket,
                value_pct=value_pct,
                model_favorite_side=model_favorite_side,
                pin_favorite_side=pin_favorite_side,
            )
        strict_match = (
            strict_min_value is not None
            and not model_ml_excluded
            and not pin_ml_excluded
            and not model_market_gap_excluded
            and not atp500_short_favorite_ml_excluded
            and has_internal_ml_value
            and value_pct is not None
            and value_pct >= strict_min_value
            and not heavy_favorite_dog_excluded
            and not strict_favorite_spread_conflict
        )
        volume_match = (
            volume_min_value is not None
            and not strict_match
            and not model_ml_excluded
            and not pin_ml_excluded
            and not model_market_gap_excluded
            and not atp500_short_favorite_ml_excluded
            and has_internal_ml_value
            and value_pct is not None
            and value_pct >= volume_min_value
        )
        clay_calibrated_match = (
            clay_calibrated_enabled
            and confidence in CLAY_CALIBRATED_CONFIDENCE
            and not model_ml_excluded
            and not pin_ml_excluded
            and not model_market_gap_excluded
            and not atp500_short_favorite_ml_excluded
            and calibrated_value_pct is not None
            and calibrated_value_pct >= CLAY_CALIBRATED_MIN_VALUE_PCT
            and (raw_value_same_side is None or raw_value_same_side < CLAY_CALIBRATED_MIN_VALUE_PCT)
            and calibrated_selected_prob >= CLAY_CALIBRATED_PROB_MIN
            and calibrated_selected_prob < CLAY_CALIBRATED_PROB_MAX
            # Calibration can tighten price on the same side, but if it crosses
            # through 50/50 and invents the opposite side, the lane becomes
            # unstable from one refresh to the next.
            and not clay_calibration_side_flip
            and not clay_calibration_favorite_flip
        )
        challenger_fields = challenger_coverage_fields(r, tournament_name, tour_id) if challenger_ml_requested else {}
        challenger_coverage_tag = str(challenger_fields.get("data_coverage_tag") or "").upper()
        challenger_ml_match = (
            challenger_ml_requested
            and CHALLENGER_ML_ENABLE
            and league == "Challenger"
            and surface in CHALLENGER_ML_ALLOWED_SURFACES
            and confidence in CHALLENGER_ML_ALLOWED_CONFIDENCE
            and challenger_coverage_tag == CHALLENGER_ML_REQUIRE_COVERAGE_TAG
            and not model_ml_excluded
            and not pin_ml_excluded
            and not model_market_gap_excluded
            and not atp500_short_favorite_ml_excluded
            and value_pct is not None
            and CHALLENGER_ML_MIN_EDGE_PCT <= value_pct <= CHALLENGER_ML_MAX_EDGE_PCT
        )
        clay_bo3_ml_match = (
            CLAY_BO3_ML_ENABLE
            and clay_bo3_scope_ok
            and not model_ml_excluded
            and not pin_ml_excluded
            and not model_market_gap_excluded
            and not atp500_short_favorite_ml_excluded
            and not heavy_favorite_dog_excluded
            and value_pct is not None
            and CLAY_BO3_MIN_EDGE_PCT <= value_pct <= CLAY_BO3_MAX_EDGE_PCT
        )
        grass_bo3_ml_match = (
            grass_bo3_scope_ok
            and (not GRASS_BO3_REQUIRE_FAV_AGREEMENT or grass_bo3_favorite_agreement)
            and not model_ml_excluded
            and not pin_ml_excluded
            and not model_market_gap_excluded
            and not atp500_short_favorite_ml_excluded
            and not heavy_favorite_dog_excluded
            and value_pct is not None
            and GRASS_BO3_MIN_EDGE_PCT <= value_pct <= GRASS_BO3_MAX_EDGE_PCT
        )
        cpi_speed_match = (
            cpi_speed_requested
            and league == "ATP"
            and cpi_speed_cpi is not None
            and cpi_speed_gate_ok
            and confidence in CPI_SPEED_ALLOWED_CONFIDENCE
            and not model_ml_excluded
            and not pin_ml_excluded
            and not model_market_gap_excluded
            and not atp500_short_favorite_ml_excluded
            and not heavy_favorite_dog_excluded
            and value_pct is not None
            and CPI_SPEED_MIN_EDGE_PCT <= value_pct <= CPI_SPEED_MAX_EDGE_PCT
        )
        if cpi_speed_requested and league == "ATP" and not cpi_speed_match:
            if cpi_speed_cpi is None:
                cpi_skip_reason = "cpi_missing"
            elif value_pct is None:
                cpi_skip_reason = "edge_missing"
            elif value_pct < CPI_SPEED_MIN_EDGE_PCT:
                cpi_skip_reason = "edge_below_floor"
            elif value_pct > CPI_SPEED_MAX_EDGE_PCT:
                cpi_skip_reason = "edge_above_cap"
            elif confidence not in CPI_SPEED_ALLOWED_CONFIDENCE:
                cpi_skip_reason = "low_confidence"
            elif model_market_gap_excluded:
                cpi_skip_reason = "model_market_gap"
            elif model_ml_excluded:
                cpi_skip_reason = "model_ml_excluded"
            elif pin_ml_excluded:
                cpi_skip_reason = "pin_ml_excluded"
            elif atp500_short_favorite_ml_excluded:
                cpi_skip_reason = "short_favorite_ml_excluded"
            elif heavy_favorite_dog_excluded:
                cpi_skip_reason = "heavy_favorite_dog_excluded"
            elif not cpi_speed_gate_ok:
                cpi_skip_reason = "no_passed_cpi_gate"
            else:
                cpi_skip_reason = "blocked"
            cpi_speed_nearmiss_rows.append(
                {
                    "date": snapshot_date_used,
                    "time_utc": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                    "player1": p1_name,
                    "player2": p2_name,
                    "surface": surface,
                    "league": league,
                    "series": series_bucket,
                    "confidence": confidence,
                    "side": side,
                    "value_pct": round(value_pct, 2) if value_pct is not None else "",
                    "model_favorite_side": model_favorite_side,
                    "pin_favorite_side": pin_favorite_side,
                    "cpi_speed_cpi": round(cpi_speed_cpi, 3) if cpi_speed_cpi is not None else "",
                    "cpi_speed_z": round(cpi_speed_z, 3) if cpi_speed_z is not None else "",
                    "cpi_speed_bucket": cpi_speed_bucket_value,
                    "cpi_speed_key": cpi_speed_key,
                    "cpi_speed_mode": cpi_speed_mode,
                    "cpi_speed_gate_labels": ";".join(cpi_speed_gate_labels[:8]),
                    "skip_reason": cpi_skip_reason,
                }
            )
        if clay_bo3_requested and league == "ATP" and surface == "Clay" and not clay_bo3_ml_match:
            skip_reason = clay_bo3_skip_reason(
                ml_enabled=CLAY_BO3_ML_ENABLE,
                scope_reason=clay_bo3_scope,
                value_pct=value_pct,
                model_ml_excluded=model_ml_excluded,
                pin_ml_excluded=pin_ml_excluded,
                model_market_gap_excluded=model_market_gap_excluded,
                atp500_short_favorite_ml_excluded=atp500_short_favorite_ml_excluded,
                heavy_favorite_dog_excluded=heavy_favorite_dog_excluded,
            )
            if skip_reason:
                clay_bo3_nearmiss_rows.append(
                    {
                        "date": snapshot_date_used,
                        "time_utc": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                        "player1": p1_name,
                        "player2": p2_name,
                        "surface": surface,
                        "league": league,
                        "series": series_bucket,
                        "confidence": confidence,
                        "side": side,
                        "value_pct": round(value_pct, 2) if value_pct is not None else "",
                        "model_favorite_prob": round(model_favorite_prob, 4),
                        "pin_favorite_prob": round(max(pin_p1_no_vig, 1.0 - pin_p1_no_vig), 4),
                        "skip_reason": skip_reason,
                    }
                )
        if grass_bo3_requested and league == "ATP" and surface == "Grass" and not grass_bo3_ml_match:
            skip_reason = grass_bo3_skip_reason(
                scope_reason=grass_bo3_scope,
                speed_reason=grass_speed_reason,
                value_pct=value_pct,
                model_ml_excluded=model_ml_excluded,
                pin_ml_excluded=pin_ml_excluded,
                model_market_gap_excluded=model_market_gap_excluded,
                atp500_short_favorite_ml_excluded=atp500_short_favorite_ml_excluded,
                heavy_favorite_dog_excluded=heavy_favorite_dog_excluded,
                favorite_agreement=grass_bo3_favorite_agreement,
            )
            if skip_reason:
                grass_bo3_nearmiss_rows.append(
                    {
                        "date": snapshot_date_used,
                        "time_utc": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                        "player1": p1_name,
                        "player2": p2_name,
                        "surface": surface,
                        "league": league,
                        "series": series_bucket,
                        "confidence": confidence,
                        "side": side,
                        "value_pct": round(value_pct, 2) if value_pct is not None else "",
                        "model_favorite_side": model_favorite_side,
                        "pin_favorite_side": pin_favorite_side,
                        "model_favorite_prob": round(model_favorite_prob, 4),
                        "pin_favorite_prob": round(max(pin_p1_no_vig, 1.0 - pin_p1_no_vig), 4),
                        "favorite_agreement": grass_bo3_favorite_agreement,
                        "grass_cpi": round(grass_cpi, 3) if grass_cpi is not None else "",
                        "grass_cpi_year": grass_cpi_year or "",
                        "grass_cpi_key": grass_cpi_key,
                        "grass_cpi_mode": grass_cpi_mode,
                        "grass_speed_tier": grass_speed_tier,
                        "grass_cpi_gate_min": GRASS_BO3_SLOW_CPI_MAX if GRASS_BO3_FAST_CPI_GATE else "",
                        "grass_cpi_slow_max": GRASS_BO3_SLOW_CPI_MAX if GRASS_BO3_FAST_CPI_GATE else "",
                        "grass_cpi_fast_min": GRASS_BO3_FAST_CPI_MIN if GRASS_BO3_FAST_CPI_GATE else "",
                        "grass_cpi_lag_years": GRASS_BO3_CPI_LAG_YEARS if GRASS_BO3_FAST_CPI_GATE else "",
                        "skip_reason": skip_reason,
                    }
                )
        if challenger_ml_requested and league == "Challenger" and not challenger_ml_match:
            skip_reason = challenger_skip_reason(
                coverage_tag=challenger_coverage_tag,
                confidence=confidence,
                surface=surface,
                value_pct=value_pct,
                model_ml_excluded=model_ml_excluded,
                pin_ml_excluded=pin_ml_excluded,
                model_market_gap_excluded=model_market_gap_excluded,
                atp500_short_favorite_ml_excluded=atp500_short_favorite_ml_excluded,
            )
            if skip_reason:
                challenger_nearmiss_rows.append(
                    {
                        "date": snapshot_date_used,
                        "time_utc": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                        "player1": p1_name,
                        "player2": p2_name,
                        "surface": surface,
                        "league": league,
                        "series": series_bucket,
                        **challenger_fields,
                        "confidence": confidence,
                        "side": side,
                        "value_pct": round(value_pct, 2) if value_pct is not None else "",
                        "skip_reason": skip_reason,
                    }
                )
        strict_spread_eligible = strict_min_value is not None
        volume_spread_eligible = (
            volume_min_value is not None
            and not strict_spread_eligible
            and args.signal_profile not in MATCH_ONLY_SIGNAL_PROFILES
            and args.signal_profile not in SPREAD_ONLY_SIGNAL_PROFILES
        )
        # spread_shadow lane targets clay/non-policy HC edges; those segments often have no
        # strict_min_value (non-policy). The API still shows them â€” do not drop the row here
        # or handicap rows never reach candidates (0/0 append forever).
        if not strict_match and not volume_match:
            if (
                not strict_spread_eligible
                and not volume_spread_eligible
                and not spread_shadow_eligible
                and not spread_v1_eligible
                and not clay_bo3_spread_eligible
                and not clay_calibrated_match
                and not challenger_ml_match
                and not clay_bo3_ml_match
                and not grass_bo3_ml_match
                and not cpi_speed_match
            ):
                continue
        bet_side = "fav" if side == fav_side else "dog"
        tname = tournament_name
        tkey = tour_key(tname)
        if args.signal_profile not in {"spread_shadow", *SPREAD_V1_SIGNAL_PROFILES} and (
            strict_match or volume_match or challenger_ml_match or clay_bo3_ml_match or grass_bo3_ml_match or cpi_speed_match
        ):
            stake_units, stake_gbp, stake_model = compute_stake_units(
                our_odds1=policy_odds1,
                our_odds2=policy_odds2,
                pin_odds1=pin["odds1"],
                pin_odds2=pin["odds2"],
                side=side,
                bet_type="match",
                value_pct=value_pct,
            )
            stake_units, stake_gbp, stake_model = apply_profile_stake_policy(
                args.signal_profile,
                stake_units,
                stake_gbp,
                stake_model,
            )

            candidates.append(
                {
                    "date": snapshot_date_used,
                    "time_utc": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                    "player1": p1_name,
                    "player2": p2_name,
                    "surface": surface,
                    "league": league,
                    "series": series_bucket,
                    "confidence": confidence,
                    **(challenger_fields if challenger_ml_match else {}),
                    "our_odds1": round(policy_odds1, 4),
                    "our_odds2": round(policy_odds2, 4),
                    "pin_odds1": round(pin["odds1"], 4),
                    "pin_odds2": round(pin["odds2"], 4),
                    "value_p1": round(value_p1, 2) if value_p1 is not None else None,
                    "value_p2": round(value_p2, 2) if value_p2 is not None else None,
                    "side": side,
                    "value_pct": round(value_pct, 2),
                    "stake_units": round(stake_units, 4),
                    "stake_gbp": round(stake_gbp, 2),
                    "stake_model": stake_model,
                    "bet_type": "match",
                    "policy_mode": "base",
                    "overlay_n": "",
                    "overlay_roi_pct_shrunk": "",
                    "overlay_reason": "",
                    "recent_injured_p1": p1_inj,
                    "recent_injured_p2": p2_inj,
                    "recent_injured_any": inj_any,
                    "recent_injured_p1_mode": p1_inj_mode,
                    "recent_injured_p2_mode": p2_inj_mode,
                    "grass_cpi": round(grass_cpi, 3) if grass_bo3_ml_match and grass_cpi is not None else "",
                    "grass_cpi_year": grass_cpi_year if grass_bo3_ml_match and grass_cpi_year is not None else "",
                    "grass_cpi_key": grass_cpi_key if grass_bo3_ml_match else "",
                    "grass_cpi_mode": grass_cpi_mode if grass_bo3_ml_match else "",
                    "grass_speed_tier": grass_speed_tier if grass_bo3_ml_match else "",
                    "grass_cpi_gate_min": GRASS_BO3_SLOW_CPI_MAX if grass_bo3_ml_match and GRASS_BO3_FAST_CPI_GATE else "",
                    "grass_cpi_slow_max": GRASS_BO3_SLOW_CPI_MAX if grass_bo3_ml_match and GRASS_BO3_FAST_CPI_GATE else "",
                    "grass_cpi_fast_min": GRASS_BO3_FAST_CPI_MIN if grass_bo3_ml_match and GRASS_BO3_FAST_CPI_GATE else "",
                    "grass_cpi_lag_years": GRASS_BO3_CPI_LAG_YEARS if grass_bo3_ml_match and GRASS_BO3_FAST_CPI_GATE else "",
                    "cpi_speed_cpi": round(cpi_speed_cpi, 3) if cpi_speed_match and cpi_speed_cpi is not None else "",
                    "cpi_speed_year": cpi_speed_year if cpi_speed_match and cpi_speed_year is not None else "",
                    "cpi_speed_z": round(cpi_speed_z, 3) if cpi_speed_match and cpi_speed_z is not None else "",
                    "cpi_speed_bucket": cpi_speed_bucket_value if cpi_speed_match else "",
                    "cpi_speed_key": cpi_speed_key if cpi_speed_match else "",
                    "cpi_speed_mode": cpi_speed_mode if cpi_speed_match else "",
                    "cpi_speed_gate": cpi_speed_gate_label if cpi_speed_match else "",
                    "cpi_speed_lag_years": CPI_SPEED_CPI_LAG_YEARS if cpi_speed_match else "",
                    "_bet_side": bet_side,
                    "_tournament_key": tkey,
                    "_tournament_name": tname,
                    "_strict_match": strict_match,
                    "_volume_match": volume_match,
                    "hard_calibration_live": hard_calibration_live_for_row,
                    "_challenger_ml_match": challenger_ml_match,
                    "_clay_bo3_match": clay_bo3_ml_match,
                    "_grass_bo3_match": grass_bo3_ml_match,
                    "_cpi_speed_match": cpi_speed_match,
                    "_spread_shadow_match": False,
                    "_spread_v1_match": False,
                    "shadow_reason": (
                        "cpi_speed_gate_passed"
                        if cpi_speed_match
                        else "grass_bo3_warmup_ml_fav_agreement_10_30"
                        if grass_bo3_ml_match
                        else "clay_bo3_ml_edge_5_13"
                        if clay_bo3_ml_match
                        else "challenger_ml_v2_prospective_high_coverage_10_15"
                        if challenger_ml_match
                        else ""
                    ),
                }
            )

        if clay_calibrated_match:
            stake_units_cal, stake_gbp_cal, stake_model_cal = compute_stake_units(
                our_odds1=calibrated_odds1,
                our_odds2=calibrated_odds2,
                pin_odds1=pin["odds1"],
                pin_odds2=pin["odds2"],
                side=calibrated_side,
                bet_type="match",
                value_pct=calibrated_value_pct,
            )
            candidates.append(
                {
                    "date": snapshot_date_used,
                    "time_utc": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                    "player1": p1_name,
                    "player2": p2_name,
                    "surface": surface,
                    "league": league,
                    "series": series_bucket,
                    "confidence": confidence,
                    "our_odds1": round(calibrated_odds1, 4),
                    "our_odds2": round(calibrated_odds2, 4),
                    "pin_odds1": round(pin["odds1"], 4),
                    "pin_odds2": round(pin["odds2"], 4),
                    "value_p1": round(calibrated_value_p1, 2) if calibrated_value_p1 is not None else None,
                    "value_p2": round(calibrated_value_p2, 2) if calibrated_value_p2 is not None else None,
                    "side": calibrated_side,
                    "value_pct": round(calibrated_value_pct, 2),
                    "stake_units": round(stake_units_cal, 4),
                    "stake_gbp": round(stake_gbp_cal, 2),
                    "stake_model": stake_model_cal,
                    "bet_type": "match",
                    "policy_mode": "base",
                    "overlay_n": "",
                    "overlay_roi_pct_shrunk": "",
                    "overlay_reason": "",
                    "recent_injured_p1": p1_inj,
                    "recent_injured_p2": p2_inj,
                    "recent_injured_any": inj_any,
                    "recent_injured_p1_mode": p1_inj_mode,
                    "recent_injured_p2_mode": p2_inj_mode,
                    "raw_p1_win_prob": round(p1_win_prob, 4),
                    "raw_p2_win_prob": round(p2_win_prob, 4),
                    "calibrated_p1_win_prob": round(calibrated_p1_win_prob, 4),
                    "calibrated_p2_win_prob": round(calibrated_p2_win_prob, 4),
                    "raw_odds1_shadow": round(our_odds1, 4),
                    "raw_odds2_shadow": round(our_odds2, 4),
                    "calibrated_odds1": round(calibrated_odds1, 4),
                    "calibrated_odds2": round(calibrated_odds2, 4),
                    "raw_value_p1": round(value_p1, 2) if value_p1 is not None else None,
                    "raw_value_p2": round(value_p2, 2) if value_p2 is not None else None,
                    "raw_value_same_side": round(raw_value_same_side, 2) if raw_value_same_side is not None else None,
                    "calibrated_selected_prob": round(calibrated_selected_prob, 4),
                    "calibration_new_edge": True,
                    "tournament_speed_signal": round(tournament_speed_signal, 4),
                    "clay_speed_tier": clay_speed_tier,
                    "_bet_side": "fav",
                    "_tournament_key": tkey,
                    "_tournament_name": tname,
                    "_strict_match": False,
                    "_volume_match": False,
                    "_clay_bo3_match": False,
                    "_spread_shadow_match": False,
                    "_spread_v1_match": False,
                    "_clay_calibrated_match": True,
                    "shadow_reason": "new_after_calibration_favorite_55_65",
                }
            )

        # Handicap signals: when handicap_edge >= 20% on P1+ or P2-
        # Keep them flat 1u and profile-gated the same way as match signals.
        profile_spread_eligible = (
            strict_spread_eligible
            or volume_spread_eligible
            or spread_shadow_eligible
            or spread_v1_eligible
            or clay_bo3_spread_eligible
        )
        if profile_spread_eligible and (
            spread_line is not None
            and spread_o1 is not None
            and spread_o2 is not None
            and he_p1 is not None
            and he_p2 is not None
            and handicap_shape_trusted
            and (
                not model_market_gap_excluded
                or args.signal_profile in SPREAD_V1_SIGNAL_PROFILES
                or clay_bo3_requested
            )
            and not inj_any
        ):
            edge_threshold = (
                SPREAD_SHADOW_MIN_EDGE_PCT
                if args.signal_profile == "spread_shadow"
                else CLAY_BO3_DOG_HC_MIN_EDGE_PCT
                if clay_bo3_requested
                else SPREAD_V1_CLAY_FAV_MIN_EDGE_PCT
                if spread_v1_clay_fav_requested
                else SPREAD_V1_MIN_EDGE_PCT
                if spread_v1_requested
                else HANDICAP_MIN_EDGE_PCT
            )
            short_fav_dog_spread_p1_guarded = is_short_favorite_dog_spread_guarded(
                "P1+",
                sl,
                model_ml_excluded,
                pin_ml_excluded,
            )
            short_fav_dog_spread_p2_guarded = is_short_favorite_dog_spread_guarded(
                "P2-",
                sl,
                model_ml_excluded,
                pin_ml_excluded,
            )
            spread_v1_segment_p1_guarded = is_spread_v1_segment_guarded("P1+", sl)
            spread_v1_segment_p2_guarded = is_spread_v1_segment_guarded("P2-", sl)
            spread_v1_max_edge = SPREAD_V1_CLAY_FAV_MAX_EDGE_PCT if spread_v1_clay_fav_requested else SPREAD_V1_MAX_EDGE_PCT
            spread_v1_p1_edge_guarded = spread_v1_requested and he1 > spread_v1_max_edge
            spread_v1_p2_edge_guarded = spread_v1_requested and he2 > spread_v1_max_edge
            clay_bo3_p1_edge_guarded = clay_bo3_requested and he1 > CLAY_BO3_DOG_HC_MAX_EDGE_PCT
            clay_bo3_p2_edge_guarded = clay_bo3_requested and he2 > CLAY_BO3_DOG_HC_MAX_EDGE_PCT
            clay_bo3_p1_dog_side = our_odds1 > our_odds2
            clay_bo3_p2_dog_side = our_odds2 > our_odds1
            clay_bo3_p1_allowed = (
                not clay_bo3_requested
                or (
                    clay_bo3_p1_dog_side
                    and not clay_bo3_p1_edge_guarded
                    and not short_fav_dog_spread_p1_guarded
                )
            )
            clay_bo3_p2_allowed = (
                not clay_bo3_requested
                or (
                    clay_bo3_p2_dog_side
                    and not clay_bo3_p2_edge_guarded
                    and not short_fav_dog_spread_p2_guarded
                )
            )
            spread_v1_p1_allowed = (
                not spread_v1_requested
                or (
                    not spread_v1_segment_p1_guarded
                    and
                    not short_fav_dog_spread_p1_guarded
                    and not spread_v1_p1_edge_guarded
                    and not is_excluded_heavy_favorite_dog(
                        surface,
                        series_bucket,
                        model_favorite_prob,
                        "P1",
                        model_favorite_side,
                    )
                )
            )
            spread_v1_p2_allowed = (
                not spread_v1_requested
                or (
                    not spread_v1_segment_p2_guarded
                    and
                    not short_fav_dog_spread_p2_guarded
                    and not spread_v1_p2_edge_guarded
                    and not is_excluded_heavy_favorite_dog(
                        surface,
                        series_bucket,
                        model_favorite_prob,
                        "P2",
                        model_favorite_side,
                    )
                )
            )
            shadow_reason_value = (
                spread_shadow_reason
                if args.signal_profile == "spread_shadow"
                else "clay_bo3_dog_handicap_edge_6_25"
                if clay_bo3_requested
                else "clay_favorite_handicap_2_3_5_edge_8_18"
                if spread_v1_clay_fav_requested
                else "strict_first_atp_bo3_hard_clay"
                if spread_v1_requested
                else ""
            )
            calibration_reason = spread_v1_calibration_status.get("reason", "")
            calibration_source = spread_v1_calibration_status.get("line_source_used", "")
            if he1 >= edge_threshold and spread_v1_p1_allowed and clay_bo3_p1_allowed:
                stake_units_h1, stake_gbp_h1, stake_model_h1 = compute_stake_units(
                    our_odds1=our_odds1,
                    our_odds2=our_odds2,
                    pin_odds1=pin["odds1"],
                    pin_odds2=pin["odds2"],
                    side="P1+",
                    bet_type="spread",
                )
                candidates.append(
                    {
                        "date": snapshot_date_used,
                        "time_utc": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                        "player1": p1_name,
                        "player2": p2_name,
                        "surface": surface,
                        "league": league,
                        "series": series_bucket,
                        "confidence": confidence,
                        "our_odds1": "",
                        "our_odds2": "",
                        "pin_odds1": round(so1, 4),
                        "pin_odds2": round(so2, 4),
                        "value_p1": round(he1, 2),
                        "value_p2": round(he2, 2),
                        "side": "P1+",
                        "value_pct": round(he1, 2),
                        "stake_units": round(stake_units_h1, 4),
                        "stake_gbp": round(stake_gbp_h1, 2),
                        "stake_model": stake_model_h1,
                        "bet_type": "spread",
                        "spread_line": round(sl, 1),
                        "spread_odds": round(so1, 4),
                        "policy_mode": "base",
                        "overlay_n": "",
                        "overlay_roi_pct_shrunk": "",
                        "overlay_reason": "",
                        "recent_injured_p1": p1_inj,
                        "recent_injured_p2": p2_inj,
                        "recent_injured_any": False,
                        "recent_injured_p1_mode": p1_inj_mode,
                        "recent_injured_p2_mode": p2_inj_mode,
                        "_bet_side": "dog" if our_odds1 > our_odds2 else "fav",
                        "_tournament_key": tkey,
                        "_tournament_name": tname,
                        "_strict_match": strict_spread_eligible,
                        "_volume_match": volume_spread_eligible,
                        "_clay_bo3_match": clay_bo3_spread_eligible,
                        "_spread_shadow_match": spread_shadow_eligible,
                        "_spread_v1_match": spread_v1_eligible,
                        "shadow_reason": shadow_reason_value or "",
                        "spread_calibration_reason": calibration_reason,
                        "spread_calibration_source": calibration_source,
                        "spread_surface_scope": surface if spread_v1_eligible else "",
                        "ml_short_fav_model_guard": model_ml_excluded,
                        "ml_short_fav_market_guard": pin_ml_excluded,
                        "ml_model_market_gap_guard": model_market_gap_excluded,
                        "atp500_short_fav_ml_guard": atp500_short_favorite_ml_excluded,
                        "short_fav_dog_spread_guard": short_fav_dog_spread_p1_guarded,
                        "spread_v1_max_edge_guard": spread_v1_p1_edge_guarded,
                        "clay_bo3_dog_side": clay_bo3_p1_dog_side if clay_bo3_requested else "",
                        "clay_bo3_max_edge_guard": clay_bo3_p1_edge_guarded if clay_bo3_requested else "",
                    }
                )
            if he2 >= edge_threshold and spread_v1_p2_allowed and clay_bo3_p2_allowed:
                stake_units_h2, stake_gbp_h2, stake_model_h2 = compute_stake_units(
                    our_odds1=our_odds1,
                    our_odds2=our_odds2,
                    pin_odds1=pin["odds1"],
                    pin_odds2=pin["odds2"],
                    side="P2-",
                    bet_type="spread",
                )
                candidates.append(
                    {
                        "date": snapshot_date_used,
                        "time_utc": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                        "player1": p1_name,
                        "player2": p2_name,
                        "surface": surface,
                        "league": league,
                        "series": series_bucket,
                        "confidence": confidence,
                        "our_odds1": "",
                        "our_odds2": "",
                        "pin_odds1": round(so1, 4),
                        "pin_odds2": round(so2, 4),
                        "value_p1": round(he1, 2),
                        "value_p2": round(he2, 2),
                        "side": "P2-",
                        "value_pct": round(he2, 2),
                        "stake_units": round(stake_units_h2, 4),
                        "stake_gbp": round(stake_gbp_h2, 2),
                        "stake_model": stake_model_h2,
                        "bet_type": "spread",
                        "spread_line": round(sl, 1),
                        "spread_odds": round(so2, 4),
                        "policy_mode": "base",
                        "overlay_n": "",
                        "overlay_roi_pct_shrunk": "",
                        "overlay_reason": "",
                        "recent_injured_p1": p1_inj,
                        "recent_injured_p2": p2_inj,
                        "recent_injured_any": False,
                        "recent_injured_p1_mode": p1_inj_mode,
                        "recent_injured_p2_mode": p2_inj_mode,
                        "_bet_side": "dog" if our_odds2 > our_odds1 else "fav",
                        "_tournament_key": tkey,
                        "_tournament_name": tname,
                        "_strict_match": strict_spread_eligible,
                        "_volume_match": volume_spread_eligible,
                        "_clay_bo3_match": clay_bo3_spread_eligible,
                        "_spread_shadow_match": spread_shadow_eligible,
                        "_spread_v1_match": spread_v1_eligible,
                        "shadow_reason": shadow_reason_value or "",
                        "spread_calibration_reason": calibration_reason,
                        "spread_calibration_source": calibration_source,
                        "spread_surface_scope": surface if spread_v1_eligible else "",
                        "ml_short_fav_model_guard": model_ml_excluded,
                        "ml_short_fav_market_guard": pin_ml_excluded,
                        "ml_model_market_gap_guard": model_market_gap_excluded,
                        "atp500_short_fav_ml_guard": atp500_short_favorite_ml_excluded,
                        "short_fav_dog_spread_guard": short_fav_dog_spread_p2_guarded,
                        "spread_v1_max_edge_guard": spread_v1_p2_edge_guarded,
                        "clay_bo3_dog_side": clay_bo3_p2_dog_side if clay_bo3_requested else "",
                        "clay_bo3_max_edge_guard": clay_bo3_p2_edge_guarded if clay_bo3_requested else "",
                    }
                )

    overlay_lookup: dict[tuple[int, str, str], dict[str, float]] = {}
    overlay_years: dict[tuple[str, str], list[int]] = {}
    if args.signal_profile == "strict" and (args.policy_mode == "overlay" or args.compare_overlay):
        overlay_lookup, overlay_years = load_overlay_policy(
            Path(args.overlay_policy_file),
            window_type=args.overlay_window,
            segment_family=args.overlay_family,
        )

    if args.signal_profile == "strict":
        profile_key = "_strict_match"
    elif args.signal_profile == "spread_shadow":
        profile_key = "_spread_shadow_match"
    elif args.signal_profile in SPREAD_V1_SIGNAL_PROFILES:
        profile_key = "_spread_v1_match"
    elif args.signal_profile == "challenger_ml_shadow":
        profile_key = "_challenger_ml_match"
    elif args.signal_profile == "clay_bo3":
        profile_key = "_clay_bo3_match"
    elif args.signal_profile == "grass_bo3":
        profile_key = "_grass_bo3_match"
    elif args.signal_profile == "cpi_speed_shadow":
        profile_key = "_cpi_speed_match"
    elif args.signal_profile == "clay_calibrated":
        profile_key = "_clay_calibrated_match"
    else:
        profile_key = "_volume_match"
    profile_candidates = [x for x in candidates if x.get(profile_key)]
    base_signals: list[dict[str, Any]] = [dict(x) for x in profile_candidates]
    overlay_signals: list[dict[str, Any]] = []
    overlay_skips = Counter()
    for s in profile_candidates:
        if s.get("bet_type") == "spread":
            row = dict(s)
            row["policy_mode"] = "overlay" if args.policy_mode == "overlay" else "base"
            row["overlay_reason"] = "spread_only"
            overlay_signals.append(row)
            continue
        pol, resolved_tkey, resolved_year, match_mode = resolve_overlay_policy(
            season_year=season_year,
            tournament_name=(s.get("_tournament_name") or ""),
            bet_side=(s.get("_bet_side") or ""),
            overlay_lookup=overlay_lookup,
            overlay_years=overlay_years,
        )
        if pol is None:
            if args.overlay_missing_mode == "skip":
                overlay_skips["missing"] += 1
                continue
            n_val = ""
            roi_val = ""
            reason = "missing_allow"
        else:
            n_val = round(float(pol.get("n", 0.0)), 2)
            roi_val = round(float(pol.get("roi_pct_shrunk", 0.0)), 4)
            if float(pol.get("n", 0.0)) < float(args.overlay_min_n):
                overlay_skips["min_n"] += 1
                continue
            if float(pol.get("roi_pct_shrunk", 0.0)) < float(args.overlay_min_roi_pct):
                overlay_skips["min_roi"] += 1
                continue
            reason = "ok" if match_mode == "exact" else f"ok_{match_mode}_{resolved_year}"

        row = dict(s)
        row["policy_mode"] = "overlay"
        row["overlay_n"] = n_val
        row["overlay_roi_pct_shrunk"] = roi_val
        row["overlay_reason"] = reason
        row["overlay_tournament_key"] = resolved_tkey
        row["overlay_resolved_year"] = "" if resolved_year is None else str(resolved_year)
        overlay_signals.append(row)

    base_signals = collapse_duplicate_spread_signals(base_signals)
    overlay_signals = collapse_duplicate_spread_signals(overlay_signals)
    signals = overlay_signals if args.policy_mode == "overlay" else base_signals
    if args.signal_profile == "strict":
        for s in signals:
            s["threshold_tier"] = "public" if (s.get("value_pct") or 0) >= STRICT_MIN_VALUE_PCT else "internal"
            s["signal_profile"] = "strict"
        public_signals = [s for s in signals if (s.get("value_pct") or 0) >= STRICT_MIN_VALUE_PCT]
        internal_signals = signals  # All 5%+ for confirmation tracking
    elif args.signal_profile == "spread_shadow":
        for s in signals:
            s["threshold_tier"] = "profile"
            s["signal_profile"] = "spread_shadow"
        public_signals = signals
        internal_signals = []
    elif args.signal_profile in SPREAD_V1_SIGNAL_PROFILES:
        for s in signals:
            s["threshold_tier"] = "profile"
            s["signal_profile"] = args.signal_profile
        public_signals = signals
        internal_signals = []
    else:
        for s in signals:
            s["threshold_tier"] = "profile"
            s["signal_profile"] = args.signal_profile
        public_signals = signals
        internal_signals = signals

    public_ml_count = sum(1 for s in public_signals if (s.get("bet_type") or "match") != "spread")
    public_spread_count = sum(1 for s in public_signals if (s.get("bet_type") or "") == "spread")

    print(f"Strict policy report - {today} UTC")
    if args.signal_profile == "strict":
        print(
            f"Profile: strict  |  Segment: {ALLOWED_SEGMENT}  |  "
            f"Confidence: {', '.join(sorted(ALLOWED_CONFIDENCE))}  |  "
            f"Public: >={STRICT_MIN_VALUE_PCT}%  |  Internal: >={INTERNAL_TRACK_MIN_VALUE_PCT}%  |  "
            f"Handicap: >={HANDICAP_MIN_EDGE_PCT}%"
        )
    else:
        print(f"Profile: {args.signal_profile}  |  {SHADOW_PROFILE_LABELS.get(args.signal_profile, args.signal_profile)}")
        if args.signal_profile in SPREAD_V1_SIGNAL_PROFILES:
            print(
                "Spread v1 calibration: "
                f"{'ready' if spread_v1_calibration_status.get('valid') else 'off'}  |  "
                f"reason={spread_v1_calibration_status.get('reason', '')}  |  "
                f"line_source={spread_v1_calibration_status.get('line_source_used', '') or 'n/a'}  |  "
                f"path={args.spread_v1_calibration_file}"
            )
            if spread_v1_calibration_status.get("warning"):
                print(f"Spread v1 calibration warning: {spread_v1_calibration_status['warning']}")
            if args.signal_profile == "spread_v1_clay_fav":
                print(
                    f"Spread v1 clay-fav edge window: {SPREAD_V1_CLAY_FAV_MIN_EDGE_PCT:.1f}%"
                    f" to {SPREAD_V1_CLAY_FAV_MAX_EDGE_PCT:.1f}%"
                    " | line 2.0-3.5 | fav side only"
                )
            else:
                print(
                    f"Spread v1 edge window: {SPREAD_V1_MIN_EDGE_PCT:.1f}%"
                    f" to {SPREAD_V1_MAX_EDGE_PCT:.1f}%"
                )
        if args.signal_profile == "challenger_ml_shadow":
            print(
                "Challenger ML gate: "
                f"enabled={CHALLENGER_ML_ENABLE} | "
                f"coverage={CHALLENGER_ML_REQUIRE_COVERAGE_TAG} | "
                f"confidence={','.join(sorted(CHALLENGER_ML_ALLOWED_CONFIDENCE))} | "
                f"edge {CHALLENGER_ML_MIN_EDGE_PCT:.1f}-{CHALLENGER_ML_MAX_EDGE_PCT:.1f}%"
            )
        if args.signal_profile == "clay_bo3":
            print(
                "Clay bo3 gate: "
                f"ML enabled={CLAY_BO3_ML_ENABLE} edge {CLAY_BO3_MIN_EDGE_PCT:.1f}-{CLAY_BO3_MAX_EDGE_PCT:.1f}% | "
                f"dog HC edge {CLAY_BO3_DOG_HC_MIN_EDGE_PCT:.1f}-{CLAY_BO3_DOG_HC_MAX_EDGE_PCT:.1f}% | "
                f"confidence={','.join(sorted(CLAY_BO3_ALLOWED_CONFIDENCE))}"
            )
        if args.signal_profile == "grass_bo3":
            print(
                "Grass bo3 gate: "
                f"ATP warm-ups only ({','.join(sorted(GRASS_BO3_ALLOWED_SERIES))}) | "
                f"ML edge {GRASS_BO3_MIN_EDGE_PCT:.1f}-{GRASS_BO3_MAX_EDGE_PCT:.1f}% | "
                f"confidence={','.join(sorted(GRASS_BO3_ALLOWED_CONFIDENCE))} | "
                f"favorite_agreement_required={GRASS_BO3_REQUIRE_FAV_AGREEMENT} | "
                f"cpi_gate={GRASS_BO3_FAST_CPI_GATE} lag_only={GRASS_BO3_CPI_LAG_ONLY} "
                f"lag_years={GRASS_BO3_CPI_LAG_YEARS} slow<{GRASS_BO3_SLOW_CPI_MAX:.2f} "
                f"fast>={GRASS_BO3_FAST_CPI_MIN:.2f}"
            )
        if args.signal_profile == "cpi_speed_shadow":
            print(
                "CPI speed shadow gate: "
                f"ATP only | ML edge {CPI_SPEED_MIN_EDGE_PCT:.1f}-{CPI_SPEED_MAX_EDGE_PCT:.1f}% | "
                f"confidence={','.join(sorted(CPI_SPEED_ALLOWED_CONFIDENCE))} | "
                f"PASS gates={len(cpi_speed_pass_gates)} | "
                f"lag_only={CPI_SPEED_CPI_LAG_ONLY} lag_years={CPI_SPEED_CPI_LAG_YEARS} | "
                f"slow_z<={CPI_SPEED_Z_SLOW:+.2f} fast_z>={CPI_SPEED_Z_FAST:+.2f}"
            )
    print(
        "Stake sizing: "
        f"match 1u flat; spread 2u flat; unit_gbp={STRICT_UNIT_GBP:.2f}"
    )
    if EXCLUDE_ATP500_HARD_SHORT_FAVORITES:
        print(
            "Exclusion: ATP500 Hard short-favourite MLs skipped "
            f"(confidence {', '.join(sorted(EXCLUDE_SHORT_FAV_CONFIDENCE))}, favorite odds < {EXCLUDE_SHORT_FAV_MAX_ODDS:.2f}); spreads remain eligible"
        )
    print(f"Production mode: {args.policy_mode}  |  signal_profile={args.signal_profile}")
    if args.signal_profile == "strict":
        print(f"Signals (public >={STRICT_MIN_VALUE_PCT}%): {len(public_signals)}  |  Internal (5%+): {len(internal_signals)}")
    else:
        print(f"Signals (profile-qualified): {len(public_signals)}")
    print(f"Breakdown: ML={public_ml_count}  |  Spread={public_spread_count}")
    print(
        "Injury list: "
        f"path={Path(args.injury_csv)} recent_rows={injury_index.rows_recent}/{injury_index.rows_loaded} "
        f"lookback={args.injury_lookback_days}d "
        f"flagged_candidates={injury_flagged_matches} "
        f"overlay={'on' if args.injury_overlay_enabled else 'off'} "
        f"skipped={injury_skipped_matches}"
    )

    if args.signal_profile == "strict" and (args.policy_mode == "overlay" or args.compare_overlay):
        print(
            "Overlay config: "
            f"window={args.overlay_window} family={args.overlay_family} "
            f"min_n={args.overlay_min_n} min_roi_pct={args.overlay_min_roi_pct:+.2f} "
            f"missing={args.overlay_missing_mode} keys={len(overlay_lookup)} key_side={len(overlay_years)}"
        )
        print(f"Overlay pass count: {len(overlay_signals)} / {len(profile_candidates)}  skip_reasons={dict(overlay_skips)}")
    if args.signal_profile == "strict" and args.compare_overlay:
        print(f"Compare mode: base={len(base_signals)} overlay={len(overlay_signals)}")
    print()

    if not public_signals:
        print("No POLICY signals today (public threshold).")
    else:
        for s in public_signals:
            bt = s.get("bet_type") or "match"
            if bt == "spread":
                sl_raw = s.get("spread_line")
                sl_val = float(sl_raw) if sl_raw not in ("", None) else None
                display_line = sl_val if s.get("side") == "P1+" else (-sl_val if sl_val is not None else None)
                so = s.get("spread_odds", "")
                guard_note = "  [ML-guarded]" if s.get("ml_model_market_gap_guard") else ""
                print(
                    f"  {s['player1']} vs {s['player2']}  |  "
                    f"{s['side']} ({format_signed_line(display_line)}) edge {s['value_pct']:+.1f}%  |  odds {so}{guard_note}"
                )
            else:
                print(
                    f"  {s['player1']} vs {s['player2']}  |  {s['side']} value {s['value_pct']:+.1f}%  |  "
                    f"our {s['our_odds1']:.2f}/{s['our_odds2']:.2f}  Pin {s['pin_odds1']:.2f}/{s['pin_odds2']:.2f}"
                )

    # Remove internal keys before CSV writes.
    for row_set in (signals, base_signals, overlay_signals):
        for r in row_set:
            r.pop("_bet_side", None)
            r.pop("_tournament_key", None)
            r.pop("_tournament_name", None)
            r.pop("_strict_match", None)
            r.pop("_volume_match", None)
            r.pop("_challenger_ml_match", None)
            r.pop("_clay_bo3_match", None)
            r.pop("_grass_bo3_match", None)
            r.pop("_cpi_speed_match", None)
            r.pop("_spread_shadow_match", None)
            r.pop("_spread_v1_match", None)
            r.pop("_clay_calibrated_match", None)

    if args.append:
        # One logical spread pick per fixture/side/lane. Alternate handicap
        # lines and odds refreshes are quote updates, not extra bets.
        live_dedup_fields = SPREAD_LOGICAL_KEY_FIELDS
        lane_key_fields = SPREAD_LOGICAL_KEY_FIELDS
        archive_key_fields = SPREAD_LOGICAL_KEY_FIELDS
        out_paths = derive_signal_csv_paths(Path(args.output))
        live_count = write_live_snapshot(
            out_paths.live,
            public_signals,
            dedup_key_fields=live_dedup_fields,
            lane_key_fields=lane_key_fields,
        )
        archive_added = append_rows_dedup(
            out_paths.archive,
            public_signals,
            key_fields=archive_key_fields,
        )
        mirror_live_snapshot(out_paths)
        print(
            f"\nWrote {live_count}/{len(public_signals)} public live rows to {out_paths.live} "
            f"and appended {archive_added} archive rows to {out_paths.archive}."
        )

        if args.internal_output:
            internal_paths = derive_signal_csv_paths(Path(args.internal_output))
            live_internal_count = write_live_snapshot(
                internal_paths.live,
                internal_signals,
                dedup_key_fields=live_dedup_fields,
                lane_key_fields=lane_key_fields,
            )
            internal_archive_added = append_rows_dedup(
                internal_paths.archive,
                internal_signals,
                key_fields=archive_key_fields,
            )
            mirror_live_snapshot(internal_paths)
            if args.signal_profile == "strict":
                print(
                    f"Wrote {live_internal_count}/{len(internal_signals)} internal live rows to {internal_paths.live} "
                    f"and appended {internal_archive_added} internal archive rows to {internal_paths.archive}."
                )
            else:
                print(
                    f"Wrote {live_internal_count}/{len(internal_signals)} profile live rows to {internal_paths.live} "
                    f"and appended {internal_archive_added} archive rows to {internal_paths.archive}."
                )

        if args.signal_profile == "strict" and args.compare_overlay:
            compare_rows = base_signals + overlay_signals
            compare_path = Path(args.compare_output)
            added_cmp = append_rows_dedup(
                compare_path,
                compare_rows,
                key_fields=["date", "time_utc", "player1", "player2", "bet_type", "side", "spread_line", "policy_mode", "signal_profile"],
            )
            print(f"Appended {added_cmp}/{len(compare_rows)} comparison rows to {compare_path} (deduped).")
        if args.signal_profile == "challenger_ml_shadow":
            nearmiss_added = append_rows_dedup(
                CHALLENGER_ML_NEARMISS_PATH,
                challenger_nearmiss_rows,
                key_fields=["date", "player1", "player2", "skip_reason"],
            )
            print(
                f"Appended {nearmiss_added}/{len(challenger_nearmiss_rows)} Challenger near-miss rows "
                f"to {CHALLENGER_ML_NEARMISS_PATH}."
            )
        if args.signal_profile == "clay_bo3":
            nearmiss_added = append_rows_dedup(
                CLAY_BO3_NEARMISS_PATH,
                clay_bo3_nearmiss_rows,
                key_fields=["date", "player1", "player2", "skip_reason"],
            )
            print(
                f"Appended {nearmiss_added}/{len(clay_bo3_nearmiss_rows)} Clay bo3 near-miss rows "
                f"to {CLAY_BO3_NEARMISS_PATH}."
            )
        if args.signal_profile == "grass_bo3":
            nearmiss_added = append_rows_dedup(
                GRASS_BO3_NEARMISS_PATH,
                grass_bo3_nearmiss_rows,
                key_fields=["date", "player1", "player2", "skip_reason"],
            )
            print(
                f"Appended {nearmiss_added}/{len(grass_bo3_nearmiss_rows)} Grass bo3 near-miss rows "
                f"to {GRASS_BO3_NEARMISS_PATH}."
            )
        if args.signal_profile == "cpi_speed_shadow":
            nearmiss_added = append_rows_dedup(
                CPI_SPEED_NEARMISS_PATH,
                cpi_speed_nearmiss_rows,
                key_fields=["date", "player1", "player2", "skip_reason"],
            )
            print(
                f"Appended {nearmiss_added}/{len(cpi_speed_nearmiss_rows)} CPI speed near-miss rows "
                f"to {CPI_SPEED_NEARMISS_PATH}."
            )
        write_signals_current_artifact()
        print(f"Updated signals artifact at {SIGNALS_CURRENT_JSON}.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
