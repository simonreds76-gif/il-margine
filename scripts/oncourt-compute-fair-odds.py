"""
Phase 4: Compute fair odds for today's matches (hold%/return% + Elo hybrid).
Reads today's fixtures from Supabase, fetches player_surface_stats and player_elo,
computes p_A/p_B -> P(serve/return) -> blend with P(Elo) -> fair odds.
Create table first: run docs/supabase-phase4-daily-fair-odds.sql in Supabase.
Run: python scripts/oncourt-compute-fair-odds.py [--dry-run] [--debug [name1,name2]]
  --debug [names]  Print Elo, stats, ATP rank and fair odds for fixtures matching names (default: Cerundolo). E.g. --debug Cerundolo,Rublev.
  WARNING: If two players share a surname (e.g. F. and J.M. Cerundolo), OnCourt today_atp must use the correct ID per match; otherwise we show wrong odds.
"""

import math
import os
import re
import subprocess
import sys
from datetime import date

# Project root for tennis_prob; scripts dir for matchup_model
_script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_script_dir, ".."))
sys.path.insert(0, _script_dir)
from src.lib.tennis_prob import (
    prob_match_best_of_3,
    prob_match_best_of_5,
    expected_total_games_best_of_3,
    expected_total_games_best_of_5,
    prob_over_games,
)
from injury_overlay import env_bool, load_recent_injury_index
from class_gap import apply_class_gap

# Matchup-aware p_a/p_b from decomposed serve stats (Path B)
try:
    from matchup_model import MatchupStats, compute_match_point_probs
    HAS_MATCHUP_MODEL = True
except ImportError:
    HAS_MATCHUP_MODEL = False

try:
    from live_model_v2 import LiveModelV2
    HAS_LIVE_V2 = True
except ImportError:
    HAS_LIVE_V2 = False

def load_env():
    base = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(base)
    for name in ["env.local", ".env.local"]:
        path = os.path.join(root, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip().replace("\r", "")
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        v = v.strip().strip('"').strip("'")
                        os.environ[k.strip()] = v

load_env()

# ─── CALIBRATION CONSTANTS (Codex full calibration pass) ───────────
HYBRID_ELO_WEIGHT_DEFAULT = 0.58
HYBRID_ELO_WEIGHT_MIN_MATCHES = 28
POINT_CLAMP = (0.42, 0.80)
RETURN_CLAMP = (0.20, 0.55)
DEFAULT_ELO = 1500
# Market-like half-point menu. We still publish 3 lines per match, centered on
# the model median, but draw from a broader realistic set.
STANDARD_OU_LINES = [x + 0.5 for x in range(18, 28)]  # 18.5 .. 27.5
# O/U calibration: model has been running high on totals; shift thresholds up
# when pricing P(over), equivalent to shifting our distribution left.
OU_LINE_SHIFT_BY_SURFACE = {"Hard": 2.6, "Clay": 2.9, "Grass": 1.8, "I.hard": 2.4, "N/A": 2.5}
OU_CHALLENGER_EXTRA_SHIFT = 0.35
OU_ATP_MAIN_TOUR_EXTRA_SHIFT = -0.15

VS_LEFTIE_WEIGHT = 0.03
VS_LEFTIE_CAP = 0.015
VS_BIG_SERVER_WEIGHT = 0.03
VS_BIG_SERVER_CAP = 0.015
BIG_SERVER_HOLD_PCT = 0.68
BLEND_RECENT_WEIGHT = 0.5

VENUE_WEIGHT = 0.025
VENUE_CAP = 0.015
ALTITUDE_WEIGHT = 0.03
ALTITUDE_CAP = 0.02
ALTITUDE_THRESHOLD_M = 200
AGE_CAP = 0.01

RANK_LOGIT_SCALE = 0.95
RANK_CLASS_GAP_RATIO_START = 1.40
RANK_CLASS_GAP_CAP = 0.07
RANK_POINTS_BLEND = 0.35
POINTS_LOGIT_SCALE = 1.25
POINTS_MIN_BASE = 5.0
SURFACE_RANK_CONFLICT_SURFACES = {"Clay", "Grass"}
SURFACE_RANK_CONFLICT_SERIES = {"Grand Slam", "Masters 1000", "ATP500"}
SURFACE_RANK_CONFLICT_MIN_SR_EDGE = 0.12
SURFACE_RANK_CONFLICT_MIN_SR_RANK_GAP = 0.32
SURFACE_RANK_CONFLICT_MAX_ELO_EDGE = 0.14
SURFACE_RANK_CONFLICT_RANK_TO_ANCHOR_RATIO = 0.10
SURFACE_RANK_CONFLICT_RELEASE_TO_SR = 1.00
SURFACE_POINTS_MISMATCH_SURFACES = {"Clay", "Grass"}
SURFACE_POINTS_MISMATCH_SERIES = {"Grand Slam", "Masters 1000", "ATP500"}
SURFACE_POINTS_MISMATCH_MIN_FAV_POINTS = 150.0
SURFACE_POINTS_MISMATCH_MAX_DOG_POINTS = 50.0
SURFACE_POINTS_MISMATCH_MIN_RATIO = 8.0
SURFACE_POINTS_MISMATCH_BLEND_BASE = 0.28
SURFACE_POINTS_MISMATCH_BLEND_CAP = 0.68

SHRINKAGE_N = 40
SURFACE_LEAGUE_AVG = {"Hard": 0.64, "Clay": 0.62, "Grass": 0.67, "I.hard": 0.64, "N/A": 0.64}

# Raw-scale priors from player_surface_stats distribution (fallbacks; overridden by DB-derived priors)
SURFACE_AVG_HOLD = {"Hard": 0.4342, "Clay": 0.4189, "Grass": 0.5053, "I.hard": 0.5099, "N/A": 0.44}
SURFACE_AVG_RETURN = {"Hard": 0.3467, "Clay": 0.3643, "Grass": 0.3166, "I.hard": 0.3413, "N/A": 0.35}

TOURNAMENT_TOTAL_WEIGHT = 0.20
TOURNAMENT_TOTAL_SHIFT_CAP = 1.5
MIN_TOUR_MATCHES_FOR_SHIFT = 30
MIN_VENUE_SPW_MATCHES = 50
SPEED_RATIO_CLAMP = (0.92, 1.08)
TOURNAMENT_SPEED_VENUE_COMPONENT_WEIGHT = 0.75
TOURNAMENT_SPEED_SHIFT_COMPONENT_WEIGHT = 0.25
TOURNAMENT_SPEED_VENUE_FULL_MATCHES = 150
TOURNAMENT_SPEED_SHIFT_FULL_MATCHES = 90
TOURNAMENT_SPEED_SHIFT_SIGNAL_SCALE = 2.0
DEFAULT_TOURNAMENT_SPEED_POINT_WEIGHT = 0.18

FORM_WEIGHT = 0.07
FORM_CAP = 0.03
FORM_MIN_MATCHES = 3
FATIGUE_PLAYED_YESTERDAY = 0.008
FATIGUE_DENSE_5D = 0.007
FATIGUE_MODERATE_COMPOUND = 0.004
FATIGUE_CAP = 0.015
RUST_THRESHOLD_MODERATE = 28
RUST_THRESHOLD_SEVERE = 42
RUST_PENALTY_MODERATE = 0.008
RUST_PENALTY_SEVERE = 0.015
RUST_CAP = 0.015
FORM_TOTAL_CAP = 0.05

# Explicit match-result form features (from oncourt_games)
RESULTS_LOOKBACK_YEARS = 5
YTD_FORM_MIN_MATCHES = 5
YTD_FORM_WEIGHT = 0.07
YTD_FORM_CAP = 0.03
LAST5_FORM_MIN_MATCHES = 3
LAST5_FORM_WEIGHT = 0.04
LAST5_FORM_CAP = 0.015
STREAK_SOFT_START = 3
STREAK_HARD_START = 6
STREAK_UNIT = 0.004
STREAK_CAP = 0.03
RESULTS_FORM_TOTAL_CAP = 0.08

# Same-edition tournament form. This is intentionally much smaller than the
# normal form layer: at a Slam everybody still alive has been winning, so we use
# score dominance, not raw W/L, and cap the effect hard.
CURRENT_TOURNAMENT_MIN_MATCHES = 1
CURRENT_TOURNAMENT_DOMINANCE_WEIGHT = 0.055
CURRENT_TOURNAMENT_CAP = 0.018

# Same-tournament history (past years by normalized tournament key)
TOURNAMENT_HISTORY_MIN_MATCHES = 2
TOURNAMENT_HISTORY_WEIGHT = 0.08
TOURNAMENT_HISTORY_CAP = 0.03
TOURNAMENT_HISTORY_PRIOR_K = 3.0
TOURNAMENT_HISTORY_PRIOR_P = 0.5

# Rank prior downweight when player is in form crisis
FORM_CRISIS_LOSS_STREAK = 4
FORM_CRISIS_YTD_MIN_MATCHES = 6
FORM_CRISIS_YTD_WINRATE_MAX = 0.30
RANK_WEIGHT_CRISIS_MULT = 0.25
RANK_WEIGHT_CRISIS_OPPOSED_MULT = 0.85
FORM_CRISIS_SHOCK_BASE = 0.020
FORM_CRISIS_SHOCK_STREAK_UNIT = 0.010
FORM_CRISIS_SHOCK_YTD_BONUS = 0.015
FORM_CRISIS_SHOCK_CAP = 0.070

# Allow larger adjustment when confidence is high
DELTA_CAP_HIGH = 0.14
DELTA_CAP_MEDIUM = 0.10
DELTA_CAP_LOW = 0.08
DELTA_COMPONENT_SUM_CAP_FACTOR = 0.60
DELTA_COMPONENT_SUM_CAP_MAX = 0.20

# H2H is a small structural nudge, not an override. Three completed meetings is
# enough to matter for matchup-specific pricing, while the cap prevents overfit.
H2H_MIN_MATCHES = 3
H2H_WEIGHT = 0.03
H2H_CAP = 0.02

ADV_MIN_MATCHES = 12
ADV_SERVE_MATCHUP_WEIGHT = 0.10
ADV_CLUTCH_WEIGHT = 0.05
ADV_DISCIPLINE_WEIGHT = 0.03
ADV_TOTAL_CAP = 0.015

INCLUDE_TOUR_RANK_MAX = 3

# PostgREST caps each request; today_atp often has 1500+ rows — a single limit=1000 drops later tours (e.g. Naples Challenger).
ONCOURT_TODAY_PAGE_SIZE = 1000
UNKNOWN_PLAYER_IDS = {3699, 3700}

ELO_RELIABILITY_MIN = 0.50
ELO_STALE_WEIGHT_CAP = 0.30
MISSING_ACTIVITY_BASE_PENALTY = 0.010
MISSING_ACTIVITY_AGE_START = 31
MISSING_ACTIVITY_AGE_WEIGHT = 0.0020
MISSING_ACTIVITY_PENALTY_CAP = 0.035
LOW_CONF_DOG_MIN_MATCHES = 6
LOW_CONF_DOG_ESTABLISHED_RANK = 120
LOW_CONF_DOG_ESTABLISHED_ELO = 1775
LOW_CONF_DOG_MODEL_ANCHOR_GAP = 0.04
LOW_CONF_DOG_BLEND_MIN = 0.45
LOW_CONF_DOG_BLEND_MAX = 0.85
ONE_SIDED_RANK_EVENT_MIN = 2.0
ONE_SIDED_RANK_BASE = 700
ONE_SIDED_RANK_EVENT_STEP = 250
ONE_SIDED_RANK_NO_EXPOSURE = 250
ONE_SIDED_RANK_THIN_EXPOSURE = 120
ONE_SIDED_RANK_RECENT_DEFICIT_UNIT = 250
ONE_SIDED_RANK_LOW_MATCH_BONUS = 80
ONE_SIDED_RANK_MED_MATCH_BONUS = 40
ONE_SIDED_RANK_LOW_CONF_BONUS = 120
ONE_SIDED_RANK_MEDIUM_CONF_BONUS = 60
ONE_SIDED_RANK_RECENT_NEAR_LEVEL_DISCOUNT = 120
ONE_SIDED_RANK_MULTI_MATCH_DISCOUNT = 80
ONE_SIDED_RANK_CAP = 2200
CLASS_JUMP_EVENT_MIN = 2.0
CLASS_JUMP_DEFICIT_ONSET = 0.55
CLASS_JUMP_ELO_PER_CLASS = 34.0
CLASS_JUMP_NO_EXPOSURE_BONUS = 34.0
CLASS_JUMP_THIN_EXPOSURE_BONUS = 16.0
CLASS_JUMP_LOW_CONF_BONUS = 16.0
CLASS_JUMP_MEDIUM_CONF_BONUS = 10.0
CLASS_JUMP_OPP_ESTABLISHED_BONUS = 10.0
CLASS_JUMP_LOW_MATCH_BONUS = 8.0
CLASS_JUMP_MAX_ELO = 120.0
CLASS_JUMP_SAMPLE_MULT_MIN = 0.18
CLASS_JUMP_ESTABLISHED_HIGH_MULT = 0.0
CLASS_JUMP_ESTABLISHED_MEDIUM_MULT = 0.35
CLASS_JUMP_ESTABLISHED_SAMPLE_MULT_MIN = 0.75
STEPUP_DOG_GUARD_EVENT_MIN = 2.0
STEPUP_DOG_GUARD_MIN_RECENT_DEFICIT = 0.75
STEPUP_DOG_GUARD_ANCHOR_GAP = 0.02
STEPUP_DOG_GUARD_BLEND_LOW = 0.36
STEPUP_DOG_GUARD_BLEND_MEDIUM = 0.24
STEPUP_DOG_GUARD_BLEND_MAX = 0.72

# Post-hoc probability calibration (fit on historical backtest; 2024 train).
# Favorite-space Platt transform blended by tour tier to avoid overcorrection
# on event classes where raw priors are already strong.
PROB_CAL_A = 0.173
PROB_CAL_B = 0.512
PROB_CAL_SERIES_BLEND = {
    "ATP250": 0.35,
    "Masters 1000": 1.00,
    "ATP500": 0.35,
    "Grand Slam": 0.00,
    "Masters Cup": 0.00,
}
SERIES_FAVORITE_PROB_CAP = {
    "ATP250": {"high": 0.89, "medium": 0.85, "low": 0.82},
    "ATP500": {"high": 0.91, "medium": 0.87, "low": 0.84},
    "Masters 1000": {"high": 0.93, "medium": 0.90, "low": 0.87},
    "Grand Slam": {"high": 0.95, "medium": 0.92, "low": 0.89},
    "Masters Cup": {"high": 0.94, "medium": 0.91, "low": 0.88},
    # Grass samples are sparse and recent holdout bins showed favourite overconfidence.
    "Grass": {"high": 0.87, "medium": 0.83, "low": 0.80},
    "Challenger": {"high": 0.84, "medium": 0.80, "low": 0.76},
}
CHALLENGER_ELO_WEIGHT_MULTIPLIER = {"high": 0.74, "medium": 0.66, "low": 0.58, "none": 0.58}
ELO_MAGNITUDE_GUARD_RANK_LOGIT_GAP = 1.5
ELO_MAGNITUDE_GUARD_SR_LOGIT_GAP = 1.0
ELO_MAGNITUDE_GUARD_MIN_DAMP = 0.50
CHALLENGER_CLASS_GAP_KWARGS = {
    "elo_gap_onset": 220,
    "elo_gap_full": 480,
    "rank_gap_onset": 60,
    "rank_gap_full": 180,
    "max_blend": 0.32,
}
SERIES_CLASS_GAP_KWARGS = {
    "Grand Slam": {
        "elo_gap_onset": 250,
        "elo_gap_full": 500,
        "rank_gap_onset": 50,
        "rank_gap_full": 150,
        "max_blend": 0.85,
    },
    "Masters Cup": {
        "elo_gap_onset": 250,
        "elo_gap_full": 500,
        "rank_gap_onset": 50,
        "rank_gap_full": 150,
        "max_blend": 0.85,
    },
    "Masters 1000": {
        "elo_gap_onset": 200,
        "elo_gap_full": 450,
        "rank_gap_onset": 40,
        "rank_gap_full": 130,
        "max_blend": 0.65,
    },
    "ATP500": {
        "elo_gap_onset": 220,
        "elo_gap_full": 450,
        "rank_gap_onset": 50,
        "rank_gap_full": 150,
        "max_blend": 0.50,
    },
    "ATP250": {
        "elo_gap_onset": 220,
        "elo_gap_full": 450,
        "rank_gap_onset": 50,
        "rank_gap_full": 150,
        "max_blend": 0.42,
    },
}
DEFAULT_INJURY_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "injured-players-tennisexplorer.csv",
)
DEFAULT_FAIR_ODDS_INJURY_LOOKBACK_DAYS = 14
DEFAULT_FAIR_ODDS_INJURY_DELTA = 0.02

# Optional tournament CPI (surface-speed) overlay from Tennis Abstract.
# Keep OFF by default and validate before enabling live.
DEFAULT_CPI_LOOKBACK_YEARS = 3
DEFAULT_CPI_MATCH_WEIGHT = 0.025
DEFAULT_CPI_MATCH_CAP = 0.012
DEFAULT_CPI_Z_CAP = 2.0
DEFAULT_CPI_TOTAL_RATIO_WEIGHT = 0.020
DEFAULT_CPI_TOTAL_RATIO_CLAMP = (0.95, 1.05)
DEFAULT_CPI_WITH_VENUE_BLEND = 0.20


def _float(v, default=None):
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def _age_years(birthdate_str):
    if not birthdate_str:
        return None
    try:
        bd = date.fromisoformat(str(birthdate_str).strip()[:10])
        return (date.today() - bd).days / 365.25
    except (ValueError, TypeError, IndexError):
        return None


def _age_factor(birthdate_str):
    """Small age modifier: prime ~22-30, mild decline after 30."""
    age = _age_years(birthdate_str)
    if age is None:
        return 0.0
    if age >= 30:
        return -0.004 * (age - 30)
    if age < 22:
        return 0.002 * (22 - age)
    return 0.0


def _solve_spw_for_match_prob(p1_win, avg_spw, clamp_lo=0.48, clamp_hi=0.82, tol=5e-4, max_iter=60, prob_fn=None):
    """Binary-search for (p_a, p_b) such that prob_fn(p_a, p_b) ≈ p1_win.

    prob_fn: prob_match_best_of_3 (default) or prob_match_best_of_5 for Grand Slams.
    Assumes symmetric offset from avg_spw: p_a = avg + delta, p_b = avg - delta.
    This preserves the surface's average serve point win % while producing the
    correct match win probability.

    Returns (p_a, p_b) clamped to [clamp_lo, clamp_hi].
    """
    if prob_fn is None:
        prob_fn = prob_match_best_of_3
    p1_win = max(0.02, min(0.98, p1_win))
    avg_spw = max(clamp_lo + 0.01, min(clamp_hi - 0.01, avg_spw))
    max_delta = min(avg_spw - clamp_lo, clamp_hi - avg_spw)
    lo, hi = -max_delta, max_delta
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        pa = max(clamp_lo, min(clamp_hi, avg_spw + mid))
        pb = max(clamp_lo, min(clamp_hi, avg_spw - mid))
        prob = prob_fn(pa, pb)
        if abs(prob - p1_win) < tol:
            return (pa, pb)
        if prob < p1_win:
            lo = mid
        else:
            hi = mid
    mid = (lo + hi) / 2.0
    return (max(clamp_lo, min(clamp_hi, avg_spw + mid)),
            max(clamp_lo, min(clamp_hi, avg_spw - mid)))


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _sample_scale(match_count, full_matches):
    if match_count is None:
        return 0.0
    if full_matches <= 0:
        return 1.0
    return _clamp(float(match_count) / float(full_matches), 0.0, 1.0)


def _compute_tournament_speed_signal(
    *,
    league_avg,
    venue_entry,
    tour_shift_entry,
):
    if league_avg is None or league_avg <= 0.0:
        return 0.0, {}

    parts = []
    debug = {
        "venue_spw": None,
        "venue_spw_matches": 0,
        "venue_ratio": None,
        "venue_signal": 0.0,
        "tour_shift": None,
        "tour_shift_matches": 0,
        "tour_shift_signal": 0.0,
    }

    speed_ratio_span = max(SPEED_RATIO_CLAMP[1] - 1.0, 1.0 - SPEED_RATIO_CLAMP[0], 1e-6)

    if venue_entry:
        venue_spw = _float(venue_entry.get("venue_avg_spw"))
        venue_n = int(venue_entry.get("match_count") or 0)
        if venue_spw is not None and venue_spw > 0.0:
            ratio = _clamp(venue_spw / league_avg, SPEED_RATIO_CLAMP[0], SPEED_RATIO_CLAMP[1])
            signal = _clamp((ratio - 1.0) / speed_ratio_span, -1.0, 1.0)
            weight = TOURNAMENT_SPEED_VENUE_COMPONENT_WEIGHT * _sample_scale(venue_n, TOURNAMENT_SPEED_VENUE_FULL_MATCHES)
            if weight > 0.0:
                parts.append((signal, weight))
            debug.update(
                {
                    "venue_spw": venue_spw,
                    "venue_spw_matches": venue_n,
                    "venue_ratio": ratio,
                    "venue_signal": signal,
                }
            )

    if tour_shift_entry:
        shift = _float(tour_shift_entry.get("shift_from_surface"))
        shift_n = int(tour_shift_entry.get("match_count") or 0)
        if shift is not None:
            signal = _clamp(shift / TOURNAMENT_SPEED_SHIFT_SIGNAL_SCALE, -1.0, 1.0)
            weight = TOURNAMENT_SPEED_SHIFT_COMPONENT_WEIGHT * _sample_scale(shift_n, TOURNAMENT_SPEED_SHIFT_FULL_MATCHES)
            if weight > 0.0:
                parts.append((signal, weight))
            debug.update(
                {
                    "tour_shift": shift,
                    "tour_shift_matches": shift_n,
                    "tour_shift_signal": signal,
                }
            )

    if not parts:
        return 0.0, debug

    total_weight = sum(weight for _signal, weight in parts)
    if total_weight <= 0.0:
        return 0.0, debug

    blended_signal = sum(signal * weight for signal, weight in parts) / total_weight
    return _clamp(blended_signal, -1.0, 1.0), debug


def _logit(p):
    p = _clamp(p, 1e-6, 1.0 - 1e-6)
    return math.log(p / (1.0 - p))


def _sigmoid(z):
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _surface_candidates(surface):
    if surface == "I.hard":
        return ("I.hard", "Hard", "N/A")
    if surface == "Hard":
        return ("Hard", "I.hard", "N/A")
    return (surface, "N/A")


def _parse_iso_date(v):
    if not v:
        return None
    try:
        return date.fromisoformat(str(v).strip()[:10])
    except (ValueError, TypeError, IndexError):
        return None


def _tour_key(name):
    """
    Normalize tournament identity across years/sponsor strings.
    Example: 'BNP Paribas Open - Indian Wells' -> 'indian wells'
    """
    raw = (name or "").strip().lower()
    if not raw:
        return ""
    parts = [p.strip() for p in re.split(r"\s*-\s*", raw) if p.strip()]
    core = parts[-1] if len(parts) >= 2 and len(parts[-1]) >= 4 else raw
    core = re.sub(r"\b\d{4}\b", " ", core)
    core = re.sub(r"\b(challenger|qualifiers?|qualifying|qualification|atp|wta)\b", " ", core)
    core = re.sub(r"[^a-z0-9]+", " ", core)
    return " ".join(core.split())


def _tour_key_candidates(name):
    raw = (name or "").strip().lower()
    if not raw:
        return []
    parts = [p.strip() for p in re.split(r"\s*-\s*", raw) if p.strip()]
    cands = [_tour_key(raw)]
    if parts:
        cands.append(_tour_key(parts[0]))
        cands.append(_tour_key(parts[-1]))
    if len(parts) >= 2:
        cands.append(_tour_key(parts[0] + " " + parts[-1]))
    out = []
    seen = set()
    for c in cands:
        if not c or c in seen:
            continue
        seen.add(c)
        out.append(c)
    return out


def _mean_std(values):
    vals = [float(x) for x in values if x is not None]
    n = len(vals)
    if n == 0:
        return (0.0, 1.0)
    mean = sum(vals) / float(n)
    if n == 1:
        return (mean, 1.0)
    var = sum((x - mean) ** 2 for x in vals) / float(n)
    std = math.sqrt(var)
    if std < 1e-9:
        std = 1.0
    return (mean, std)


def _is_grand_slam_tour_name(tour_name):
    u = (tour_name or "").upper()
    return any(
        x in u
        for x in (
            "AUSTRALIAN OPEN",
            "FRENCH OPEN",
            "ROLAND GARROS",
            "WIMBLEDON",
            "US OPEN",
            "U.S. OPEN",
            "GRAND SLAM",
        )
    )


def _series_bucket_from_tour(tour_name, tour_rank):
    u = (tour_name or "").upper()
    if _is_grand_slam_tour_name(tour_name):
        return "Grand Slam"
    if "MASTERS CUP" in u or "ATP FINALS" in u or "TOUR FINALS" in u:
        return "Masters Cup"
    if "MASTERS" in u or "1000" in u:
        return "Masters 1000"
    if "ATP 500" in u or "500" in u:
        return "ATP500"
    if "ATP 250" in u or "250" in u:
        return "ATP250"
    if "CHALLENGER" in u:
        return "ATP250"

    # Rank fallback from OnCourt tours table when naming is sparse.
    try:
        rk = int(tour_rank) if tour_rank is not None else None
    except (TypeError, ValueError):
        rk = None
    if rk == 4:
        return "Grand Slam"
    if rk == 3:
        return "Masters 1000"
    if rk == 2:
        return "ATP500"
    return "ATP250"


def _tour_class_score(tour_rank, tour_name):
    name = (tour_name or "").upper()
    try:
        rank = int(tour_rank) if tour_rank is not None else None
    except (TypeError, ValueError):
        rank = None

    if "JUNIOR" in name:
        return 0.0
    if "DAVIS CUP" in name or "BILLIE JEAN KING" in name:
        return 2.3
    if rank == 4 or "GRAND SLAM" in name:
        return 4.0
    if rank == 3 or "MASTERS" in name or "ATP FINALS" in name or "TOUR FINALS" in name:
        return 3.0
    if rank == 2 or "ATP" in name:
        return 2.0
    if rank == 1 or "CHALLENGER" in name:
        return 1.0
    if rank == 0 or "ITF" in name or "FUTURES" in name or re.search(r"\b[MW]\d{1,2}\b", name):
        return 0.0
    return 1.0


def _score_games_for_winner(result):
    text = (result or "").strip()
    if not text or "bye" in text.lower() or "w/o" in text.lower() or "walkover" in text.lower():
        return None
    winner_games = 0
    loser_games = 0
    winner_sets = 0
    loser_sets = 0
    for token in text.split():
        cleaned = re.sub(r"\([^)]*\)", "", token)
        match = re.match(r"^(\d+)-(\d+)", cleaned)
        if not match:
            continue
        left = int(match.group(1))
        right = int(match.group(2))
        winner_games += left
        loser_games += right
        if left > right:
            winner_sets += 1
        elif right > left:
            loser_sets += 1
    if winner_games + loser_games <= 0:
        return None
    return winner_games, loser_games, winner_sets, loser_sets


def _series_calibration_blend(series_bucket, surface, confidence):
    blend = PROB_CAL_SERIES_BLEND.get(series_bucket, 1.0)
    if series_bucket in ("ATP250", "ATP500"):
        if confidence == "medium":
            blend *= 0.55
        elif confidence == "low":
            blend *= 0.35
        if series_bucket == "ATP500" and surface == "Hard":
            blend = max(0.20, blend)
        elif surface in ("Clay", "Grass"):
            blend *= 0.75
    return _clamp(blend, 0.0, 1.0)


def _series_rank_weight_multiplier(series_bucket, confidence):
    if series_bucket == "ATP250":
        return {"high": 0.90, "medium": 0.72, "low": 0.60}.get(confidence, 1.0)
    if series_bucket == "ATP500":
        return {"high": 0.95, "medium": 0.78, "low": 0.65}.get(confidence, 1.0)
    return 1.0


def _is_challenger_tour(tour_name):
    return "CHALLENGER" in (tour_name or "").upper()


def _series_elo_weight_multiplier(series_bucket, confidence, is_challenger):
    if is_challenger:
        return CHALLENGER_ELO_WEIGHT_MULTIPLIER.get(confidence, CHALLENGER_ELO_WEIGHT_MULTIPLIER["medium"])
    return 1.0


def _apply_elo_magnitude_guard(w_sr, w_elo, w_rank, p_serve_return, p_elo, p_rank, is_challenger):
    if p_rank is None or p_serve_return is None:
        return w_sr, w_elo, w_rank, 0.0

    elo_rank_logit_gap = abs(_logit(p_elo) - _logit(_clamp(p_rank, 0.01, 0.99)))
    elo_sr_logit_gap = abs(_logit(p_elo) - _logit(_clamp(p_serve_return, 0.01, 0.99)))
    if elo_rank_logit_gap <= ELO_MAGNITUDE_GUARD_RANK_LOGIT_GAP or elo_sr_logit_gap <= ELO_MAGNITUDE_GUARD_SR_LOGIT_GAP:
        return w_sr, w_elo, w_rank, 0.0

    dampener = max(
        ELO_MAGNITUDE_GUARD_MIN_DAMP,
        1.0 - 0.25 * min(elo_rank_logit_gap / 3.0, 1.0),
    )
    if is_challenger:
        dampener *= 0.82
    dampener = max(0.38, dampener)

    w_elo_before = w_elo
    w_elo *= dampener
    released = max(0.0, w_elo_before - w_elo)
    if released > 0:
        w_sr += released * 0.55
        w_rank += released * 0.45
    return w_sr, w_elo, w_rank, released


def _apply_surface_rank_conflict_guard(
    w_sr,
    w_elo,
    w_rank,
    p_serve_return,
    p_elo,
    p_rank,
    surface,
    series_bucket,
    confidence,
):
    """Cap stale broad-rank dominance when surface matchup data points the other way."""
    if p_rank is None or p_serve_return is None:
        return w_sr, w_elo, w_rank, 0.0
    if surface not in SURFACE_RANK_CONFLICT_SURFACES:
        return w_sr, w_elo, w_rank, 0.0
    if series_bucket not in SURFACE_RANK_CONFLICT_SERIES:
        return w_sr, w_elo, w_rank, 0.0
    if confidence not in ("high", "medium"):
        return w_sr, w_elo, w_rank, 0.0
    if (p_rank - 0.5) * (p_serve_return - 0.5) >= 0:
        return w_sr, w_elo, w_rank, 0.0
    if abs(p_serve_return - 0.5) < SURFACE_RANK_CONFLICT_MIN_SR_EDGE:
        return w_sr, w_elo, w_rank, 0.0
    if abs(p_serve_return - p_rank) < SURFACE_RANK_CONFLICT_MIN_SR_RANK_GAP:
        return w_sr, w_elo, w_rank, 0.0
    if (p_elo - 0.5) * (p_rank - 0.5) > 0 and abs(p_elo - 0.5) > SURFACE_RANK_CONFLICT_MAX_ELO_EDGE:
        return w_sr, w_elo, w_rank, 0.0

    anchor_weight = max(0.0, w_sr + w_elo)
    if anchor_weight <= 0:
        return w_sr, w_elo, w_rank, 0.0
    rank_cap = anchor_weight * SURFACE_RANK_CONFLICT_RANK_TO_ANCHOR_RATIO
    if w_rank <= rank_cap:
        return w_sr, w_elo, w_rank, 0.0

    released = w_rank - rank_cap
    w_rank = rank_cap
    w_sr += released * SURFACE_RANK_CONFLICT_RELEASE_TO_SR
    w_elo += released * (1.0 - SURFACE_RANK_CONFLICT_RELEASE_TO_SR)
    return w_sr, w_elo, w_rank, released


def _is_established_player(rank, elo_surface, elo_overall, match_count):
    if rank is not None and rank > 0 and rank <= LOW_CONF_DOG_ESTABLISHED_RANK:
        return True
    if elo_surface is not None and float(elo_surface) >= LOW_CONF_DOG_ESTABLISHED_ELO:
        return True
    if elo_overall is not None and float(elo_overall) >= LOW_CONF_DOG_ESTABLISHED_ELO:
        return True
    if match_count is not None and int(match_count or 0) >= 12:
        return True
    return False


def _days_since(value, today_value=None):
    parsed = _parse_iso_date(value)
    if parsed is None:
        return None
    today_value = today_value or date.today()
    return max(0, (today_value - parsed).days)


def _coverage_tag(surface_matches_12m, history, activity, today_value=None) -> bool:
    last_match_days = _days_since((activity or {}).get("last_match_date"), today_value)
    return (
        int(surface_matches_12m or 0) >= 3
        and int((history or {}).get("matches_total") or 0) >= 20
        and int((history or {}).get("recent_challenger_plus_matches") or 0) >= 2
        and last_match_days is not None
        and last_match_days <= 75
    )


def _data_coverage_tag(mc1, mc2, h1, h2, a1, a2, today_value=None) -> str:
    if _coverage_tag(mc1, h1, a1, today_value) and _coverage_tag(mc2, h2, a2, today_value):
        return "HIGH"
    if int(mc1 or 0) >= 2 and int(mc2 or 0) >= 2:
        return "PARTIAL"
    return "THIN"


def _apply_low_confidence_dog_guard(
    p1_win,
    p_elo,
    p_rank,
    confidence,
    has_s1,
    has_s2,
    mc1_12,
    mc2_12,
    e1_is_real,
    e2_is_real,
    e1_s,
    e2_s,
    e1_o,
    e2_o,
    r1,
    r2,
):
    if confidence != "low":
        return p1_win, 0.0

    underdog_is_p1 = p1_win < 0.5
    underdog_has_stats = has_s1 if underdog_is_p1 else has_s2
    underdog_matches = mc1_12 if underdog_is_p1 else mc2_12
    underdog_elo_real = e1_is_real if underdog_is_p1 else e2_is_real
    favourite_matches = mc2_12 if underdog_is_p1 else mc1_12
    favourite_rank = r2 if underdog_is_p1 else r1
    favourite_elo_surface = e2_s if underdog_is_p1 else e1_s
    favourite_elo_overall = e2_o if underdog_is_p1 else e1_o

    weak_underdog_profile = (
        (not underdog_has_stats)
        or underdog_matches < LOW_CONF_DOG_MIN_MATCHES
        or (not underdog_elo_real)
    )
    if not weak_underdog_profile:
        return p1_win, 0.0

    if not _is_established_player(favourite_rank, favourite_elo_surface, favourite_elo_overall, favourite_matches):
        return p1_win, 0.0

    anchor_probs = [p_elo]
    if p_rank is not None:
        anchor_probs.append(p_rank)

    if underdog_is_p1:
        anchor_p1 = min(anchor_probs)
        if p1_win <= anchor_p1 + LOW_CONF_DOG_MODEL_ANCHOR_GAP:
            return p1_win, 0.0
    else:
        anchor_p1 = max(anchor_probs)
        if p1_win >= anchor_p1 - LOW_CONF_DOG_MODEL_ANCHOR_GAP:
            return p1_win, 0.0

    elo_gap = abs(float(e1_s or DEFAULT_ELO) - float(e2_s or DEFAULT_ELO))
    rank_gap = abs((r1 or 9999) - (r2 or 9999)) if (r1 and r2 and r1 > 0 and r2 > 0) else 0
    gap_strength = max(
        _clamp((elo_gap - 120.0) / 260.0, 0.0, 1.0),
        _clamp((rank_gap - 40.0) / 160.0, 0.0, 1.0),
    )

    blend = LOW_CONF_DOG_BLEND_MIN
    if not underdog_has_stats:
        blend += 0.20
    if underdog_matches < 4:
        blend += 0.10
    if not underdog_elo_real:
        blend += 0.10
    blend += 0.10 * gap_strength
    blend = _clamp(blend, LOW_CONF_DOG_BLEND_MIN, LOW_CONF_DOG_BLEND_MAX)

    adjusted = (1.0 - blend) * p1_win + blend * anchor_p1
    if underdog_is_p1:
        adjusted = min(p1_win, adjusted)
    else:
        adjusted = max(p1_win, adjusted)

    return adjusted, adjusted - p1_win


def _recent_matches_at_current_level(rec, current_class_score):
    if current_class_score >= 4.0:
        return int(rec.get("recent_slam_plus_matches") or 0)
    if current_class_score >= 3.0:
        return int(rec.get("recent_masters_plus_matches") or 0)
    if current_class_score >= 2.0:
        return int(rec.get("recent_atp_plus_matches") or 0)
    if current_class_score >= 1.0:
        return int(rec.get("recent_challenger_plus_matches") or 0)
    return int(rec.get("matches_total") or 0)


def _synthetic_rank_for_unranked(rec, current_class_score, confidence, opponent_established):
    if current_class_score < ONE_SIDED_RANK_EVENT_MIN or not opponent_established:
        return None

    recent_avg = _float(rec.get("recent_class_avg"), 0.0) or 0.0
    current_plus_matches = _recent_matches_at_current_level(rec, current_class_score)
    matches_total = int(rec.get("matches_total") or 0)
    deficit = max(0.0, current_class_score - recent_avg)

    synthetic = ONE_SIDED_RANK_BASE + max(0.0, current_class_score - 2.0) * ONE_SIDED_RANK_EVENT_STEP
    synthetic += max(0.0, deficit) * ONE_SIDED_RANK_RECENT_DEFICIT_UNIT

    if current_plus_matches <= 0:
        synthetic += ONE_SIDED_RANK_NO_EXPOSURE
    elif current_plus_matches <= 2:
        synthetic += ONE_SIDED_RANK_THIN_EXPOSURE
    elif current_plus_matches >= 5:
        synthetic -= ONE_SIDED_RANK_MULTI_MATCH_DISCOUNT

    if recent_avg >= current_class_score - 0.25:
        synthetic -= ONE_SIDED_RANK_RECENT_NEAR_LEVEL_DISCOUNT

    if matches_total < 8:
        synthetic += ONE_SIDED_RANK_LOW_MATCH_BONUS
    elif matches_total < 15:
        synthetic += ONE_SIDED_RANK_MED_MATCH_BONUS

    if confidence == "low":
        synthetic += ONE_SIDED_RANK_LOW_CONF_BONUS
    elif confidence == "medium":
        synthetic += ONE_SIDED_RANK_MEDIUM_CONF_BONUS

    return int(round(_clamp(synthetic, 350.0, ONE_SIDED_RANK_CAP)))


def _class_jump_adjustment(rec, current_class_score, confidence, opponent_established, player_established=False):
    if current_class_score < CLASS_JUMP_EVENT_MIN:
        return 0.0, 1.0

    if not rec:
        deficit = current_class_score
        matches_total = 0
        current_plus_matches = 0
    else:
        avg_class = float(rec.get("recent_class_avg") or 0.0)
        deficit = current_class_score - avg_class
        matches_total = int(rec.get("matches_total") or 0)
        current_plus_matches = _recent_matches_at_current_level(rec, current_class_score)

    if deficit <= CLASS_JUMP_DEFICIT_ONSET and current_plus_matches >= 3:
        return 0.0, 1.0

    penalty = max(0.0, (deficit - 0.10) * CLASS_JUMP_ELO_PER_CLASS)
    if current_plus_matches == 0:
        penalty += CLASS_JUMP_NO_EXPOSURE_BONUS
    elif current_plus_matches <= 2:
        penalty += CLASS_JUMP_THIN_EXPOSURE_BONUS

    if matches_total < 12:
        penalty += CLASS_JUMP_LOW_MATCH_BONUS

    if confidence == "low":
        penalty += CLASS_JUMP_LOW_CONF_BONUS
    elif confidence == "medium":
        penalty += CLASS_JUMP_MEDIUM_CONF_BONUS

    if opponent_established:
        penalty += CLASS_JUMP_OPP_ESTABLISHED_BONUS

    if player_established:
        if confidence == "high":
            penalty *= CLASS_JUMP_ESTABLISHED_HIGH_MULT
        elif confidence == "medium":
            penalty *= CLASS_JUMP_ESTABLISHED_MEDIUM_MULT

    penalty = _clamp(penalty, 0.0, CLASS_JUMP_MAX_ELO)
    sample_multiplier = _clamp(1.0 - penalty / 150.0, CLASS_JUMP_SAMPLE_MULT_MIN, 1.0)
    if player_established and confidence == "high":
        sample_multiplier = max(sample_multiplier, CLASS_JUMP_ESTABLISHED_SAMPLE_MULT_MIN)
    return penalty, sample_multiplier


def _apply_stepup_dog_guard(
    p1_win,
    p_elo,
    p_rank,
    confidence,
    current_class_score,
    p1_hist,
    p2_hist,
    r1,
    r2,
    p1_established,
    p2_established,
):
    if confidence not in ("low", "medium") or current_class_score < STEPUP_DOG_GUARD_EVENT_MIN:
        return p1_win, 0.0

    underdog_is_p1 = p1_win < 0.5
    underdog_hist = p1_hist if underdog_is_p1 else p2_hist
    favourite_established = p2_established if underdog_is_p1 else p1_established
    underdog_rank = r1 if underdog_is_p1 else r2
    favourite_rank = r2 if underdog_is_p1 else r1

    if not favourite_established:
        return p1_win, 0.0

    recent_avg = _float(underdog_hist.get("recent_class_avg"), 0.0) or 0.0
    current_plus_matches = _recent_matches_at_current_level(underdog_hist, current_class_score)
    matches_total = int(underdog_hist.get("matches_total") or 0)
    deficit = max(0.0, current_class_score - recent_avg)

    weak_step_up_profile = (
        deficit >= STEPUP_DOG_GUARD_MIN_RECENT_DEFICIT
        and current_plus_matches <= 1
        and ((underdog_rank is None) or underdog_rank > 350 or matches_total < 12)
    )
    if confidence == "medium" and not weak_step_up_profile:
        return p1_win, 0.0
    if confidence == "low" and deficit < 0.45 and current_plus_matches >= 3:
        return p1_win, 0.0

    anchor_probs = [p_elo]
    if p_rank is not None:
        anchor_probs.append(p_rank)

    if underdog_is_p1:
        anchor_p1 = min(anchor_probs)
        if p1_win <= anchor_p1 + STEPUP_DOG_GUARD_ANCHOR_GAP:
            return p1_win, 0.0
    else:
        anchor_p1 = max(anchor_probs)
        if p1_win >= anchor_p1 - STEPUP_DOG_GUARD_ANCHOR_GAP:
            return p1_win, 0.0

    blend = STEPUP_DOG_GUARD_BLEND_LOW if confidence == "low" else STEPUP_DOG_GUARD_BLEND_MEDIUM
    if current_plus_matches <= 0:
        blend += 0.12
    elif current_plus_matches == 1:
        blend += 0.05
    if underdog_rank is None:
        blend += 0.08
    elif underdog_rank > 600:
        blend += 0.04
    if favourite_rank is not None and favourite_rank <= 120:
        blend += 0.05
    blend += _clamp((deficit - 0.50) * 0.14, 0.0, 0.14)
    blend = _clamp(blend, STEPUP_DOG_GUARD_BLEND_MEDIUM, STEPUP_DOG_GUARD_BLEND_MAX)

    adjusted = (1.0 - blend) * p1_win + blend * anchor_p1
    if underdog_is_p1:
        adjusted = min(p1_win, adjusted)
    else:
        adjusted = max(p1_win, adjusted)
    return adjusted, adjusted - p1_win


def _series_delta_multipliers(series_bucket, surface, confidence):
    if series_bucket == "ATP250":
        if confidence == "high":
            return (1.12, 1.15, 0.88, 0.90)
        if confidence == "medium":
            return (1.18, 1.22, 0.76, 0.82)
        if confidence == "low":
            return (1.24, 1.28, 0.66, 0.72)
    if series_bucket == "ATP500":
        if surface == "Hard":
            if confidence == "high":
                return (0.98, 1.02, 0.68, 0.80)
            if confidence == "medium":
                return (1.02, 1.06, 0.60, 0.72)
            if confidence == "low":
                return (1.06, 1.10, 0.52, 0.66)
        if confidence == "high":
            return (1.02, 1.06, 0.78, 0.88)
        if confidence == "medium":
            return (1.08, 1.12, 0.70, 0.82)
        if confidence == "low":
            return (1.14, 1.18, 0.62, 0.74)
    return (1.0, 1.0, 1.0, 1.0)


def _series_crisis_rank_multiplier(series_bucket):
    if series_bucket == "ATP250":
        return 0.42
    if series_bucket == "ATP500":
        return 0.48
    return RANK_WEIGHT_CRISIS_MULT


def _apply_series_probability_guard(p1_win, series_bucket, surface, confidence, is_challenger=False):
    if is_challenger:
        cap_bucket = "Challenger"
    elif surface == "Grass":
        cap_bucket = "Grass"
    else:
        cap_bucket = series_bucket
    caps = SERIES_FAVORITE_PROB_CAP.get(cap_bucket)
    if not caps:
        return _clamp(float(p1_win), 1e-6, 1.0 - 1e-6)
    cap = float(caps.get(confidence, 0.90))
    if series_bucket == "ATP500" and surface == "Hard":
        cap -= 0.02
    cap = _clamp(cap, 0.78, 0.93)
    p = _clamp(float(p1_win), 1e-6, 1.0 - 1e-6)
    fav_is_p1 = p >= 0.5
    q = p if fav_is_p1 else (1.0 - p)
    q = min(q, cap)
    return q if fav_is_p1 else (1.0 - q)


def _apply_surface_points_mismatch_guard(
    p1_win,
    surface,
    series_bucket,
    confidence,
    pts1,
    pts2,
    p_rank_points,
):
    """Stop thin clay/grass samples from inventing value against clear surface specialists."""
    if surface not in SURFACE_POINTS_MISMATCH_SURFACES:
        return p1_win, 0.0, 0.0
    if series_bucket not in SURFACE_POINTS_MISMATCH_SERIES:
        return p1_win, 0.0, 0.0
    if p_rank_points is None:
        return p1_win, 0.0, 0.0
    try:
        p1_pts = max(0.0, float(pts1 or 0.0))
        p2_pts = max(0.0, float(pts2 or 0.0))
    except (TypeError, ValueError):
        return p1_win, 0.0, 0.0

    fav_pts = max(p1_pts, p2_pts)
    dog_pts = min(p1_pts, p2_pts)
    ratio = (fav_pts + POINTS_MIN_BASE) / (dog_pts + POINTS_MIN_BASE)
    if (
        fav_pts < SURFACE_POINTS_MISMATCH_MIN_FAV_POINTS
        or dog_pts > SURFACE_POINTS_MISMATCH_MAX_DOG_POINTS
        or ratio < SURFACE_POINTS_MISMATCH_MIN_RATIO
    ):
        return p1_win, 0.0, ratio

    points_favour_p1 = p1_pts > p2_pts
    anchor = _clamp(float(p_rank_points), 0.02, 0.98)
    if points_favour_p1 and p1_win >= anchor - 0.02:
        return p1_win, 0.0, ratio
    if (not points_favour_p1) and p1_win <= anchor + 0.02:
        return p1_win, 0.0, ratio

    blend = SURFACE_POINTS_MISMATCH_BLEND_BASE
    blend += min(0.22, math.log(ratio / SURFACE_POINTS_MISMATCH_MIN_RATIO) * 0.14)
    if series_bucket == "Grand Slam":
        blend += 0.10
    if dog_pts <= 20:
        blend += 0.10
    if confidence in ("medium", "low"):
        blend += 0.08
    blend = _clamp(blend, SURFACE_POINTS_MISMATCH_BLEND_BASE, SURFACE_POINTS_MISMATCH_BLEND_CAP)

    adjusted = (1.0 - blend) * p1_win + blend * anchor
    if points_favour_p1:
        adjusted = max(p1_win, adjusted)
    else:
        adjusted = min(p1_win, adjusted)
    return adjusted, adjusted - p1_win, ratio


def _calibrate_match_probability(p1_win, series_bucket, surface, confidence):
    p = _clamp(float(p1_win), 1e-6, 1.0 - 1e-6)
    fav_is_p1 = p >= 0.5
    q_raw = p if fav_is_p1 else (1.0 - p)
    z = PROB_CAL_A + PROB_CAL_B * _logit(q_raw)
    q_cal = _sigmoid(z)
    blend = _series_calibration_blend(series_bucket, surface, confidence)
    q = (1.0 - blend) * q_raw + blend * q_cal
    q = _clamp(q, 1e-6, 1.0 - 1e-6)
    return q if fav_is_p1 else (1.0 - q)


def main():
    import requests
    def _env_int(name, default):
        raw = os.environ.get(name)
        if raw is None or str(raw).strip() == "":
            return default
        try:
            return int(float(raw))
        except (TypeError, ValueError):
            return default

    def _env_float(name, default):
        raw = os.environ.get(name)
        if raw is None or str(raw).strip() == "":
            return default
        try:
            return float(raw)
        except (TypeError, ValueError):
            return default

    do_dry_run = "--dry-run" in sys.argv
    do_skip_handicap_values = "--skip-handicap-values" in sys.argv
    if do_dry_run:
        print("Dry run: will not write to Supabase\n")

    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    _supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not _supabase_key:
        print("Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env.local")
        sys.exit(1)

    base = url.rstrip("/") + "/rest/v1"
    headers = {"apikey": _supabase_key, "Authorization": f"Bearer {_supabase_key}"}
    REQ_TIMEOUT = 45  # avoid hanging on slow Supabase

    def _daily_row_key(row):
        return (
            str(row.get("tour_id") or ""),
            str(row.get("player1_id") or ""),
            str(row.get("player2_id") or ""),
            str(row.get("surface") or ""),
            str(row.get("round_id") or ""),
            str(row.get("draw") or ""),
        )

    def _chunked(values, size):
        for start in range(0, len(values), size):
            yield values[start : start + size]

    def _fetch_existing_daily_rows():
        r = requests.get(
            f"{base}/daily_fair_odds",
            headers=headers,
            params={"select": "id,tour_id,player1_id,player2_id,surface,round_id,draw", "limit": 5000},
            timeout=REQ_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()

    def _load_known_player_ids(player_ids):
        known_ids = set()
        ids = sorted({str(pid) for pid in player_ids if str(pid).strip()})
        for chunk in _chunked(ids, 200):
            r = requests.get(
                f"{base}/oncourt_players",
                headers=headers,
                params={"select": "id", "id": f"in.({','.join(chunk)})", "limit": len(chunk)},
                timeout=REQ_TIMEOUT,
            )
            r.raise_for_status()
            for item in r.json():
                if item.get("id") is not None:
                    known_ids.add(str(item["id"]))
        return known_ids

    def _filter_rows_with_known_players(rows):
        needed_ids = {
            str(row.get("player1_id") or "")
            for row in rows
        } | {
            str(row.get("player2_id") or "")
            for row in rows
        }
        known_ids = _load_known_player_ids(needed_ids)
        missing_ids = sorted(pid for pid in needed_ids if pid and pid not in known_ids)
        if missing_ids:
            print(
                "  Warning: skipping rows with missing oncourt_players ids: "
                + ", ".join(missing_ids[:20])
                + (" ..." if len(missing_ids) > 20 else "")
            )
            print("  Run `python scripts/oncourt-load-supabase.py --quick` to backfill those players.")
            if os.environ.get("ALLOW_MISSING_ONCOURT_PLAYERS", "").strip().lower() not in {"1", "true", "yes", "on"}:
                print(
                    "ERROR: Refusing to sync partial daily_fair_odds because oncourt_players is stale. "
                    "Run Supabase sync without --skip-players, then rerun fair odds."
                )
                sys.exit(1)

        filtered = [
            row
            for row in rows
            if str(row.get("player1_id") or "") in known_ids and str(row.get("player2_id") or "") in known_ids
        ]
        return filtered

    def _find_existing_daily_row_id(row):
        queries = []

        exact_params = {
            "select": "id",
            "tour_id": f"eq.{row['tour_id']}",
            "player1_id": f"eq.{row['player1_id']}",
            "player2_id": f"eq.{row['player2_id']}",
            "surface": f"eq.{row['surface']}",
            "round_id": f"eq.{row['round_id']}",
            "limit": 5,
        }
        draw = row.get("draw")
        if draw is None or draw == "":
            exact_params["draw"] = "is.null"
        else:
            exact_params["draw"] = f"eq.{draw}"
        queries.append(exact_params)

        queries.append(
            {
                "select": "id",
                "tour_id": f"eq.{row['tour_id']}",
                "player1_id": f"eq.{row['player1_id']}",
                "player2_id": f"eq.{row['player2_id']}",
                "limit": 5,
            }
        )
        queries.append(
            {
                "select": "id",
                "player1_id": f"eq.{row['player1_id']}",
                "player2_id": f"eq.{row['player2_id']}",
                "surface": f"eq.{row['surface']}",
                "limit": 5,
            }
        )

        for params in queries:
            r = requests.get(f"{base}/daily_fair_odds", headers=headers, params=params, timeout=REQ_TIMEOUT)
            r.raise_for_status()
            payload = r.json()
            if payload:
                return payload[0].get("id")
        return None

    def _sync_daily_fair_odds(rows):
        rows_by_key = {}
        for row in rows:
            rows_by_key[_daily_row_key(row)] = row

        current_rows = list(rows_by_key.values())
        existing_rows = _fetch_existing_daily_rows()
        existing_by_key = {
            _daily_row_key(row): row
            for row in existing_rows
            if row.get("id") is not None
        }
        keep_existing_ids = set()

        headers_write = {**headers, "Content-Type": "application/json", "Prefer": "return=minimal"}
        coverage_fields = {
            "p1_win_prob_raw",
            "p2_win_prob_raw",
            "match_count_12m_p1",
            "match_count_12m_p2",
            "matches_total_p1",
            "matches_total_p2",
            "recent_challenger_plus_p1",
            "recent_challenger_plus_p2",
            "last_match_days_p1",
            "last_match_days_p2",
            "data_coverage_tag",
        }
        coverage_schema_missing = False
        inserted = 0
        updated = 0
        recovered = 0

        def _strip_coverage_fields(row):
            return {k: v for k, v in row.items() if k not in coverage_fields}

        def _is_schema_cache_error(resp):
            if resp.status_code < 400:
                return False
            body = (resp.text or "").lower()
            return any(tok in body for tok in ("schema cache", "unknown column", "could not find", "does not exist", "42703"))

        def _write_daily_row(method, url, row):
            nonlocal coverage_schema_missing
            payload = _strip_coverage_fields(row) if coverage_schema_missing else row
            resp = requests.request(method, url, headers=headers_write, json=payload, timeout=REQ_TIMEOUT)
            if not coverage_schema_missing and _is_schema_cache_error(resp):
                coverage_schema_missing = True
                print(f"  coverage_fields_not_synced_schema_missing rows={len(current_rows)}")
                resp = requests.request(
                    method,
                    url,
                    headers=headers_write,
                    json=_strip_coverage_fields(row),
                    timeout=REQ_TIMEOUT,
                )
            return resp

        for row in current_rows:
            key = _daily_row_key(row)
            existing = existing_by_key.get(key)
            if existing is not None:
                r = _write_daily_row(
                    "PATCH",
                    f"{base}/daily_fair_odds?id=eq.{existing['id']}",
                    row,
                )
                r.raise_for_status()
                keep_existing_ids.add(str(existing["id"]))
                updated += 1
                continue

            r = _write_daily_row("POST", f"{base}/daily_fair_odds", row)
            if r.status_code == 409:
                existing_id = _find_existing_daily_row_id(row)
                if existing_id is None:
                    print(f"  daily_fair_odds conflict body: {r.text}")
                    r.raise_for_status()
                patch_r = _write_daily_row(
                    "PATCH",
                    f"{base}/daily_fair_odds?id=eq.{existing_id}",
                    row,
                )
                patch_r.raise_for_status()
                keep_existing_ids.add(str(existing_id))
                recovered += 1
                continue

            r.raise_for_status()
            inserted += 1

        stale_ids = [
            str(existing["id"])
            for existing in existing_by_key.values()
            if existing.get("id") is not None and str(existing["id"]) not in keep_existing_ids
        ]
        deleted = 0
        for chunk in _chunked(stale_ids, 100):
            r = requests.delete(
                f"{base}/daily_fair_odds",
                headers={k: v for k, v in headers.items() if k != "Content-Type"},
                params={"id": f"in.({','.join(chunk)})"},
                timeout=REQ_TIMEOUT,
            )
            r.raise_for_status()
            deleted += len(chunk)

        print(
            "  Synced daily_fair_odds: "
            f"{len(current_rows)} current / {inserted} inserted / {updated} updated / {recovered} recovered / {deleted} stale removed"
        )

    # 1) Today's fixtures (dedupe by match key so same match isn't listed twice)
    raw_fixtures = []
    off = 0
    while True:
        r = requests.get(
            f"{base}/oncourt_today",
            headers=headers,
            params={
                "select": "*",
                "limit": ONCOURT_TODAY_PAGE_SIZE,
                "offset": off,
                # Stable order so pagination is complete (default order can hide high tour_ids past the first page).
                "order": "tour_id.asc,round_id.asc,draw.asc,player1_id.asc,player2_id.asc",
            },
            timeout=REQ_TIMEOUT,
        )
        r.raise_for_status()
        chunk = r.json()
        if not chunk:
            break
        raw_fixtures.extend(chunk)
        if len(chunk) < ONCOURT_TODAY_PAGE_SIZE:
            break
        off += len(chunk)
    if not raw_fixtures:
        print("No rows in oncourt_today. Run sync first.")
        return
    print(f"  oncourt_today: {len(raw_fixtures)} rows from API (paginated if >{ONCOURT_TODAY_PAGE_SIZE})")
    seen = set()
    fixtures = []
    for f in raw_fixtures:
        match_key = (f.get("tour_id"), f.get("player1_id"), f.get("player2_id"), f.get("round_id"))
        if match_key in seen:
            continue
        seen.add(match_key)
        fixtures.append(f)
    if len(fixtures) < len(raw_fixtures):
        print(f"Fixtures: {len(fixtures)} (deduped from {len(raw_fixtures)})")
    else:
        print(f"Fixtures: {len(fixtures)}")

    # Only include fixtures that are not yet played (no result from OnCourt)
    fixtures = [f for f in fixtures if not (f.get("result") or "").strip()]
    print(f"  Fixtures with no result (unplayed): {len(fixtures)}")

    # 2) Tour -> surface; restrict to ATP + Challenger only (exclude ITF, Futures, etc.)
    tour_select = "id,court_id,name,rank,altitude,date"
    r0 = requests.get(f"{base}/oncourt_tours", headers=headers, params={"select": tour_select, "limit": 1}, timeout=REQ_TIMEOUT)
    if r0.status_code == 400:
        tour_select = "id,court_id,name,rank,date"
    tours_list = []
    off = 0
    while True:
        r = requests.get(f"{base}/oncourt_tours", headers=headers, params={"select": tour_select, "offset": off, "limit": 1000}, timeout=REQ_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        tours_list.extend(data)
        off += len(data)
        if len(data) < 1000:
            break
    # ITF/Futures: M15, M25, M5, W15, W25, W5 etc. – exclude these
    itf_pattern = re.compile(r"\b[MW]\d{1,2}\b", re.IGNORECASE)

    tours = {}
    tour_name_by_id = {}
    tour_rank_by_id = {}
    tour_date_by_id = {}
    tour_to_altitude = {}
    atp_challenger_tour_ids = set()
    for t in tours_list:
        if t.get("id") is None:
            continue
        tid = int(t["id"])
        tours[tid] = t.get("court_id")
        tour_name_by_id[tid] = t.get("name") or ""
        tour_rank_by_id[tid] = t.get("rank")
        tdate = _parse_iso_date(t.get("date"))
        if tdate is not None:
            tour_date_by_id[tid] = tdate.isoformat()
        alt = t.get("altitude")
        if alt is not None:
            try:
                tour_to_altitude[tid] = float(alt)
            except (TypeError, ValueError):
                pass
        name = (t.get("name") or "").upper()
        raw_name = t.get("name") or ""
        rank = t.get("rank")
        if itf_pattern.search(raw_name):
            continue
        if "ITF" in name or "FUTURES" in name:
            continue
        # Include ATP + Challenger. OnCourt marks Grand Slams (including RG qualies)
        # as rank=4 and often names them "French Open - Paris", without "ATP".
        if _is_grand_slam_tour_name(raw_name):
            atp_challenger_tour_ids.add(tid)
        elif rank is not None and rank <= INCLUDE_TOUR_RANK_MAX:
            atp_challenger_tour_ids.add(tid)
        elif "CHALLENGER" in name:
            atp_challenger_tour_ids.add(tid)
        elif "ATP" in name or "MASTERS" in name or "GRAND SLAM" in name:
            atp_challenger_tour_ids.add(tid)
    tour_key_by_id = {tid: _tour_key(tour_name_by_id.get(tid, "")) for tid in tour_name_by_id}
    fixtures = [f for f in fixtures if f.get("tour_id") in atp_challenger_tour_ids]
    print(f"  Fixtures after ATP/Challenger only (excl. M15/M25/ITF): {len(fixtures)}")

    r = requests.get(f"{base}/oncourt_courts", headers=headers, params={"select": "id,name", "limit": 100}, timeout=REQ_TIMEOUT)
    r.raise_for_status()
    courts = {int(c["id"]): (c.get("name") or "N/A").strip() for c in r.json() if c.get("id") is not None}

    def _court_to_surface(court_name):
        """Map OnCourt court name to canonical surface (Hard, Clay, Grass, I.hard) for stats lookup."""
        if not court_name:
            return "N/A"
        c = court_name.upper()
        if "CLAY" in c or "TERRE" in c:
            return "Clay"
        if "GRASS" in c:
            return "Grass"
        if "INDOOR" in c and "HARD" in c:
            return "I.hard"
        if "HARD" in c or "DECOTURF" in c or "ACRYLIC" in c:
            return "Hard"
        return court_name  # keep as-is if no match (e.g. "Carpet" -> N/A later)

    tour_to_surface = {}
    for tid, cid in tours.items():
        if cid is not None:
            raw = courts.get(int(cid), "N/A")
            tour_to_surface[tid] = _court_to_surface(raw) if raw != "N/A" else raw
    print(f"  Loaded {len(tour_to_surface):,} tours -> surface" + (f", {len(tour_to_altitude):,} with altitude (run oncourt-derive-altitude.py + migration if 0)" if tour_to_altitude else ""))

    # 3) Player surface stats. Prefer player_surface_stats_v2 (decomposed serve) when available.
    stats_select_v2 = ("player_id,surface,hold_pct,return_pct,hold_pct_long,return_pct_long,"
                      "match_count,service_pts,return_pts,first_serve_pct,first_serve_win_pct,"
                      "second_serve_win_pct,ace_rate,df_rate,bp_save_rate,bp_convert_rate,"
                      "first_serve_pct_long,first_serve_win_pct_long,second_serve_win_pct_long")
    stats_select_full = "player_id,surface,hold_pct,return_pct,hold_pct_long,return_pct_long,match_count,service_pts,return_pts"
    stats_select_base = "player_id,surface,hold_pct,return_pct,match_count,service_pts,return_pts"
    stats_select_legacy = "player_id,surface,hold_pct,return_pct,match_count,service_pts"

    stats_rows = []
    use_v2 = False
    if HAS_MATCHUP_MODEL:
        r = requests.get(
            f"{base}/player_surface_stats_v2",
            headers={**headers, "Prefer": "count=exact"},
            params={"select": stats_select_v2, "limit": 1},
            timeout=REQ_TIMEOUT,
        )
        if r.status_code in (200, 206):
            use_v2 = True
            off = 0
            while True:
                r = requests.get(
                    f"{base}/player_surface_stats_v2",
                    headers=headers,
                    params={"select": stats_select_v2, "offset": off, "limit": 1000},
                    timeout=REQ_TIMEOUT,
                )
                r.raise_for_status()
                data = r.json()
                if not data:
                    break
                stats_rows.extend(data)
                off += len(data)
                if len(data) < 1000:
                    break
            print(f"  Loaded {len(stats_rows):,} rows from player_surface_stats_v2 (matchup model)")
    if not stats_rows:
        r = requests.get(
            f"{base}/player_surface_stats",
            headers={**headers, "Prefer": "count=exact"},
            params={"select": stats_select_full, "limit": 1},
            timeout=REQ_TIMEOUT,
        )
        stats_select = stats_select_full
        if r.status_code in (400, 404):
            r = requests.get(
                f"{base}/player_surface_stats",
                headers={**headers, "Prefer": "count=exact"},
                params={"select": stats_select_base, "limit": 1},
                timeout=REQ_TIMEOUT,
            )
            stats_select = stats_select_base
        if r.status_code in (400, 404):
            r = requests.get(
                f"{base}/player_surface_stats",
                headers={**headers, "Prefer": "count=exact"},
                params={"select": stats_select_legacy, "limit": 1},
                timeout=REQ_TIMEOUT,
            )
            stats_select = stats_select_legacy
        if r.status_code not in (200, 206):
            print("player_surface_stats fetch failed:", r.status_code)
            sys.exit(1)
        off = 0
        while True:
            r = requests.get(
                f"{base}/player_surface_stats",
                headers=headers,
                params={"select": stats_select, "offset": off, "limit": 1000},
                timeout=REQ_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            if not data:
                break
            stats_rows.extend(data)
            off += len(data)
            if len(data) < 1000:
                break

    stats = {(int(r["player_id"]), (r.get("surface") or "N/A").strip()): r for r in stats_rows}

    # Surface priors in raw player_surface_stats scale (weighted by point counts)
    surface_hold_prior = dict(SURFACE_AVG_HOLD)
    surface_ret_prior = dict(SURFACE_AVG_RETURN)
    _hold_num, _hold_den = {}, {}
    _ret_num, _ret_den = {}, {}
    for row in stats_rows:
        surf = (row.get("surface") or "N/A").strip() or "N/A"
        h = _float(row.get("hold_pct"))
        rv = _float(row.get("return_pct"))
        svc_pts = int(row.get("service_pts") or 0)
        ret_pts = int(row.get("return_pts") or 0)
        if h is not None:
            w = max(1, svc_pts)
            _hold_num[surf] = _hold_num.get(surf, 0.0) + h * w
            _hold_den[surf] = _hold_den.get(surf, 0) + w
        if rv is not None:
            w = max(1, ret_pts if ret_pts > 0 else svc_pts)
            _ret_num[surf] = _ret_num.get(surf, 0.0) + rv * w
            _ret_den[surf] = _ret_den.get(surf, 0) + w
    for surf, den in _hold_den.items():
        if den > 0:
            surface_hold_prior[surf] = _hold_num[surf] / den
    for surf, den in _ret_den.items():
        if den > 0:
            surface_ret_prior[surf] = _ret_num[surf] / den
    if surface_hold_prior:
        h_h = surface_hold_prior.get("Hard", SURFACE_AVG_HOLD["Hard"])
        h_c = surface_hold_prior.get("Clay", SURFACE_AVG_HOLD["Clay"])
        r_h = surface_ret_prior.get("Hard", SURFACE_AVG_RETURN["Hard"])
        r_c = surface_ret_prior.get("Clay", SURFACE_AVG_RETURN["Clay"])
        print(f"  Surface priors (raw stats): Hard hold={h_h:.3f} ret={r_h:.3f}, Clay hold={h_c:.3f} ret={r_c:.3f}")

    elo_rows = []
    off = 0
    while True:
        r = requests.get(
            f"{base}/player_elo",
            headers=headers,
            params={"select": "player_id,surface,elo", "offset": off, "limit": 1000},
            timeout=REQ_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        elo_rows.extend(data)
        off += len(data)
        if len(data) < 1000:
            break
    elo_lookup = {(int(r["player_id"]), (r.get("surface") or "N/A").strip()): _float(r.get("elo"), DEFAULT_ELO) for r in elo_rows}
    has_overall_elo = any(s == "Overall" for (_, s) in elo_lookup)
    print(f"  Elo: {len(elo_lookup):,} rows" + (" (surface + Overall 50/50 blend)" if has_overall_elo else " (surface only)"))

    # 4) Lefties: prefer player_hand_reference (hand=L), then fallback to player_extra + categories
    leftie_ids = set()
    try:
        off = 0
        while True:
            r = requests.get(
                f"{base}/player_hand_reference",
                headers=headers,
                params={"select": "player_id", "hand": "eq.L", "offset": off, "limit": 1000},
                timeout=REQ_TIMEOUT,
            )
            if r.status_code != 200:
                break
            data = r.json()
            if not data:
                break
            for row in data:
                pid = row.get("player_id")
                if pid is not None:
                    leftie_ids.add(int(pid))
            off += len(data)
            if len(data) < 1000:
                break
        if leftie_ids:
            pass  # use player_hand_reference
        else:
            for tbl, col in [("oncourt_player_extra", "plays"), ("oncourt_categories", "cat1")]:
                off = 0
                while True:
                    sel = f"player_id,{col}" if tbl == "oncourt_player_extra" else "player_id,cat1"
                    r = requests.get(f"{base}/{tbl}", headers=headers, params={"select": sel, "offset": off, "limit": 1000}, timeout=REQ_TIMEOUT)
                    if r.status_code != 200:
                        break
                    data = r.json()
                    if not data:
                        break
                    for row in data:
                        if row.get("player_id") is None:
                            continue
                        if tbl == "oncourt_player_extra" and "Left-Handed" in (row.get("plays") or ""):
                            leftie_ids.add(int(row["player_id"]))
                        if tbl == "oncourt_categories" and row.get("cat1") is True:
                            leftie_ids.add(int(row["player_id"]))
                    off += len(data)
                    if len(data) < 1000:
                        break
    except Exception:
        pass
    vs_leftie_rows = []
    try:
        off = 0
        while True:
            r = requests.get(
                f"{base}/player_vs_leftie_stats",
                headers=headers,
                params={"select": "player_id,surface,win_pct_vs_leftie,match_count_vs_leftie", "offset": off, "limit": 1000},
                timeout=REQ_TIMEOUT,
            )
            if r.status_code != 200:
                break
            data = r.json()
            if not data:
                break
            vs_leftie_rows.extend(data)
            off += len(data)
            if len(data) < 1000:
                break
    except Exception:
        pass
    vs_leftie_lookup = {}
    for r in vs_leftie_rows:
        pid = r.get("player_id")
        surf = (r.get("surface") or "N/A").strip()
        if pid is not None and surf:
            vs_leftie_lookup[(int(pid), surf)] = _float(r.get("win_pct_vs_leftie"), 0.5)
    print(f"  Lefties: {len(leftie_ids)}, vs-leftie stats: {len(vs_leftie_lookup):,} rows")

    # 4b) Big servers (hold_pct >= threshold on surface) and vs-big-server stats
    big_server_set = set()
    try:
        off = 0
        while True:
            r = requests.get(
                f"{base}/player_surface_stats",
                headers=headers,
                params={"select": "player_id,surface,hold_pct", "hold_pct": f"gte.{BIG_SERVER_HOLD_PCT}", "offset": off, "limit": 1000},
                timeout=REQ_TIMEOUT,
            )
            if r.status_code != 200:
                break
            data = r.json()
            if not data:
                break
            for row in data:
                pid = row.get("player_id")
                surf = (row.get("surface") or "N/A").strip()
                if pid is not None and surf:
                    big_server_set.add((int(pid), surf))
            off += len(data)
            if len(data) < 1000:
                break
    except Exception:
        pass
    vs_big_server_rows = []
    try:
        off = 0
        while True:
            r = requests.get(
                f"{base}/player_vs_big_server_stats",
                headers=headers,
                params={"select": "player_id,surface,win_pct_vs_big_server", "offset": off, "limit": 1000},
                timeout=REQ_TIMEOUT,
            )
            if r.status_code != 200:
                break
            data = r.json()
            if not data:
                break
            vs_big_server_rows.extend(data)
            off += len(data)
            if len(data) < 1000:
                break
    except Exception:
        pass
    vs_big_server_lookup = {}
    for r in vs_big_server_rows:
        pid = r.get("player_id")
        surf = (r.get("surface") or "N/A").strip()
        if pid is not None and surf:
            vs_big_server_lookup[(int(pid), surf)] = _float(r.get("win_pct_vs_big_server"), 0.5)
    print(f"  Big servers: {len(big_server_set)} (player,surface), vs-big-server stats: {len(vs_big_server_lookup):,} rows")

    # 5) Venue stats (player_id, tour_id) -> win_pct at this event (lifetime). Load only for players/tours in today's fixtures (avoids pulling ~1.2M rows).
    venue_player_ids = set()
    venue_tour_ids = set()
    for f in fixtures:
        a, b = f.get("player1_id"), f.get("player2_id")
        if a is not None:
            venue_player_ids.add(int(a))
        if b is not None:
            venue_player_ids.add(int(b))
        t = f.get("tour_id")
        if t is not None:
            try:
                venue_tour_ids.add(int(t))
            except (TypeError, ValueError):
                pass
    venue_rows = []
    if venue_player_ids and venue_tour_ids:
        ids_list = list(venue_player_ids)
        tours_list = list(venue_tour_ids)
        try:
            r = requests.get(
                f"{base}/player_venue_stats",
                headers=headers,
                params={
                    "select": "player_id,tour_id,win_count,match_count",
                    "player_id": "in.(" + ",".join(str(x) for x in ids_list) + ")",
                    "tour_id": "in.(" + ",".join(str(x) for x in tours_list) + ")",
                    "limit": 10000,
                },
                timeout=REQ_TIMEOUT,
            )
            if r.status_code == 200:
                venue_rows = r.json() or []
        except Exception:
            pass
    print(f"  Venue: loaded {len(venue_rows):,} rows (fixture players/tours only)")
    venue_lookup = {}
    for r in venue_rows:
        pid = r.get("player_id")
        tid = r.get("tour_id")
        m = _float(r.get("match_count"), 0) or 0
        if pid is not None and tid is not None and m > 0:
            w = _float(r.get("win_count"), 0) or 0
            venue_lookup[(int(pid), int(tid))] = w / m
    print(f"  Venue stats: {len(venue_lookup):,} rows" + (" (venue adjustment active)" if venue_lookup else " (none – run venue pipeline or create table)"))

    # 5b) Player record at altitude (win % at high-altitude venues by surface) – used when match is at altitude
    altitude_rows = []
    if venue_player_ids:
        try:
            r = requests.get(
                f"{base}/player_altitude_stats",
                headers=headers,
                params={"player_id": "in.(" + ",".join(str(x) for x in list(venue_player_ids)) + ")", "limit": 5000},
                timeout=REQ_TIMEOUT,
            )
            if r.status_code == 200:
                altitude_rows = r.json() or []
        except Exception:
            pass
    altitude_lookup = {}
    for r in altitude_rows:
        pid = r.get("player_id")
        surf = (r.get("surface") or "N/A").strip()
        if pid is not None and surf:
            w = _float(r.get("win_pct_at_altitude"), 0.5)
            altitude_lookup[(int(pid), surf)] = w
    print(f"  Altitude stats: {len(altitude_lookup):,} rows" + (" (player record at altitude active)" if altitude_lookup else " (run oncourt-compute-altitude-stats.py after derive-altitude)"))

    # 5c) League avg serve point win % per surface (for ratio p_a/p_b). Fallback to constants if missing.
    league_avg_by_surface = dict(SURFACE_LEAGUE_AVG)
    league_avg_from_db = 0
    try:
        r = requests.get(f"{base}/surface_league_averages", headers=headers, params={"select": "surface,serve_point_win_pct", "limit": 20}, timeout=REQ_TIMEOUT)
        if r.status_code == 200 and r.json():
            for row in r.json():
                surf = (row.get("surface") or "N/A").strip()
                pct = _float(row.get("serve_point_win_pct"))
                if surf and pct is not None:
                    league_avg_by_surface[surf] = pct
                    league_avg_from_db += 1
    except Exception:
        pass
    print(f"  League avg (surface): {league_avg_from_db} from DB" + (", rest constants" if league_avg_from_db < len(SURFACE_LEAGUE_AVG) else ""))

    # Map raw player_surface_stats scale -> SPW scale used by tennis_prob
    surface_hold_shift = {}
    surface_ret_shift = {}
    all_surfaces = set(surface_hold_prior.keys()) | set(surface_ret_prior.keys()) | set(league_avg_by_surface.keys())
    for surf in all_surfaces:
        raw_h = surface_hold_prior.get(surf, SURFACE_AVG_HOLD.get(surf, 0.44))
        raw_r = surface_ret_prior.get(surf, SURFACE_AVG_RETURN.get(surf, 0.35))
        spw = league_avg_by_surface.get(surf, SURFACE_LEAGUE_AVG.get(surf, 0.64))
        spw = _clamp(spw, 0.52, 0.72)
        surface_hold_shift[surf] = spw - raw_h
        surface_ret_shift[surf] = (1.0 - spw) - raw_r

    # 5d) Tournament avg total games (shift_from_surface for expected_total_games adjustment)
    tour_shift_lookup = {}
    if venue_tour_ids:
        try:
            r = requests.get(
                f"{base}/tournament_game_averages",
                headers=headers,
                params={"tour_id": "in.(" + ",".join(str(x) for x in list(venue_tour_ids)) + ")", "select": "tour_id,surface,shift_from_surface,match_count", "limit": 500},
                timeout=REQ_TIMEOUT,
            )
            if r.status_code == 200 and r.json():
                for row in r.json():
                    tid, surf = row.get("tour_id"), (row.get("surface") or "N/A").strip()
                    shift = row.get("shift_from_surface")
                    n = int(row.get("match_count") or 0)
                    if tid is not None and surf and shift is not None and n >= MIN_TOUR_MATCHES_FOR_SHIFT:
                        tour_shift_lookup[(int(tid), surf)] = {
                            "shift_from_surface": float(shift),
                            "match_count": n,
                        }
        except Exception:
            pass
    print(f"  Tournament totals shift: {len(tour_shift_lookup):,} rows" + (" (active)" if tour_shift_lookup else " (run oncourt-compute-tournament-avg-games.py)"))

    # 5d2) Tournament serve profile (venue_avg_spw) for expected-total-games: adjust p_a/p_b before K-M
    venue_serve_lookup = {}
    if venue_tour_ids:
        try:
            r_venue = requests.get(
                f"{base}/tournament_serve_profile",
                headers=headers,
                params={"tour_id": "in.(" + ",".join(str(x) for x in list(venue_tour_ids)) + ")", "select": "tour_id,surface,venue_avg_spw,match_count", "limit": 500},
                timeout=REQ_TIMEOUT,
            )
            if r_venue.status_code == 200 and r_venue.json():
                for row in r_venue.json():
                    tid, surf = row.get("tour_id"), (row.get("surface") or "N/A").strip()
                    spw = row.get("venue_avg_spw")
                    n = int(row.get("match_count") or 0)
                    if tid is not None and surf and spw is not None and n >= MIN_VENUE_SPW_MATCHES:
                        venue_serve_lookup[(int(tid), surf)] = {
                            "venue_avg_spw": float(spw),
                            "match_count": n,
                        }
        except Exception:
            pass
    if venue_serve_lookup:
        print(f"  Tournament serve profile: {len(venue_serve_lookup):,} rows (venue SPW adjustment active)")

    # 5e) Recent form / fatigue (player_recent_activity)
    recent_activity_by_player = {}
    fixture_player_ids = set()
    current_fixture_tour_ids = set()
    for f in fixtures:
        a, b = f.get("player1_id"), f.get("player2_id")
        tid_fixture = f.get("tour_id")
        if tid_fixture is not None:
            try:
                current_fixture_tour_ids.add(int(tid_fixture))
            except (TypeError, ValueError):
                pass
        if a is not None:
            fixture_player_ids.add(int(a))
        if b is not None:
            fixture_player_ids.add(int(b))
    # 5e0) Match-history features from oncourt_games:
    # YTD form, current streak, and same-tournament history across past years.
    recent_results_by_player = {}
    current_tournament_results_by_player_tour = {}
    tournament_history_by_player_key = {}
    history_start = date(max(2000, date.today().year - RESULTS_LOOKBACK_YEARS), 1, 1).isoformat()

    if fixture_player_ids:
        ids_list = list(fixture_player_ids)
        seen_hist = set()
        player_history = {pid: [] for pid in ids_list}

        for i in range(0, len(ids_list), 60):
            chunk = ids_list[i : i + 60]
            in_clause = "in.(" + ",".join(str(x) for x in chunk) + ")"

            for col in ("winner_id", "loser_id"):
                off = 0
                while True:
                    try:
                        r = requests.get(
                            f"{base}/oncourt_games",
                            headers=headers,
                            params={
                                "select": "winner_id,loser_id,tour_id,round_id,date,result",
                                col: in_clause,
                                "date": f"gte.{history_start}",
                                "offset": off,
                                "limit": 1000,
                            },
                            timeout=REQ_TIMEOUT,
                        )
                    except Exception:
                        break
                    if r.status_code != 200:
                        break

                    data = r.json() or []
                    if not data:
                        break

                    for row in data:
                        w = row.get("winner_id")
                        l = row.get("loser_id")
                        if w is None or l is None:
                            continue
                        try:
                            w = int(w)
                            l = int(l)
                        except (TypeError, ValueError):
                            continue

                        tid_hist = row.get("tour_id")
                        try:
                            tid_hist = int(tid_hist) if tid_hist is not None else None
                        except (TypeError, ValueError):
                            tid_hist = None

                        d_hist = _parse_iso_date(
                            row.get("date") or (tour_date_by_id.get(tid_hist) if tid_hist is not None else None)
                        )
                        if d_hist is None:
                            continue

                        rec_key = (w, l, tid_hist, int(row.get("round_id") or -1), d_hist.isoformat())
                        if rec_key in seen_hist:
                            continue
                        seen_hist.add(rec_key)

                        class_score = _tour_class_score(
                            tour_rank_by_id.get(tid_hist),
                            tour_name_by_id.get(tid_hist, ""),
                        )

                        if w in player_history:
                            player_history[w].append((d_hist, True, tid_hist, class_score))
                        if l in player_history:
                            player_history[l].append((d_hist, False, tid_hist, class_score))

                        if tid_hist in current_fixture_tour_ids and d_hist < date.today():
                            parsed_score = _score_games_for_winner(row.get("result"))
                            if parsed_score is not None:
                                w_games, l_games, w_sets, l_sets = parsed_score
                                w_key = (w, tid_hist)
                                l_key = (l, tid_hist)
                                w_rec = current_tournament_results_by_player_tour.setdefault(
                                    w_key,
                                    {"matches": 0, "games_for": 0, "games_against": 0, "sets_for": 0, "sets_against": 0},
                                )
                                l_rec = current_tournament_results_by_player_tour.setdefault(
                                    l_key,
                                    {"matches": 0, "games_for": 0, "games_against": 0, "sets_for": 0, "sets_against": 0},
                                )
                                w_rec["matches"] += 1
                                w_rec["games_for"] += w_games
                                w_rec["games_against"] += l_games
                                w_rec["sets_for"] += w_sets
                                w_rec["sets_against"] += l_sets
                                l_rec["matches"] += 1
                                l_rec["games_for"] += l_games
                                l_rec["games_against"] += w_games
                                l_rec["sets_for"] += l_sets
                                l_rec["sets_against"] += w_sets

                    off += len(data)
                    if len(data) < 1000:
                        break

        ytd_start = date(date.today().year, 1, 1)

        for pid, hist in player_history.items():
            hist.sort(key=lambda x: x[0], reverse=True)

            total_n = len(hist)
            ytd_hist = [h for h in hist if h[0] >= ytd_start]
            ytd_n = len(ytd_hist)
            ytd_w = sum(1 for _, is_win, _, _ in ytd_hist if is_win)

            last5_hist = hist[:5]
            last5_n = len(last5_hist)
            last5_w = sum(1 for _, is_win, _, _ in last5_hist if is_win)

            win_streak = 0
            loss_streak = 0
            if hist:
                first_is_win = hist[0][1]
                streak = 0
                for _, is_win, _, _ in hist:
                    if is_win == first_is_win:
                        streak += 1
                    else:
                        break
                if first_is_win:
                    win_streak = streak
                else:
                    loss_streak = streak

            recent12 = hist[:12]
            class_vals = [float(cls) for _, _, _, cls in recent12 if cls is not None]
            recent_class_avg = (sum(class_vals) / len(class_vals)) if class_vals else None
            recent_challenger_plus = sum(1 for _, _, _, cls in recent12 if cls is not None and cls >= 1.0)
            recent_atp_plus = sum(1 for _, _, _, cls in recent12 if cls is not None and cls >= 2.0)
            recent_masters_plus = sum(1 for _, _, _, cls in recent12 if cls is not None and cls >= 3.0)
            recent_slam_plus = sum(1 for _, _, _, cls in recent12 if cls is not None and cls >= 4.0)

            recent_results_by_player[pid] = {
                "matches_total": total_n,
                "ytd_matches": ytd_n,
                "ytd_wins": ytd_w,
                "ytd_win_rate": (ytd_w / ytd_n) if ytd_n > 0 else None,
                "last5_matches": last5_n,
                "last5_wins": last5_w,
                "last5_win_rate": (last5_w / last5_n) if last5_n > 0 else None,
                "win_streak": win_streak,
                "loss_streak": loss_streak,
                "recent_class_avg": recent_class_avg,
                "recent_challenger_plus_matches": recent_challenger_plus,
                "recent_atp_plus_matches": recent_atp_plus,
                "recent_masters_plus_matches": recent_masters_plus,
                "recent_slam_plus_matches": recent_slam_plus,
            }

            per_tour = {}
            for _, is_win, tid_hist, _ in hist:
                if tid_hist is None:
                    continue
                tkey = tour_key_by_id.get(tid_hist, "")
                if not tkey:
                    continue
                wins, matches = per_tour.get(tkey, (0, 0))
                wins += 1 if is_win else 0
                matches += 1
                per_tour[tkey] = (wins, matches)

            for tkey, (wins, matches) in per_tour.items():
                tournament_history_by_player_key[(pid, tkey)] = {"wins": wins, "matches": matches}

    players_with_hist = sum(
        1 for v in recent_results_by_player.values() if (v.get("matches_total") or 0) > 0
    )
    print(
        f"  Match history: {players_with_hist}/{len(fixture_player_ids)} players with matches since {history_start}, "
        f"tournament-history keys: {len(tournament_history_by_player_key):,}, "
        f"current-tournament keys: {len(current_tournament_results_by_player_tour):,}"
    )

    def _results_form_component(pid):
        rec = recent_results_by_player.get(pid) or {}
        d = 0.0

        ytd_n = int(rec.get("ytd_matches") or 0)
        ytd_wr = rec.get("ytd_win_rate")
        if ytd_n >= YTD_FORM_MIN_MATCHES and ytd_wr is not None:
            ytd_scale = min(1.0, ytd_n / 14.0)
            d += _clamp((float(ytd_wr) - 0.5) * YTD_FORM_WEIGHT * ytd_scale, -YTD_FORM_CAP, YTD_FORM_CAP)

        l5_n = int(rec.get("last5_matches") or 0)
        l5_wr = rec.get("last5_win_rate")
        if l5_n >= LAST5_FORM_MIN_MATCHES and l5_wr is not None:
            l5_scale = min(1.0, l5_n / 5.0)
            d += _clamp((float(l5_wr) - 0.5) * LAST5_FORM_WEIGHT * l5_scale, -LAST5_FORM_CAP, LAST5_FORM_CAP)

        loss_streak = int(rec.get("loss_streak") or 0)
        win_streak = int(rec.get("win_streak") or 0)

        if loss_streak >= STREAK_SOFT_START:
            streak_pen = (loss_streak - STREAK_SOFT_START + 1) * STREAK_UNIT
            if loss_streak >= STREAK_HARD_START:
                streak_pen += 0.006
            d -= min(STREAK_CAP, streak_pen)
        elif win_streak >= STREAK_SOFT_START:
            streak_boost = (win_streak - STREAK_SOFT_START + 1) * STREAK_UNIT
            if win_streak >= STREAK_HARD_START:
                streak_boost += 0.004
            d += min(STREAK_CAP, streak_boost)

        return _clamp(d, -RESULTS_FORM_TOTAL_CAP, RESULTS_FORM_TOTAL_CAP)

    def _current_tournament_component(pid, tid):
        if tid is None:
            return 0.0
        rec = current_tournament_results_by_player_tour.get((pid, tid)) or {}
        matches = int(rec.get("matches") or 0)
        if matches < CURRENT_TOURNAMENT_MIN_MATCHES:
            return 0.0
        games_for = float(rec.get("games_for") or 0.0)
        games_against = float(rec.get("games_against") or 0.0)
        total_games = games_for + games_against
        if total_games < 12:
            return 0.0
        dominance = (games_for - games_against) / total_games
        scale = min(1.0, matches / 3.0)
        return _clamp(
            dominance * CURRENT_TOURNAMENT_DOMINANCE_WEIGHT * scale,
            -CURRENT_TOURNAMENT_CAP,
            CURRENT_TOURNAMENT_CAP,
        )

    def _tournament_history_component(pid, tid):
        if tid is None:
            return 0.0
        tkey = tour_key_by_id.get(tid, "")
        if not tkey:
            return 0.0
        rec = tournament_history_by_player_key.get((pid, tkey))
        if not rec:
            return 0.0

        n = int(rec.get("matches") or 0)
        if n < TOURNAMENT_HISTORY_MIN_MATCHES:
            return 0.0

        w = int(rec.get("wins") or 0)
        wr = (w + TOURNAMENT_HISTORY_PRIOR_P * TOURNAMENT_HISTORY_PRIOR_K) / (n + TOURNAMENT_HISTORY_PRIOR_K)
        scale = min(1.0, n / 8.0)
        return _clamp((wr - 0.5) * TOURNAMENT_HISTORY_WEIGHT * scale, -TOURNAMENT_HISTORY_CAP, TOURNAMENT_HISTORY_CAP)

    def _is_form_crisis(pid):
        rec = recent_results_by_player.get(pid) or {}
        ytd_n = int(rec.get("ytd_matches") or 0)
        ytd_wr = rec.get("ytd_win_rate")
        loss_streak = int(rec.get("loss_streak") or 0)

        if loss_streak >= FORM_CRISIS_LOSS_STREAK:
            return True
        if ytd_n >= FORM_CRISIS_YTD_MIN_MATCHES and ytd_wr is not None and float(ytd_wr) <= FORM_CRISIS_YTD_WINRATE_MAX:
            return True
        return False

    def _form_crisis_shock(pid):
        rec = recent_results_by_player.get(pid) or {}
        if not _is_form_crisis(pid):
            return 0.0

        loss_streak = int(rec.get("loss_streak") or 0)
        ytd_n = int(rec.get("ytd_matches") or 0)
        ytd_wr = rec.get("ytd_win_rate")

        shock = FORM_CRISIS_SHOCK_BASE
        if loss_streak >= FORM_CRISIS_LOSS_STREAK:
            shock += (loss_streak - FORM_CRISIS_LOSS_STREAK + 1) * FORM_CRISIS_SHOCK_STREAK_UNIT
        if ytd_n >= FORM_CRISIS_YTD_MIN_MATCHES and ytd_wr is not None and float(ytd_wr) <= FORM_CRISIS_YTD_WINRATE_MAX:
            shock += FORM_CRISIS_SHOCK_YTD_BONUS

        return min(FORM_CRISIS_SHOCK_CAP, shock)
    if fixture_player_ids:
        try:
            r = requests.get(
                f"{base}/player_recent_activity",
                headers=headers,
                params={"player_id": "in.(" + ",".join(str(x) for x in list(fixture_player_ids)) + ")", "select": "player_id,matches_last_21d,wins_last_21d,win_rate_21d,matches_last_5d,played_yesterday,last_match_date,avg_opponent_elo", "limit": 500},
                timeout=REQ_TIMEOUT,
            )
            if r.status_code == 200 and r.json():
                for row in r.json():
                    pid = row.get("player_id")
                    if pid is not None:
                        recent_activity_by_player[int(pid)] = row
        except Exception:
            pass
    print(f"  Recent activity: {len(recent_activity_by_player):,} rows" + (" (form/fatigue active)" if recent_activity_by_player else " (run oncourt-compute-recent-activity.py)"))

    # --- V2 MODEL: load decomposed stats + recent games ---
    v2_model = None
    if HAS_LIVE_V2 and fixture_player_ids and venue_tour_ids and tour_to_surface:
        v2_model = LiveModelV2(url.rstrip("/"), _supabase_key)
        v2_model.load_data(fixture_player_ids, venue_tour_ids, tour_to_surface)
    # --- END V2 ---

    # 5f) H2H from authoritative match history (oncourt_games), not pre-aggregated table.
    h2h_lookup = {}
    h2h_source_rows = 0
    if fixture_player_ids:
        try:
            id_list = sorted(int(x) for x in fixture_player_ids)
            in_clause = "in.(" + ",".join(str(x) for x in id_list) + ")"
            off = 0
            while True:
                r = requests.get(
                    f"{base}/oncourt_games",
                    headers=headers,
                    params={
                        "select": "winner_id,loser_id,tour_id,date",
                        "winner_id": in_clause,
                        "loser_id": in_clause,
                        "offset": off,
                        "limit": 1000,
                    },
                    timeout=REQ_TIMEOUT,
                )
                if r.status_code != 200:
                    break
                data = r.json() or []
                if not data:
                    break

                h2h_source_rows += len(data)
                for row in data:
                    w = row.get("winner_id")
                    l = row.get("loser_id")
                    if w is None or l is None:
                        continue
                    try:
                        w = int(w)
                        l = int(l)
                    except (TypeError, ValueError):
                        continue
                    if w == l:
                        continue

                    tid_h2h = row.get("tour_id")
                    try:
                        tid_h2h = int(tid_h2h) if tid_h2h is not None else None
                    except (TypeError, ValueError):
                        tid_h2h = None

                    d_h2h = _parse_iso_date(
                        row.get("date") or (tour_date_by_id.get(tid_h2h) if tid_h2h is not None else None)
                    )
                    d_h2h_iso = d_h2h.isoformat() if d_h2h is not None else None

                    surf = (tour_to_surface.get(tid_h2h) or "N/A") if tid_h2h is not None else "N/A"
                    if not surf:
                        surf = "N/A"

                    a, b = (w, l) if w < l else (l, w)
                    winner_is_a = (w == a)

                    def _bump(key_surf):
                        rec = h2h_lookup.get((a, b, key_surf))
                        if rec is None:
                            rec = {
                                "player_a_id": a,
                                "player_b_id": b,
                                "wins_a": 0,
                                "wins_b": 0,
                                "match_count": 0,
                                "last_match_date": None,
                            }
                            h2h_lookup[(a, b, key_surf)] = rec
                        if winner_is_a:
                            rec["wins_a"] += 1
                        else:
                            rec["wins_b"] += 1
                        rec["match_count"] += 1
                        if d_h2h_iso and (rec["last_match_date"] is None or d_h2h_iso > rec["last_match_date"]):
                            rec["last_match_date"] = d_h2h_iso

                    # Surface-specific record
                    _bump(surf)
                    # All-surface fallback record
                    if surf != "N/A":
                        _bump("N/A")

                off += len(data)
                if len(data) < 1000:
                    break
        except Exception:
            pass
    def _get_h2h_row(pid1, pid2, surf):
        a, b = (pid1, pid2) if pid1 < pid2 else (pid2, pid1)
        for s in _surface_candidates(surf):
            rec = h2h_lookup.get((a, b, s))
            if rec:
                return rec
        return None
    print(
        f"  H2H: {len(h2h_lookup):,} rows"
        + (f" from oncourt_games ({h2h_source_rows:,} source rows)" if h2h_lookup else " (none from oncourt_games)")
    )

    # 5g) Advanced player stats
    adv_rows = []
    try:
        off = 0
        while True:
            r = requests.get(
                f"{base}/player_advanced_stats",
                headers=headers,
                params={"select": "player_id,surface,first_serve_pct,first_serve_win_pct,second_serve_win_pct,ace_rate,df_rate,bp_save_pct,bp_convert_pct,match_count", "offset": off, "limit": 1000},
                timeout=REQ_TIMEOUT,
            )
            if r.status_code != 200:
                break
            data = r.json()
            if not data:
                break
            adv_rows.extend(data)
            off += len(data)
            if len(data) < 1000:
                break
    except Exception:
        pass
    advanced_lookup = {}
    for row in adv_rows:
        pid = row.get("player_id")
        surf = (row.get("surface") or "N/A").strip()
        if pid is None or not surf:
            continue
        advanced_lookup[(int(pid), surf)] = row
    def _get_advanced_row(pid, surf):
        for s in _surface_candidates(surf):
            rec = advanced_lookup.get((pid, s))
            if rec:
                return rec
        return None
    print(f"  Advanced stats: {len(advanced_lookup):,} rows" + (" (active)" if advanced_lookup else " (none - run sackmann-compute-advanced-stats.py)"))

    birthdate_by_player = {}
    atp_rank_by_player = {}
    surface_points_by_player = {}  # pid -> {"Hard": x, "Clay": y, "Grass": z} from OnCourt
    name_by_player = {}
    player_select = "id,name,birthdate,atp_rank,hard_points,clay_points,grass_points"
    if fixture_player_ids:
        ids_list = list(fixture_player_ids)
        for i in range(0, len(ids_list), 100):
            chunk = ids_list[i : i + 100]
            r = requests.get(
                f"{base}/oncourt_players",
                headers=headers,
                params={"id": "in.(" + ",".join(str(x) for x in chunk) + ")", "select": player_select},
                timeout=REQ_TIMEOUT,
            )
            if r.status_code == 400:
                r = requests.get(
                    f"{base}/oncourt_players",
                    headers=headers,
                    params={"id": "in.(" + ",".join(str(x) for x in chunk) + ")", "select": "id,name,birthdate,atp_rank"},
                    timeout=REQ_TIMEOUT,
                )
            if r.status_code == 200:
                for row in r.json():
                    if row.get("id") is not None:
                        pid = int(row["id"])
                        name_by_player[pid] = (row.get("name") or "").strip()
                        birthdate_by_player[pid] = row.get("birthdate")
                        rk = row.get("atp_rank")
                        if rk is not None and str(rk).strip() != "":
                            try:
                                atp_rank_by_player[pid] = int(float(rk))
                            except (ValueError, TypeError):
                                pass
                        hp = _float(row.get("hard_points")); cp = _float(row.get("clay_points")); gp = _float(row.get("grass_points"))
                        if hp is not None or cp is not None or gp is not None:
                            surface_points_by_player[pid] = {"Hard": hp, "Clay": cp, "Grass": gp, "I.hard": hp}
    print(f"  Players (birthdate + atp_rank): {len(birthdate_by_player)} with birthdate, {len(atp_rank_by_player)} with rank, {len(surface_points_by_player)} with surface points")
    # Warn if same surname appears for multiple players in today's fixtures (e.g. two Cerundolos) – wrong ID in OnCourt today_atp can cause wrong odds
    surname_to_players = {}
    skip_surnames = {"player", "unknown", "tbd", "tba"}  # ignore placeholders
    for pid in fixture_player_ids:
        name = name_by_player.get(pid, "")
        parts = (name or "").strip().split()
        sn = (parts[-1] if parts else "").strip().lower()
        if sn and sn not in skip_surnames:
            surname_to_players.setdefault(sn, []).append((pid, name))
    for sn, plist in surname_to_players.items():
        if len(plist) > 1:
            print(f"  WARNING: Same surname '{sn}' for multiple players in today's fixtures: {plist}. If odds look wrong, check OnCourt today_atp has the correct player ID for each match (e.g. F. vs J.M. Cerundolo).")

    injury_downweight_enabled = env_bool(os.environ.get("FAIR_ODDS_INJURY_DOWNWEIGHT_ENABLED"), False)
    injury_lookback_days = max(
        0,
        _env_int(
            "FAIR_ODDS_INJURY_LOOKBACK_DAYS",
            _env_int("STRICT_INJURY_LOOKBACK_DAYS", DEFAULT_FAIR_ODDS_INJURY_LOOKBACK_DAYS),
        ),
    )
    injury_delta = _clamp(_env_float("FAIR_ODDS_INJURY_DELTA", DEFAULT_FAIR_ODDS_INJURY_DELTA), 0.0, 0.08)
    injury_csv = os.environ.get("INJURED_PLAYERS_CSV", DEFAULT_INJURY_CSV)
    injury_index = load_recent_injury_index(
        injury_csv,
        lookback_days=injury_lookback_days,
        today=date.today(),
        include_sources=("injured",),
    )
    injury_flagged_p1 = 0
    injury_flagged_p2 = 0
    injury_adjusted_matches = 0
    print(
        f"  Injury list: {injury_index.rows_recent}/{injury_index.rows_loaded} recent rows "
        f"(lookback {injury_lookback_days}d, downweight={'on' if injury_downweight_enabled else 'off'}, "
        f"delta={injury_delta:.3f})"
    )

    cpi_enabled = env_bool(os.environ.get("FAIR_ODDS_CPI_ENABLED"), False)
    cpi_lookback_years = max(0, _env_int("FAIR_ODDS_CPI_FALLBACK_YEARS", DEFAULT_CPI_LOOKBACK_YEARS))
    cpi_match_weight = _clamp(_env_float("FAIR_ODDS_CPI_MATCH_WEIGHT", DEFAULT_CPI_MATCH_WEIGHT), 0.0, 0.15)
    cpi_match_cap = _clamp(_env_float("FAIR_ODDS_CPI_MATCH_CAP", DEFAULT_CPI_MATCH_CAP), 0.0, 0.08)
    cpi_z_cap = _clamp(_env_float("FAIR_ODDS_CPI_Z_CAP", DEFAULT_CPI_Z_CAP), 0.2, 6.0)
    cpi_total_ratio_weight = _clamp(
        _env_float("FAIR_ODDS_CPI_TOTAL_RATIO_WEIGHT", DEFAULT_CPI_TOTAL_RATIO_WEIGHT),
        0.0,
        0.20,
    )
    cpi_total_ratio_min = _clamp(
        _env_float("FAIR_ODDS_CPI_TOTAL_RATIO_MIN", DEFAULT_CPI_TOTAL_RATIO_CLAMP[0]),
        0.80,
        1.00,
    )
    cpi_total_ratio_max = _clamp(
        _env_float("FAIR_ODDS_CPI_TOTAL_RATIO_MAX", DEFAULT_CPI_TOTAL_RATIO_CLAMP[1]),
        1.00,
        1.20,
    )
    if cpi_total_ratio_min > cpi_total_ratio_max:
        cpi_total_ratio_min, cpi_total_ratio_max = cpi_total_ratio_max, cpi_total_ratio_min
    cpi_with_venue_blend = _clamp(
        _env_float("FAIR_ODDS_CPI_WITH_VENUE_BLEND", DEFAULT_CPI_WITH_VENUE_BLEND),
        0.0,
        1.0,
    )
    tournament_speed_point_weight = _clamp(
        _env_float("FAIR_ODDS_TOUR_SPEED_POINT_WEIGHT", DEFAULT_TOURNAMENT_SPEED_POINT_WEIGHT),
        0.0,
        0.40,
    )

    cpi_lookup = {}
    cpi_year_surface_stats = {}
    cpi_surface_stats = {}
    cpi_resolved_matches = 0
    cpi_delta_applied_matches = 0
    cpi_total_used_matches = 0
    cpi_rows_loaded = 0
    tournament_speed_resolved_matches = 0
    tournament_speed_adjusted_matches = 0

    if cpi_enabled:
        fixture_tour_ids = set()
        fixture_years = set()
        for f in fixtures:
            tid_raw = f.get("tour_id")
            if tid_raw is None:
                continue
            try:
                tid_i = int(tid_raw)
            except (TypeError, ValueError):
                continue
            fixture_tour_ids.add(tid_i)
            td = _parse_iso_date(tour_date_by_id.get(tid_i))
            if td is not None:
                fixture_years.add(td.year)
        if not fixture_years:
            fixture_years.add(date.today().year)
        min_year = max(1980, min(fixture_years) - cpi_lookback_years)
        max_year = max(fixture_years)

        cpi_rows = []
        try:
            off = 0
            while True:
                r = requests.get(
                    f"{base}/tournament_surface_speed",
                    headers=headers,
                    params={
                        "select": "season_year,surface,tournament_key,cpi",
                        "and": f"(season_year.gte.{min_year},season_year.lte.{max_year})",
                        "offset": off,
                        "limit": 1000,
                    },
                    timeout=REQ_TIMEOUT,
                )
                if r.status_code != 200:
                    break
                data = r.json() or []
                if not data:
                    break
                cpi_rows.extend(data)
                off += len(data)
                if len(data) < 1000:
                    break
        except Exception:
            pass

        stats_by_year_surface = {}
        stats_by_surface = {}
        for row in cpi_rows:
            y = row.get("season_year")
            surf_raw = (row.get("surface") or "").strip()
            tkey = (row.get("tournament_key") or "").strip()
            cpi_val = _float(row.get("cpi"))
            if y is None or not surf_raw or not tkey or cpi_val is None:
                continue
            try:
                y = int(y)
            except (TypeError, ValueError):
                continue
            surf = "Hard" if surf_raw == "I.hard" else surf_raw
            if surf not in ("Hard", "Clay", "Grass"):
                continue
            cpi_lookup[(y, surf, tkey)] = float(cpi_val)
            stats_by_year_surface.setdefault((y, surf), []).append(float(cpi_val))
            stats_by_surface.setdefault(surf, []).append(float(cpi_val))

        cpi_rows_loaded = len(cpi_lookup)
        for key, vals in stats_by_year_surface.items():
            cpi_year_surface_stats[key] = _mean_std(vals)
        for surf, vals in stats_by_surface.items():
            cpi_surface_stats[surf] = _mean_std(vals)

        print(
            f"  CPI rows: {cpi_rows_loaded:,} "
            f"(years {min_year}-{max_year}, fallback {cpi_lookback_years}y, "
            f"match_weight={cpi_match_weight:.3f}, total_ratio_weight={cpi_total_ratio_weight:.3f})"
        )
    else:
        print("  CPI rows: disabled (set FAIR_ODDS_CPI_ENABLED=true to activate)")

    def _resolve_cpi_for_match(tid, surface):
        if not cpi_lookup or tid is None:
            return (None, None, "none")
        tname = tour_name_by_id.get(tid, "")
        if not tname:
            return (None, None, "missing_tour")
        td = _parse_iso_date(tour_date_by_id.get(tid))
        season_year = td.year if td is not None else date.today().year
        keys = _tour_key_candidates(tname)
        if not keys:
            return (None, season_year, "missing_key")

        surf_candidates = []
        for s in _surface_candidates(surface):
            ss = "Hard" if s == "I.hard" else s
            if ss in ("Hard", "Clay", "Grass") and ss not in surf_candidates:
                surf_candidates.append(ss)
        if not surf_candidates:
            surf_candidates = ["Hard", "Clay", "Grass"]

        for yr_back in range(0, cpi_lookback_years + 1):
            y = season_year - yr_back
            for surf in surf_candidates:
                for tkey in keys:
                    v = cpi_lookup.get((y, surf, tkey))
                    if v is not None:
                        mode = "exact_year" if yr_back == 0 else f"fallback_y{yr_back}"
                        return (float(v), y, mode)
        return (None, season_year, "missing")

    def _cpi_z_score(cpi_value, season_year, surface):
        if cpi_value is None:
            return 0.0
        surf = "Hard" if surface == "I.hard" else surface
        mean, std = cpi_year_surface_stats.get((season_year, surf), cpi_surface_stats.get(surf, (0.0, 1.0)))
        if std <= 1e-9:
            std = 1.0
        z = (float(cpi_value) - mean) / std
        return _clamp(z, -cpi_z_cap, cpi_z_cap)

    do_debug = "--debug" in sys.argv
    debug_names = []
    for i, arg in enumerate(sys.argv):
        if arg == "--debug" and i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("-"):
            debug_names = [s.strip().lower() for s in sys.argv[i + 1].split(",") if s.strip()]
            break
    if "--debug" in sys.argv and not debug_names:
        debug_names = ["cerundolo"]  # default

    out = []
    skip_no_players = 0
    skip_doubles = 0
    skip_unknown = 0
    skip_same_player = 0
    skip_missing_both = 0
    skip_missing_p1 = 0
    skip_missing_p2 = 0
    surface_points_guarded_matches = 0
    surface_counts = {}
    for f in fixtures:
        tour_id = f.get("tour_id")
        p1 = f.get("player1_id")
        p2 = f.get("player2_id")
        round_id = f.get("round_id")
        draw = f.get("draw")
        if p1 is None or p2 is None:
            skip_no_players += 1
            continue
        p1, p2 = int(p1), int(p2)
        if p1 == p2:
            skip_same_player += 1
            continue
        n1 = (name_by_player.get(p1) or "")
        n2 = (name_by_player.get(p2) or "")
        n1_l = n1.lower()
        n2_l = n2.lower()
        if p1 in UNKNOWN_PLAYER_IDS or p2 in UNKNOWN_PLAYER_IDS or "unknown player" in n1_l or "unknown player" in n2_l:
            skip_unknown += 1
            continue
        if "/" in n1 or "/" in n2 or "&" in n1 or "&" in n2:
            skip_doubles += 1
            continue
        p1_recent_injured, p1_injury_mode = injury_index.match_name(n1)
        p2_recent_injured, p2_injury_mode = injury_index.match_name(n2)
        if p1_recent_injured:
            injury_flagged_p1 += 1
        if p2_recent_injured:
            injury_flagged_p2 += 1
        try:
            tid = int(tour_id) if tour_id is not None else None
        except (TypeError, ValueError):
            tid = None
        surface = (tour_to_surface.get(tid) or "N/A") if tid is not None else "N/A"
        surface_counts[surface] = surface_counts.get(surface, 0) + 1
        tour_name = tour_name_by_id.get(tid, "")
        series_bucket = _series_bucket_from_tour(tour_name, tour_rank_by_id.get(tid))
        is_challenger = _is_challenger_tour(tour_name)
        current_class_score = _tour_class_score(tour_rank_by_id.get(tid), tour_name)
        is_best_of_5 = series_bucket == "Grand Slam"

        cpi_value = None
        cpi_year = None
        cpi_mode = "off"
        cpi_z = 0.0
        if cpi_enabled:
            cpi_value, cpi_year, cpi_mode = _resolve_cpi_for_match(tid, surface)
            if cpi_value is not None and cpi_year is not None:
                cpi_resolved_matches += 1
                cpi_z = _cpi_z_score(cpi_value, cpi_year, surface)

        s1 = stats.get((p1, surface))
        s2 = stats.get((p2, surface))
        e1_s = elo_lookup.get((p1, surface), DEFAULT_ELO)
        e2_s = elo_lookup.get((p2, surface), DEFAULT_ELO)
        e1_o = elo_lookup.get((p1, "Overall"))
        e2_o = elo_lookup.get((p2, "Overall"))

        # Track whether player has real Elo (not default 1500)
        e1_is_real = (p1, surface) in elo_lookup or (p1, "Overall") in elo_lookup
        e2_is_real = (p2, surface) in elo_lookup or (p2, "Overall") in elo_lookup

        # Determine confidence and whether we have stats
        has_s1 = s1 is not None
        has_s2 = s2 is not None
        if not has_s1 and not has_s2:
            skip_missing_both += 1
        elif not has_s1:
            skip_missing_p1 += 1
        elif not has_s2:
            skip_missing_p2 += 1

        surf_hold = surface_hold_prior.get(surface, SURFACE_AVG_HOLD.get(surface, 0.44))
        surf_ret = surface_ret_prior.get(surface, SURFACE_AVG_RETURN.get(surface, 0.35))

        # Blend 12m with long-window (36m); use surface priors as fallback when stats missing
        h1_12 = _float((s1 or {}).get("hold_pct"), surf_hold)
        r1_12 = _float((s1 or {}).get("return_pct"), surf_ret)
        h2_12 = _float((s2 or {}).get("hold_pct"), surf_hold)
        r2_12 = _float((s2 or {}).get("return_pct"), surf_ret)
        h1_long = _float((s1 or {}).get("hold_pct_long"), h1_12)
        r1_long = _float((s1 or {}).get("return_pct_long"), r1_12)
        h2_long = _float((s2 or {}).get("hold_pct_long"), h2_12)
        r2_long = _float((s2 or {}).get("return_pct_long"), r2_12)

        mc1_12 = int((s1 or {}).get("match_count") or 0) if has_s1 else 0
        mc2_12 = int((s2 or {}).get("match_count") or 0) if has_s2 else 0
        min_matches_12 = min(mc1_12, mc2_12)
        r1 = atp_rank_by_player.get(p1)
        r2 = atp_rank_by_player.get(p2)
        p1_hist = recent_results_by_player.get(p1) or {}
        p2_hist = recent_results_by_player.get(p2) or {}
        both_elo_default = not e1_is_real and not e2_is_real

        if both_elo_default and p1_hist.get("matches_total", 0) == 0 and p2_hist.get("matches_total", 0) == 0 and not has_s1 and not has_s2:
            confidence = "none"
        elif not has_s1 and not has_s2:
            confidence = "low"
        elif not has_s1 or not has_s2:
            confidence = "low" if min(mc1_12, mc2_12) < 5 else "medium"
        elif min(mc1_12, mc2_12) < 5:
            confidence = "medium"
        elif min(mc1_12, mc2_12) >= 10:
            confidence = "high"
        else:
            confidence = "medium"

        if confidence in ("high", "medium"):
            if p1 not in recent_activity_by_player or p2 not in recent_activity_by_player:
                confidence = "medium" if confidence == "high" else "low"

        p1_established = _is_established_player(r1, e1_s, e1_o, mc1_12)
        p2_established = _is_established_player(r2, e2_s, e2_o, mc2_12)
        class_penalty_elo_1, class_sample_mult_1 = _class_jump_adjustment(
            p1_hist, current_class_score, confidence, p2_established, p1_established
        )
        class_penalty_elo_2, class_sample_mult_2 = _class_jump_adjustment(
            p2_hist, current_class_score, confidence, p1_established, p2_established
        )

        if min_matches_12 >= 25:
            recent_weight = 0.75
        elif min_matches_12 >= 15:
            recent_weight = 0.6
        elif min_matches_12 >= 8:
            recent_weight = 0.5
        else:
            recent_weight = 0.3

        if surface == "Clay":
            recent_weight = min(recent_weight, 0.6)
        elif surface == "Grass":
            recent_weight = max(recent_weight, 0.55)

        hold1_raw = recent_weight * h1_12 + (1.0 - recent_weight) * h1_long
        ret1_raw = recent_weight * r1_12 + (1.0 - recent_weight) * r1_long
        hold2_raw = recent_weight * h2_12 + (1.0 - recent_weight) * h2_long
        ret2_raw = recent_weight * r2_12 + (1.0 - recent_weight) * r2_long

        # Shrinkage toward surface priors when sample is low
        mc1_eff = mc1_12 * class_sample_mult_1
        mc2_eff = mc2_12 * class_sample_mult_2
        alpha1 = mc1_eff / (mc1_eff + SHRINKAGE_N) if mc1_eff else 0.0
        alpha2 = mc2_eff / (mc2_eff + SHRINKAGE_N) if mc2_eff else 0.0
        hold1 = alpha1 * hold1_raw + (1.0 - alpha1) * surf_hold if alpha1 > 0 else surf_hold
        ret1 = alpha1 * ret1_raw + (1.0 - alpha1) * surf_ret if alpha1 > 0 else surf_ret
        hold2 = alpha2 * hold2_raw + (1.0 - alpha2) * surf_hold if alpha2 > 0 else surf_hold
        ret2 = alpha2 * ret2_raw + (1.0 - alpha2) * surf_ret if alpha2 > 0 else surf_ret

        # Convert raw stats scale -> SPW scale expected by tennis_prob
        hold_shift = surface_hold_shift.get(surface, 0.0)
        ret_shift = surface_ret_shift.get(surface, 0.0)

        hold1_eff = _clamp(hold1 + hold_shift, POINT_CLAMP[0], POINT_CLAMP[1])
        hold2_eff = _clamp(hold2 + hold_shift, POINT_CLAMP[0], POINT_CLAMP[1])
        ret1_eff = _clamp(ret1 + ret_shift, RETURN_CLAMP[0], RETURN_CLAMP[1])
        ret2_eff = _clamp(ret2 + ret_shift, RETURN_CLAMP[0], RETURN_CLAMP[1])

        # p_A / p_B: use LiveModelV2 (matchup + fallback) when available
        league_avg = league_avg_by_surface.get(surface, 0.64)
        if league_avg <= 0 or league_avg >= 1:
            league_avg = 0.64
        tour_speed_signal = 0.0
        tour_speed_debug = {}
        if tournament_speed_point_weight > 0.0 and tour_id is not None:
            venue_entry = venue_serve_lookup.get((int(tour_id), surface))
            tour_shift_entry = tour_shift_lookup.get((int(tour_id), surface))
            tour_speed_signal, tour_speed_debug = _compute_tournament_speed_signal(
                league_avg=league_avg,
                venue_entry=venue_entry,
                tour_shift_entry=tour_shift_entry,
            )
            if abs(tour_speed_signal) > 1e-9:
                tournament_speed_resolved_matches += 1

        hold1_model = hold1_eff
        hold2_model = hold2_eff
        ret1_model = ret1_eff
        ret2_model = ret2_eff
        tour_speed_multiplier = 0.0
        if abs(tour_speed_signal) > 1e-9 and tournament_speed_point_weight > 0.0:
            tour_speed_multiplier = _clamp(
                tour_speed_signal * tournament_speed_point_weight,
                -0.35,
                0.35,
            )
            return_baseline = 1.0 - league_avg
            hold1_model = _clamp(league_avg + (hold1_eff - league_avg) * (1.0 + tour_speed_multiplier), POINT_CLAMP[0], POINT_CLAMP[1])
            hold2_model = _clamp(league_avg + (hold2_eff - league_avg) * (1.0 + tour_speed_multiplier), POINT_CLAMP[0], POINT_CLAMP[1])
            ret1_model = _clamp(return_baseline + (ret1_eff - return_baseline) * (1.0 - tour_speed_multiplier), RETURN_CLAMP[0], RETURN_CLAMP[1])
            ret2_model = _clamp(return_baseline + (ret2_eff - return_baseline) * (1.0 - tour_speed_multiplier), RETURN_CLAMP[0], RETURN_CLAMP[1])
            tournament_speed_adjusted_matches += 1

        if v2_model is not None:
            p_a, p_b, _ = v2_model.point_probs(
                p1, p2, surface,
                hold1=hold1_model, ret1=ret1_model,
                hold2=hold2_model, ret2=ret2_model,
                league_avg=league_avg,
            )
            p_a = _clamp(p_a, POINT_CLAMP[0], POINT_CLAMP[1])
            p_b = _clamp(p_b, POINT_CLAMP[0], POINT_CLAMP[1])
        elif HAS_MATCHUP_MODEL and (s1 or s2):
            def _blend(s, k12, klong):
                v12 = _float((s or {}).get(k12))
                vlong = _float((s or {}).get(klong), v12)
                if v12 is None:
                    return vlong
                if vlong is None:
                    return v12
                return recent_weight * v12 + (1.0 - recent_weight) * vlong

            def _build_matchup_row(s, hold_val, ret_val):
                row = {
                    "hold_pct": hold_val, "return_pct": ret_val,
                    "match_count": int((s or {}).get("match_count") or 0),
                    "service_pts": int((s or {}).get("service_pts") or 0),
                }
                if s:
                    row["first_serve_pct"] = _blend(s, "first_serve_pct", "first_serve_pct_long")
                    row["first_serve_win_pct"] = _blend(s, "first_serve_win_pct", "first_serve_win_pct_long")
                    row["second_serve_win_pct"] = _blend(s, "second_serve_win_pct", "second_serve_win_pct_long")
                    row["ace_rate"] = _float(s.get("ace_rate"))
                    row["df_rate"] = _float(s.get("df_rate"))
                    row["bp_save_rate"] = _float(s.get("bp_save_rate"))
                    row["bp_convert_rate"] = _float(s.get("bp_convert_rate"))
                return row

            # Use venue-speed adjusted SPW values when available, consistent with
            # the fallback branch and tennis_prob expectations.
            row1 = _build_matchup_row(s1, hold1_model, ret1_model)
            row2 = _build_matchup_row(s2, hold2_model, ret2_model)
            stats_a = MatchupStats.from_db_row(row1)
            stats_b = MatchupStats.from_db_row(row2)
            p_a, p_b, _ = compute_match_point_probs(stats_a, stats_b, surface)
        else:
            p_a = (hold1_model * (1.0 - ret2_model)) / league_avg
            p_b = (hold2_model * (1.0 - ret1_model)) / league_avg
            p_a = _clamp(p_a, POINT_CLAMP[0], POINT_CLAMP[1])
            p_b = _clamp(p_b, POINT_CLAMP[0], POINT_CLAMP[1])

        p_serve_return = prob_match_best_of_5(p_a, p_b) if is_best_of_5 else prob_match_best_of_3(p_a, p_b)

        def _recent_reliability(pid):
            act = recent_activity_by_player.get(pid)
            if not act:
                age = _age_years(birthdate_by_player.get(pid))
                rel = 0.72
                if age is not None and age >= 31:
                    rel -= min(0.24, (age - 31) * 0.025)
                return max(ELO_RELIABILITY_MIN, rel)
            m21 = int(act.get("matches_last_21d") or 0)
            if m21 >= 8:
                return 1.00
            if m21 >= 5:
                return 0.95
            if m21 >= 3:
                return 0.90
            if m21 >= 1:
                return 0.84
            last_d = act.get("last_match_date")
            if last_d:
                try:
                    ld = date.fromisoformat(str(last_d)[:10])
                    days = (date.today() - ld).days
                    if days >= 90:
                        return 0.55
                    if days >= 60:
                        return 0.65
                    if days >= 35:
                        return 0.75
                except (ValueError, TypeError):
                    pass
            return 0.80

        rel1 = _recent_reliability(p1)
        rel2 = _recent_reliability(p2)
        elo_reliability = 0.5 * (rel1 + rel2)

        # Reliability-adjust Elo per player (directional; stale player is penalized individually)
        e1_s_eff = DEFAULT_ELO + rel1 * ((e1_s - class_penalty_elo_1) - DEFAULT_ELO)
        e2_s_eff = DEFAULT_ELO + rel2 * ((e2_s - class_penalty_elo_2) - DEFAULT_ELO)
        p_elo_surface = 1.0 / (1.0 + 10.0 ** ((e2_s_eff - e1_s_eff) / 400.0))

        if e1_o is not None and e2_o is not None:
            e1_o_eff = DEFAULT_ELO + rel1 * ((float(e1_o) - class_penalty_elo_1 * 0.75) - DEFAULT_ELO)
            e2_o_eff = DEFAULT_ELO + rel2 * ((float(e2_o) - class_penalty_elo_2 * 0.75) - DEFAULT_ELO)
            p_elo_overall = 1.0 / (1.0 + 10.0 ** ((e2_o_eff - e1_o_eff) / 400.0))
            p_elo = 0.5 * p_elo_surface + 0.5 * p_elo_overall
        else:
            p_elo = p_elo_surface

        # Rank/points prior (stronger class-gap separation than old linear blend)
        pts1 = surface_points_by_player.get(p1, {}).get(surface) if surface in ("Hard", "Clay", "Grass", "I.hard") else None
        pts2 = surface_points_by_player.get(p2, {}).get(surface) if surface in ("Hard", "Clay", "Grass", "I.hard") else None

        p_rank = None
        p_rank_atp = None
        p_rank_points = None
        synthetic_r1 = None
        synthetic_r2 = None

        rank1_eff = r1
        rank2_eff = r2
        if (rank1_eff is None or rank1_eff <= 0) and (rank2_eff is not None and rank2_eff > 0):
            synthetic_r1 = _synthetic_rank_for_unranked(p1_hist, current_class_score, confidence, p2_established)
            if synthetic_r1 is not None:
                rank1_eff = synthetic_r1
        if (rank2_eff is None or rank2_eff <= 0) and (rank1_eff is not None and rank1_eff > 0):
            synthetic_r2 = _synthetic_rank_for_unranked(p2_hist, current_class_score, confidence, p1_established)
            if synthetic_r2 is not None:
                rank2_eff = synthetic_r2

        if rank1_eff is not None and rank2_eff is not None and rank1_eff > 0 and rank2_eff > 0:
            log_ratio = math.log(max(1.0, float(rank2_eff)) / max(1.0, float(rank1_eff)))
            p_rank_atp = _sigmoid(log_ratio / RANK_LOGIT_SCALE)
            rr = max(rank1_eff, rank2_eff) / float(min(rank1_eff, rank2_eff))
            if rr >= RANK_CLASS_GAP_RATIO_START:
                extra = min(RANK_CLASS_GAP_CAP, math.log(rr / RANK_CLASS_GAP_RATIO_START) * 0.08)
                p_rank_atp = _clamp(p_rank_atp + (extra if rank1_eff < rank2_eff else -extra), 0.02, 0.98)

        if pts1 is not None and pts2 is not None and (pts1 > 0 or pts2 > 0):
            log_pts_ratio = math.log((max(0.0, pts1) + POINTS_MIN_BASE) / (max(0.0, pts2) + POINTS_MIN_BASE))
            p_rank_points = _sigmoid(log_pts_ratio / POINTS_LOGIT_SCALE)

        if p_rank_atp is not None and p_rank_points is not None:
            p_rank = (1.0 - RANK_POINTS_BLEND) * p_rank_atp + RANK_POINTS_BLEND * p_rank_points
        elif p_rank_atp is not None:
            p_rank = p_rank_atp
        elif p_rank_points is not None:
            p_rank = p_rank_points

        form_mult, results_mult, structural_mult, cap_mult = _series_delta_multipliers(series_bucket, surface, confidence)

        # Blend in logit space (better behavior than linear prob mix when components disagree)
        serve_rel = min(1.0, min(mc1_eff, mc2_eff) / float(HYBRID_ELO_WEIGHT_MIN_MATCHES)) if (has_s1 and has_s2) else 0.0
        w_sr = (1.0 - HYBRID_ELO_WEIGHT_DEFAULT) * (0.35 + 0.65 * serve_rel) if (has_s1 and has_s2) else 0.0
        w_sr *= math.sqrt(class_sample_mult_1 * class_sample_mult_2)
        w_elo = HYBRID_ELO_WEIGHT_DEFAULT * (0.65 + 0.35 * elo_reliability)
        w_elo *= _series_elo_weight_multiplier(series_bucket, confidence, is_challenger)

        w_rank = 0.0
        rank_gap_strength = 0.0
        elo_magnitude_release = 0.0
        if p_rank is not None:
            if rank1_eff is not None and rank2_eff is not None and rank1_eff > 0 and rank2_eff > 0:
                rr = max(rank1_eff, rank2_eff) / float(min(rank1_eff, rank2_eff))
                rank_strength = _clamp((rr - 1.0) / 3.0, 0.25, 1.0)
            else:
                rank_strength = 0.45
            rank_gap_strength = _clamp(abs(p_rank - 0.5) * 2.0, 0.0, 1.0)
            w_rank = 0.18 + 0.34 * rank_strength + 0.10 * rank_gap_strength

            # If rank and Elo disagree strongly, reduce Elo dominance.
            if (p_rank - 0.5) * (p_elo - 0.5) < 0:
                w_elo *= max(0.45, 1.0 - 0.75 * rank_gap_strength)
                w_sr *= max(0.70, 1.0 - 0.35 * rank_gap_strength)
                w_rank += 0.18 * rank_gap_strength
            w_rank *= _series_rank_weight_multiplier(series_bucket, confidence)
            w_sr, w_elo, w_rank, elo_magnitude_release = _apply_elo_magnitude_guard(
                w_sr,
                w_elo,
                w_rank,
                p_serve_return,
                p_elo,
                p_rank,
                is_challenger,
            )
            w_sr, w_elo, w_rank, surface_rank_conflict_release = _apply_surface_rank_conflict_guard(
                w_sr,
                w_elo,
                w_rank,
                p_serve_return,
                p_elo,
                p_rank,
                surface,
                series_bucket,
                confidence,
            )
        else:
            surface_rank_conflict_release = 0.0

        if not has_s1 or not has_s2:
            w_sr *= 0.15
            w_elo += 0.08
            if p_rank is not None:
                w_rank += 0.12

        if both_elo_default:
            w_elo *= 0.30
            if p_rank is not None:
                w_rank += 0.35

        p1_crisis = _is_form_crisis(p1)
        p2_crisis = _is_form_crisis(p2)
        if p_rank is not None and w_rank > 0 and p1_crisis != p2_crisis:
            rank_favors_p1 = p_rank > 0.5
            crisis_favored_by_rank = (p1_crisis and rank_favors_p1) or (p2_crisis and not rank_favors_p1)
            if crisis_favored_by_rank:
                w_rank *= _series_crisis_rank_multiplier(series_bucket)
            else:
                w_rank *= RANK_WEIGHT_CRISIS_OPPOSED_MULT

        total_w = w_sr + w_elo + w_rank
        sr_weight = 0.0
        elo_weight = 0.0
        rank_weight = 0.0

        if total_w <= 0:
            p1_win = 0.5
        else:
            sr_weight = w_sr / total_w
            elo_weight = w_elo / total_w
            rank_weight = w_rank / total_w
            z = sr_weight * _logit(p_serve_return) + elo_weight * _logit(p_elo)
            if p_rank is not None and rank_weight > 0:
                z += rank_weight * _logit(p_rank)
            p1_win = _sigmoid(z)

        p2_win = 1.0 - p1_win

        # Factor adjustments (small weights, capped so we don't flip favourites)
        delta_p1 = 0.0
        h2h_delta = 0.0
        adv_delta = 0.0
        results_form_delta = 0.0
        current_tournament_delta = 0.0
        tour_history_delta = 0.0
        crisis_shock_delta = 0.0
        cpi_delta = 0.0

        # H2H
        h2h_row = _get_h2h_row(p1, p2, surface)
        if h2h_row:
            h2h_n = int(h2h_row.get("match_count") or 0)
            if h2h_n >= H2H_MIN_MATCHES:
                wins_p1 = h2h_row["wins_a"] if p1 == h2h_row["player_a_id"] else h2h_row["wins_b"]
                win_rate_p1 = wins_p1 / h2h_n if h2h_n > 0 else 0.5
                h2h_delta = _clamp((win_rate_p1 - 0.5) * H2H_WEIGHT, -H2H_CAP, H2H_CAP)
                delta_p1 += structural_mult * h2h_delta

        # Advanced serve/return profile
        adv1 = _get_advanced_row(p1, surface)
        adv2 = _get_advanced_row(p2, surface)
        if adv1 and adv2:
            adv_m1 = int(adv1.get("match_count") or 0)
            adv_m2 = int(adv2.get("match_count") or 0)
            adv_min = min(adv_m1, adv_m2)
            if adv_min >= ADV_MIN_MATCHES:
                sample_scale = min(1.0, adv_min / 40.0)
                fs_pct_1 = _float(adv1.get("first_serve_pct"), 0.0) or 0.0
                fs_pct_2 = _float(adv2.get("first_serve_pct"), 0.0) or 0.0
                fsw_1 = _float(adv1.get("first_serve_win_pct"), 0.0) or 0.0
                fsw_2 = _float(adv2.get("first_serve_win_pct"), 0.0) or 0.0
                ssw_1 = _float(adv1.get("second_serve_win_pct"), 0.0) or 0.0
                ssw_2 = _float(adv2.get("second_serve_win_pct"), 0.0) or 0.0
                ace_1 = _float(adv1.get("ace_rate"), 0.0) or 0.0
                ace_2 = _float(adv2.get("ace_rate"), 0.0) or 0.0
                df_1 = _float(adv1.get("df_rate"), 0.0) or 0.0
                df_2 = _float(adv2.get("df_rate"), 0.0) or 0.0
                bp_save_1 = _float(adv1.get("bp_save_pct"), 0.5) or 0.5
                bp_save_2 = _float(adv2.get("bp_save_pct"), 0.5) or 0.5
                bp_conv_1 = _float(adv1.get("bp_convert_pct"), 0.5) or 0.5
                bp_conv_2 = _float(adv2.get("bp_convert_pct"), 0.5) or 0.5

                serve_matchup = (fsw_1 - fsw_2) * 0.45 + (ssw_1 - ssw_2) * 0.40 + (fs_pct_1 - fs_pct_2) * 0.15
                clutch_matchup = ((bp_save_1 - bp_conv_2) - (bp_save_2 - bp_conv_1)) * 0.5
                discipline_matchup = (ace_1 - df_1) - (ace_2 - df_2)

                adv_delta = sample_scale * (
                    ADV_SERVE_MATCHUP_WEIGHT * serve_matchup
                    + ADV_CLUTCH_WEIGHT * clutch_matchup
                    + ADV_DISCIPLINE_WEIGHT * discipline_matchup
                )
                adv_delta = _clamp(adv_delta, -ADV_TOTAL_CAP, ADV_TOTAL_CAP)
                delta_p1 += adv_delta

        # Vs leftie
        if p2 in leftie_ids:
            w1_vs_leftie = vs_leftie_lookup.get((p1, surface), 0.5)
            delta_p1 += structural_mult * (w1_vs_leftie - 0.5) * VS_LEFTIE_WEIGHT
        if p1 in leftie_ids:
            w2_vs_leftie = vs_leftie_lookup.get((p2, surface), 0.5)
            delta_p1 -= structural_mult * (w2_vs_leftie - 0.5) * VS_LEFTIE_WEIGHT
        # Vs big server: when opponent is big server, use win_pct_vs_big_server (continuous: weight by how much over surface avg)
        if (p2, surface) in big_server_set:
            w1_vs_bs = vs_big_server_lookup.get((p1, surface), 0.5)
            server_strength = max(0.0, (hold2 - surf_hold) / 0.13) if surf_hold < 0.75 else 1.0  # 0.75 - 0.62 ≈ 0.13 for clay
            server_strength = min(1.0, server_strength)
            d_bs = (w1_vs_bs - 0.5) * VS_BIG_SERVER_WEIGHT * server_strength
            delta_p1 += structural_mult * max(-VS_BIG_SERVER_CAP, min(VS_BIG_SERVER_CAP, d_bs))
        if (p1, surface) in big_server_set:
            w2_vs_bs = vs_big_server_lookup.get((p2, surface), 0.5)
            server_strength = max(0.0, (hold1 - surf_hold) / 0.13) if surf_hold < 0.75 else 1.0
            server_strength = min(1.0, server_strength)
            d_bs = (w2_vs_bs - 0.5) * VS_BIG_SERVER_WEIGHT * server_strength
            delta_p1 -= structural_mult * max(-VS_BIG_SERVER_CAP, min(VS_BIG_SERVER_CAP, d_bs))
        # Venue (same-event): better record at this tour gets a small boost
        if tid is not None:
            v1 = venue_lookup.get((p1, tid), 0.5)
            v2 = venue_lookup.get((p2, tid), 0.5)
            delta_p1 += structural_mult * ((v1 - 0.5) * VENUE_WEIGHT - (v2 - 0.5) * VENUE_WEIGHT)
        # Tournament CPI overlay (surface-speed): faster courts amplify server-style edge.
        if cpi_enabled and cpi_value is not None and cpi_match_weight > 0.0:
            style_edge = (hold1 - hold2) - (ret1 - ret2)
            cpi_delta = _clamp(cpi_z * style_edge * cpi_match_weight, -cpi_match_cap, cpi_match_cap)
            if abs(cpi_delta) > 1e-9:
                delta_p1 += structural_mult * cpi_delta
                cpi_delta_applied_matches += 1
        # Altitude: use player record at high-altitude venues (win_pct_at_altitude by surface); fallback to hold% proxy if no stats
        alt = tour_to_altitude.get(tid) if tid is not None else None
        if alt is not None and alt >= ALTITUDE_THRESHOLD_M:
            a1 = altitude_lookup.get((p1, surface), 0.5)
            a2 = altitude_lookup.get((p2, surface), 0.5)
            if a1 != 0.5 or a2 != 0.5:
                d_alt = (a1 - 0.5) * ALTITUDE_WEIGHT - (a2 - 0.5) * ALTITUDE_WEIGHT
            else:
                d_alt = (hold1 - hold2) * ALTITUDE_WEIGHT
            d_alt = max(-ALTITUDE_CAP, min(ALTITUDE_CAP, d_alt))
            delta_p1 += structural_mult * d_alt
        # Age: prime vs decline (scale so max effect ~ ±0.01)
        a1 = _age_factor(birthdate_by_player.get(p1))
        a2 = _age_factor(birthdate_by_player.get(p2))
        delta_p1 += 0.5 * (a1 - a2)
        # --- V2 MODEL: compound fatigue + form ---
        today_d = date.today()

        def _form_only(pid, player_elo_surface):
            act = recent_activity_by_player.get(pid)
            if not act:
                return 0.0
            m21 = int(act.get("matches_last_21d") or 0)
            wr = _float(act.get("win_rate_21d"))
            avg_opp = _float(act.get("avg_opponent_elo"), 1500)
            delta_form = 0.0
            if m21 >= FORM_MIN_MATCHES and wr is not None and avg_opp is not None:
                expected_wr = 1.0 / (1.0 + 10.0 ** ((avg_opp - player_elo_surface) / 400.0))
                delta_form = (wr - expected_wr) * FORM_WEIGHT
                delta_form = max(-FORM_CAP, min(FORM_CAP, delta_form))
            return delta_form

        def _form_fatigue_rust(pid, player_elo_surface):
            act = recent_activity_by_player.get(pid)
            if not act:
                age = _age_years(birthdate_by_player.get(pid))
                penalty = MISSING_ACTIVITY_BASE_PENALTY
                if age is not None and age >= MISSING_ACTIVITY_AGE_START:
                    penalty += (age - MISSING_ACTIVITY_AGE_START) * MISSING_ACTIVITY_AGE_WEIGHT
                if age is not None and age >= 34:
                    penalty += min(0.010, (age - 34) * 0.002)
                return -min(MISSING_ACTIVITY_PENALTY_CAP, penalty)
            m21 = int(act.get("matches_last_21d") or 0)
            wr = _float(act.get("win_rate_21d"))
            avg_opp = _float(act.get("avg_opponent_elo"), 1500)
            delta_form = 0.0
            if m21 >= FORM_MIN_MATCHES and wr is not None and avg_opp is not None:
                expected_wr = 1.0 / (1.0 + 10.0 ** ((avg_opp - player_elo_surface) / 400.0))
                delta_form = (wr - expected_wr) * FORM_WEIGHT
                delta_form = max(-FORM_CAP, min(FORM_CAP, delta_form))
            delta_fatigue = 0.0
            if act.get("played_yesterday"):
                delta_fatigue -= FATIGUE_PLAYED_YESTERDAY
            m5 = int(act.get("matches_last_5d") or 0)
            if m5 >= 3:
                delta_fatigue -= FATIGUE_DENSE_5D
            elif m5 >= 2 and act.get("played_yesterday"):
                delta_fatigue -= FATIGUE_MODERATE_COMPOUND
            delta_fatigue = max(-FATIGUE_CAP, delta_fatigue)
            delta_rust = 0.0
            last_d = act.get("last_match_date")
            if last_d:
                try:
                    if isinstance(last_d, str):
                        last_d = date.fromisoformat(last_d[:10])
                    days = (today_d - last_d).days
                    if days >= RUST_THRESHOLD_SEVERE:
                        delta_rust = -RUST_PENALTY_SEVERE
                    elif days >= RUST_THRESHOLD_MODERATE:
                        delta_rust = -RUST_PENALTY_MODERATE
                    delta_rust = max(-RUST_CAP, delta_rust)
                except (ValueError, TypeError):
                    pass
            return delta_form + delta_fatigue + delta_rust

        if v2_model is not None:
            delta_fatigue_v2 = v2_model.fatigue_delta(p1, p2, today_d, surface, tid)
            p1_form = _form_only(p1, e1_s)
            p2_form = _form_only(p2, e2_s)
            delta_p1_form = form_mult * 0.5 * (p1_form - p2_form)
            delta_p1_form = max(-FORM_TOTAL_CAP, min(FORM_TOTAL_CAP, delta_p1_form))
            delta_p1 += delta_p1_form + delta_fatigue_v2
        else:
            p1_form = _form_fatigue_rust(p1, e1_s)
            p2_form = _form_fatigue_rust(p2, e2_s)
            delta_p1_form = form_mult * 0.5 * (p1_form - p2_form)
            delta_p1_form = max(-FORM_TOTAL_CAP, min(FORM_TOTAL_CAP, delta_p1_form))
            delta_p1 += delta_p1_form
        # --- END V2 ---

        # Direct results-form layer (YTD + last5 + active streak)
        p1_results_form = _results_form_component(p1)
        p2_results_form = _results_form_component(p2)
        results_form_delta = _clamp(
            results_mult * (p1_results_form - p2_results_form),
            -RESULTS_FORM_TOTAL_CAP,
            RESULTS_FORM_TOTAL_CAP,
        )
        delta_p1 += results_form_delta

        # Current edition form: score dominance from already completed matches
        # in this exact tournament_id, capped separately from long-form history.
        p1_current_tour = _current_tournament_component(p1, tid)
        p2_current_tour = _current_tournament_component(p2, tid)
        current_tournament_delta = _clamp(
            results_mult * (p1_current_tour - p2_current_tour),
            -CURRENT_TOURNAMENT_CAP,
            CURRENT_TOURNAMENT_CAP,
        )
        delta_p1 += current_tournament_delta

        # Tournament history (same event across years)
        if tid is not None:
            t1 = _tournament_history_component(p1, tid)
            t2 = _tournament_history_component(p2, tid)
            tour_history_delta = _clamp(t1 - t2, -TOURNAMENT_HISTORY_CAP, TOURNAMENT_HISTORY_CAP)
            delta_p1 += structural_mult * tour_history_delta

        # Extra crisis shock (one-sided only): pushes severe losing-run players further out.
        if p1_crisis and not p2_crisis:
            crisis_shock_delta = -_form_crisis_shock(p1)
        elif p2_crisis and not p1_crisis:
            crisis_shock_delta = _form_crisis_shock(p2)
        delta_p1 += crisis_shock_delta

        # Cap total adjustment
        cap_components = [
            VS_LEFTIE_CAP,
            VS_BIG_SERVER_CAP,
            VENUE_CAP,
            cpi_match_cap if cpi_enabled else 0.0,
            ALTITUDE_CAP,
            AGE_CAP,
            FORM_TOTAL_CAP,
            RESULTS_FORM_TOTAL_CAP,
            CURRENT_TOURNAMENT_CAP,
            TOURNAMENT_HISTORY_CAP,
            H2H_CAP,
            ADV_TOTAL_CAP,
        ]
        component_cap = min(
            DELTA_COMPONENT_SUM_CAP_MAX,
            sum(cap_components) * DELTA_COMPONENT_SUM_CAP_FACTOR,
        )
        delta_p1 = _clamp(delta_p1, -component_cap, component_cap)

        overall_cap = DELTA_CAP_HIGH if confidence == "high" else (DELTA_CAP_MEDIUM if confidence == "medium" else DELTA_CAP_LOW)
        overall_cap *= cap_mult
        delta_p1 = _clamp(delta_p1, -overall_cap, overall_cap)
        p1_win += delta_p1
        p2_win -= delta_p1

        # Class gap: push heavy mismatches toward Elo expectation (before normalisation)
        if is_challenger:
            class_gap_kwargs = CHALLENGER_CLASS_GAP_KWARGS
        else:
            class_gap_kwargs = SERIES_CLASS_GAP_KWARGS.get(series_bucket, {})
        p1_win = apply_class_gap(
            p1_win, e1_s, e2_s, e1_o, e2_o,
            rank1_eff, rank2_eff,
            **class_gap_kwargs,
        )
        p2_win = 1.0 - p1_win

        surface_points_guard_delta = 0.0
        surface_points_guard_ratio = 0.0
        p1_win, surface_points_guard_delta, surface_points_guard_ratio = _apply_surface_points_mismatch_guard(
            p1_win,
            surface,
            series_bucket,
            confidence,
            pts1,
            pts2,
            p_rank_points,
        )
        if abs(surface_points_guard_delta) > 1e-9:
            surface_points_guarded_matches += 1
        p2_win = 1.0 - p1_win

        # Normalize
        tot = p1_win + p2_win
        if tot > 0:
            p1_win, p2_win = p1_win / tot, p2_win / tot

        p1_win_raw = p1_win
        p2_win_raw = p2_win

        # Post-hoc calibration by tour tier (trained on historical backtest).
        p1_win = _calibrate_match_probability(p1_win, series_bucket, surface, confidence)
        p1_win = _apply_series_probability_guard(
            p1_win,
            series_bucket,
            surface,
            confidence,
            is_challenger=is_challenger,
        )
        p2_win = 1.0 - p1_win

        low_conf_dog_delta = 0.0
        p1_win, low_conf_dog_delta = _apply_low_confidence_dog_guard(
            p1_win,
            p_elo,
            p_rank,
            confidence,
            has_s1,
            has_s2,
            mc1_12,
            mc2_12,
            e1_is_real,
            e2_is_real,
            e1_s,
            e2_s,
            e1_o,
            e2_o,
            r1,
            r2,
        )
        p2_win = 1.0 - p1_win

        stepup_dog_delta = 0.0
        p1_win, stepup_dog_delta = _apply_stepup_dog_guard(
            p1_win,
            p_elo,
            p_rank,
            confidence,
            current_class_score,
            p1_hist,
            p2_hist,
            r1,
            r2,
            p1_established,
            p2_established,
        )
        p2_win = 1.0 - p1_win

        injury_delta_p1 = 0.0
        if injury_downweight_enabled and injury_delta > 0.0:
            if p1_recent_injured and not p2_recent_injured:
                injury_delta_p1 = -injury_delta
            elif p2_recent_injured and not p1_recent_injured:
                injury_delta_p1 = injury_delta
            if injury_delta_p1 != 0.0:
                # Risk-control cap: do not flip the pre-adjustment favorite.
                fav_before_p1 = p1_win >= 0.5
                p1_adj = _clamp(p1_win + injury_delta_p1, 0.02, 0.98)
                if fav_before_p1:
                    p1_adj = max(0.5001, p1_adj)
                else:
                    p1_adj = min(0.4999, p1_adj)
                if abs(p1_adj - p1_win) > 1e-9:
                    injury_adjusted_matches += 1
                p1_win = p1_adj
                p2_win = 1.0 - p1_win

        odds1 = 1.0 / p1_win if p1_win > 0 else 100.0
        odds2 = 1.0 / p2_win if p2_win > 0 else 100.0

        # ─── Solve SPW from final p1_win, then compute E[G] and O/U ──────
        # avg_spw for this surface (used as centre point for the solve)
        avg_spw_surface_base = league_avg_by_surface.get(surface, 0.64)
        avg_spw_surface = avg_spw_surface_base
        venue_entry = venue_serve_lookup.get((tid, surface)) if tid is not None else None
        venue_spw = _float((venue_entry or {}).get("venue_avg_spw"))
        cpi_ratio = 1.0
        cpi_used_in_totals = False

        if cpi_enabled and cpi_value is not None and cpi_total_ratio_weight > 0.0:
            cpi_ratio = _clamp(
                1.0 + cpi_total_ratio_weight * cpi_z,
                cpi_total_ratio_min,
                cpi_total_ratio_max,
            )
            cpi_spw_center = _clamp(
                avg_spw_surface_base * cpi_ratio,
                POINT_CLAMP[0] + 0.01,
                POINT_CLAMP[1] - 0.01,
            )
            if venue_spw is not None:
                # Blend CPI with venue-SPW to avoid double counting pace information.
                avg_spw_surface = (
                    (1.0 - cpi_with_venue_blend) * venue_spw
                    + cpi_with_venue_blend * cpi_spw_center
                )
            else:
                avg_spw_surface = cpi_spw_center
            cpi_used_in_totals = True
            cpi_total_used_matches += 1
        elif venue_spw is not None:
            # Default behavior: venue-specific SPW centre when available.
            avg_spw_surface = venue_spw
        prob_match_fn = prob_match_best_of_5 if is_best_of_5 else prob_match_best_of_3
        p_a_eg, p_b_eg = _solve_spw_for_match_prob(
            p1_win, avg_spw_surface,
            clamp_lo=POINT_CLAMP[0], clamp_hi=POINT_CLAMP[1],
            prob_fn=prob_match_fn,
        )
        exp_games = expected_total_games_best_of_5(p_a_eg, p_b_eg) if is_best_of_5 else expected_total_games_best_of_3(p_a_eg, p_b_eg)

        # Tournament residual shift (e.g. court speed effects not captured by venue SPW)
        tour_shift_entry = tour_shift_lookup.get((tid, surface)) if tid is not None else None
        tour_shift = _float((tour_shift_entry or {}).get("shift_from_surface"))
        if tour_shift is not None:
            raw_add = TOURNAMENT_TOTAL_WEIGHT * tour_shift
            exp_games += max(-TOURNAMENT_TOTAL_SHIFT_CAP, min(TOURNAMENT_TOTAL_SHIFT_CAP, raw_add))
        exp_games = max(12.0, min(48.0, exp_games))

        # Market calibration for totals: our raw model tends to run high on E[G].
        # Shift line-space up when pricing P(over), equivalent to a left shift in
        # total-games distribution.
        ou_shift = OU_LINE_SHIFT_BY_SURFACE.get(surface, OU_LINE_SHIFT_BY_SURFACE["N/A"])
        if tid is not None:
            tname = (tour_name_by_id.get(tid) or "").upper()
            if "CHALLENGER" in tname:
                ou_shift += OU_CHALLENGER_EXTRA_SHIFT
            elif "ATP" in tname or "MASTERS" in tname or "GRAND SLAM" in tname:
                ou_shift += OU_ATP_MAIN_TOUR_EXTRA_SHIFT
        exp_games_cal = max(12.0, min(48.0, exp_games - ou_shift))

        # O/U: use STANDARD bookie lines (not centred on mean E[G]).
        # Find the line where P(over) crosses 50% (median), then show that line ± 1 — like Pinnacle.
        ou_data = {}
        if confidence != "none":
            line_probs = []
            for line in STANDARD_OU_LINES:
                p_over = prob_over_games(p_a_eg, p_b_eg, line + ou_shift)
                p_over = max(0.01, min(0.99, p_over))
                line_probs.append((line, p_over))
            median_idx = min(range(len(line_probs)), key=lambda i: abs(line_probs[i][1] - 0.50))
            median_idx = max(1, min(len(line_probs) - 2, median_idx))
            for idx_offset, display_idx in enumerate(range(median_idx - 1, median_idx + 2)):
                line, p_over = line_probs[display_idx]
                fair_over = round(1.0 / p_over, 3)
                fair_under = round(1.0 / (1.0 - p_over), 3)
                ou_data[f"ou_line_{idx_offset + 1}"] = round(line, 1)
                ou_data[f"ou_over_{idx_offset + 1}"] = fair_over
                ou_data[f"ou_under_{idx_offset + 1}"] = fair_under

        if do_debug:
            n1, n2 = name_by_player.get(p1, ""), name_by_player.get(p2, "")
            n1_l, n2_l = n1.lower(), n2.lower()
            if any(d in n1_l or d in n2_l for d in debug_names):
                print(f"\n  [DEBUG] {n1} (P1 id={p1}) vs {n2} (P2 id={p2}) surface={surface}")
                print(f"    Elo surface: P1={e1_s:.0f} P2={e2_s:.0f}  Overall: P1={e1_o} P2={e2_o}  real_elo: P1={e1_is_real} P2={e2_is_real}  confidence={confidence}")
                mc1 = (s1 or {}).get("match_count"); sp1 = (s1 or {}).get("service_pts"); mc2 = (s2 or {}).get("match_count"); sp2 = (s2 or {}).get("service_pts")
                print(f"    Hold/return 12m: P1 hold={hold1:.3f} ret={ret1:.3f}  P2 hold={hold2:.3f} ret={ret2:.3f}  (P1 matches={mc1} svc_pts={sp1}  P2 matches={mc2} svc_pts={sp2})")
                print(f"    Shrinkage: alpha1={alpha1:.3f} alpha2={alpha2:.3f}  mc_eff=({mc1_eff:.1f}/{mc2_eff:.1f})  class_mult=({class_sample_mult_1:.2f}/{class_sample_mult_2:.2f})  (SHRINKAGE_N={SHRINKAGE_N})")
                print(
                    f"    ATP rank: P1={atp_rank_by_player.get(p1)} P2={atp_rank_by_player.get(p2)} "
                    f"synthetic=({synthetic_r1}/{synthetic_r2}) p_rank={p_rank}  both_elo_default={both_elo_default}"
                )
                print(f"    p_elo={p_elo:.4f} p_rank={p_rank} p_serve_return={p_serve_return:.4f} weights(sr/elo/rank)=({sr_weight:.2f}/{elo_weight:.2f}/{rank_weight:.2f}) -> p1_win={p1_win:.4f} (after adj+cal), series={series_bucket}, challenger={is_challenger}")
                print(f"    Class jump: current={current_class_score:.1f} recent_avg=({p1_hist.get('recent_class_avg')}/{p2_hist.get('recent_class_avg')})  elo_penalty=({class_penalty_elo_1:.1f}/{class_penalty_elo_2:.1f})")
                print(f"    Effective SPW inputs: P1 serve={hold1_eff:.3f} ret={ret1_eff:.3f} | P2 serve={hold2_eff:.3f} ret={ret2_eff:.3f} | shifts hold={hold_shift:+.3f} ret={ret_shift:+.3f}")
                print(
                    f"    Tournament speed: signal={tour_speed_signal:+.3f} mult={tour_speed_multiplier:+.3f} "
                    f"venue_spw={tour_speed_debug.get('venue_spw')} n={tour_speed_debug.get('venue_spw_matches')} "
                    f"ratio={tour_speed_debug.get('venue_ratio')} shift={tour_speed_debug.get('tour_shift')} "
                    f"shift_n={tour_speed_debug.get('tour_shift_matches')}"
                )
                if abs(tour_speed_multiplier) > 1e-9:
                    print(
                        f"    Venue-adjusted SPW: P1 serve={hold1_model:.3f} ret={ret1_model:.3f} | "
                        f"P2 serve={hold2_model:.3f} ret={ret2_model:.3f}"
                    )
                print(
                    f"    Injury: p1={p1_recent_injured}({p1_injury_mode}) "
                    f"p2={p2_recent_injured}({p2_injury_mode}) "
                    f"enabled={injury_downweight_enabled} delta={injury_delta_p1:+.4f}"
                )
                print(
                    f"    CPI: enabled={cpi_enabled} value={cpi_value} year={cpi_year} mode={cpi_mode} "
                    f"z={cpi_z:+.3f} delta={cpi_delta:+.4f} ratio={cpi_ratio:.3f} totals_used={cpi_used_in_totals}"
                )
                print(
                    f"    H2H={h2h_delta:+.4f} ADV={adv_delta:+.4f} "
                    f"form_base={delta_p1_form:+.4f} results_form={results_form_delta:+.4f} "
                    f"current_tour={current_tournament_delta:+.4f} "
                    f"tour_hist={tour_history_delta:+.4f} crisis_shock={crisis_shock_delta:+.4f} "
                    f"total_delta={delta_p1:+.4f} elo_mag_release={elo_magnitude_release:+.4f} "
                    f"rank_conflict_release={surface_rank_conflict_release:+.4f} "
                    f"surface_points_guard={surface_points_guard_delta:+.4f} (ratio={surface_points_guard_ratio:.1f}) "
                    f"low_conf_guard={low_conf_dog_delta:+.4f} "
                    f"stepup_guard={stepup_dog_delta:+.4f} "
                    f"crisis(P1/P2)={p1_crisis}/{p2_crisis}"
                )
                o1 = 1.0 / p1_win if p1_win > 0 else 0
                o2 = 1.0 / p2_win if p2_win > 0 else 0
                print(f"    Our fair odds: P1={o1:.2f} P2={o2:.2f}  (if P1 favoured, P1 odds should be lower e.g. ~1.2)")
                print(f"    Expected total games: raw={exp_games:.1f} calibrated={exp_games_cal:.1f} (ou_shift={ou_shift:+.2f})")
                print(f"    p_a_eg={p_a_eg:.4f} p_b_eg={p_b_eg:.4f}  (solved from p1_win={p1_win:.4f}, avg_spw={avg_spw_surface:.3f})")
                if (mc1 is not None and int(mc1 or 0) < 10) or (mc2 is not None and int(mc2 or 0) < 10):
                    print(f"    ^ Low match_count -> hold/return may be noisy. Re-run oncourt-compute-player-stats after fresh extract, or add prior when sample small.")

        p1_activity = recent_activity_by_player.get(p1) or {}
        p2_activity = recent_activity_by_player.get(p2) or {}

        # Store the same point-probability shape used to price totals/spreads.
        # The raw matchup p_a/p_b still feeds p_serve_return as one ML blend
        # component, but the published ML fair can move after Elo/rank/form/
        # calibration overlays. Persisting the raw pair made the handicap layer
        # reject many rows as "divergent" from the final fair.
        out.append({
            "tour_id": tour_id,
            "player1_id": p1,
            "player2_id": p2,
            "surface": surface,
            "round_id": round_id,
            "draw": draw,
            "p1_win_prob_raw": round(p1_win_raw, 4),
            "p2_win_prob_raw": round(p2_win_raw, 4),
            "p1_win_prob": round(p1_win, 4),
            "p2_win_prob": round(p2_win, 4),
            "p_a": round(p_a_eg, 4),
            "p_b": round(p_b_eg, 4),
            "p_serve_return": round(p_serve_return, 4),
            "p_elo": round(p_elo, 4),
            "odds1": round(odds1, 2),
            "odds2": round(odds2, 2),
            "expected_total_games": round(exp_games_cal, 1),
            "confidence": confidence,
            "match_count_12m_p1": mc1_12,
            "match_count_12m_p2": mc2_12,
            "matches_total_p1": int((p1_hist or {}).get("matches_total") or 0),
            "matches_total_p2": int((p2_hist or {}).get("matches_total") or 0),
            "recent_challenger_plus_p1": int((p1_hist or {}).get("recent_challenger_plus_matches") or 0),
            "recent_challenger_plus_p2": int((p2_hist or {}).get("recent_challenger_plus_matches") or 0),
            "last_match_days_p1": _days_since(p1_activity.get("last_match_date"), today_d),
            "last_match_days_p2": _days_since(p2_activity.get("last_match_date"), today_d),
            "data_coverage_tag": _data_coverage_tag(mc1_12, mc2_12, p1_hist, p2_hist, p1_activity, p2_activity, today_d),
            **ou_data,
        })

    print(f"Computed {len(out)} fair odds rows")
    if v2_model is not None:
        v2_model.print_summary()
    print(f"  Fixture surfaces (from tour_id): {dict(surface_counts)}")
    print(f"  Skipped: no player1/player2 = {skip_no_players}, same-player = {skip_same_player}, unknown = {skip_unknown}, doubles/team (name contains / or &) = {skip_doubles}")
    print(f"  Elo/rank fallback (missing stats): both = {skip_missing_both}, P1 only = {skip_missing_p1}, P2 only = {skip_missing_p2}")
    print(f"  Surface-points mismatch guard: adjusted_matches={surface_points_guarded_matches}")
    conf_counts = {"high": 0, "medium": 0, "low": 0, "none": 0}
    for row in out:
        c = row.get("confidence", "high")
        conf_counts[c] = conf_counts.get(c, 0) + 1
    print(f"  Confidence: high={conf_counts['high']}, medium={conf_counts['medium']}, low={conf_counts['low']}, none={conf_counts['none']}")
    print(
        "  Injury flags: "
        f"P1={injury_flagged_p1}, P2={injury_flagged_p2}, "
        f"adjusted_matches={injury_adjusted_matches} "
        f"(downweight={'on' if injury_downweight_enabled else 'off'})"
    )
    if cpi_enabled:
        print(
            "  CPI overlay: "
            f"rows={cpi_rows_loaded:,}, resolved_matches={cpi_resolved_matches}, "
            f"delta_applied={cpi_delta_applied_matches}, totals_used={cpi_total_used_matches}"
        )
    print(
        "  Tournament speed overlay: "
        f"weight={tournament_speed_point_weight:.3f}, "
        f"resolved_matches={tournament_speed_resolved_matches}, "
        f"adjusted_matches={tournament_speed_adjusted_matches}"
    )
    if out:
        for row in out[:3]:
            print(f"  P1={row['player1_id']} P2={row['player2_id']} surface={row['surface']} P1={row['p1_win_prob']} odds1={row['odds1']} odds2={row['odds2']}")

    if do_dry_run:
        print("\nDry run done. Run without --dry-run to upsert to daily_fair_odds.")
        return

    out = _filter_rows_with_known_players(out)
    _sync_daily_fair_odds(out)
    if do_skip_handicap_values:
        print("Skipped handicap-value refresh (--skip-handicap-values).")
        print("Done.")
        return

    print("  Refreshing handicap values...")
    handicap_result = subprocess.run(
        [sys.executable, os.path.join(_script_dir, "compute-handicap-values.py")],
        cwd=os.path.join(_script_dir, ".."),
    )
    if handicap_result.returncode != 0:
        print(f"ERROR: compute-handicap-values failed (exit {handicap_result.returncode}).")
        sys.exit(handicap_result.returncode)
    print("Done.")


if __name__ == "__main__":
    if "--test-solver" in sys.argv:
        # Quick local check: 85% favourite -> E[G] ~22.5 (no Supabase needed)
        p_a, p_b = _solve_spw_for_match_prob(0.85, 0.64, clamp_lo=POINT_CLAMP[0], clamp_hi=POINT_CLAMP[1])
        eg = expected_total_games_best_of_3(p_a, p_b)
        print(f"[--test-solver] p1_win=0.85 avg_spw=0.64 -> p_a={p_a:.3f} p_b={p_b:.3f} E[G]={eg:.1f} (expect ~22.5)")
        sys.exit(0)
    main()
