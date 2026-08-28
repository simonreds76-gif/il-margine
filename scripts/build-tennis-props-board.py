#!/usr/bin/env python3
"""Build an internal ATP/WTA aces and double-fault projection board."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from tennis_props_names import (
    baseline_names_by_tour,
    norm_name as normalize_player_name,
    resolve_baseline_name,
)
from tennis_props_model import (
    count_line_probabilities,
    project_player,
    push_adjusted_fair_odds,
    resolve_break_distribution,
)


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ONCOURT_DIR = DATA_DIR / "oncourt"
SACKMANN_DIR = DATA_DIR / "sackmann"
PROPS_DIR = DATA_DIR / "tennis-props"
INBOX_DIR = PROPS_DIR / "inbox"
DEFAULT_BASELINE = PROPS_DIR / "player-props-baseline.csv"
DEFAULT_ACTIVITY = PROPS_DIR / "player-props-activity.csv"
DEFAULT_FACTORS = PROPS_DIR / "slam-venue-factors.csv"
DEFAULT_SURFACE_BASELINES = PROPS_DIR / "tour-surface-baselines.csv"
DEFAULT_ALIASES = PROPS_DIR / "player-name-aliases.csv"
DEFAULT_OUT = PROPS_DIR / "player-props-board.csv"
DEFAULT_FAIR_ODDS_TOTALS_SOURCE = "auto"
SURFACE_BY_COURT = {
    "1": "Hard",
    "2": "Clay",
    "3": "Grass",
    "4": "Hard",
    "5": "Grass",
}
ROUND_BY_ID = {
    "4": "R128",
    "5": "R64",
    "6": "R32",
    "7": "R16",
    "9": "QF",
    "10": "SF",
    "12": "F",
}
SLAM_QUALIFYING_ROUND_BY_ID = {
    "1": "Q1",
    "2": "Q2",
    "3": "Q3",
}
SLAM_TOURNAMENTS = {"Australian Open", "Roland Garros", "Wimbledon", "US Open"}
MAIN_TOUR_RANKS = {2, 3, 4}
EXCLUDED_TOUR_NAME_FRAGMENTS = (
    "junior",
    "juniors",
    "challenger",
    "itf",
    " m15",
    " m25",
    " w15",
    " w25",
    "qualifying",
    "qualification",
    "wild card",
    "wildcard",
    "play-off",
    "playoff",
)
VENUE_FACTOR_MIN = 0.85
VENUE_FACTOR_MAX = 1.20
CURRENT_ENV_ACE_DF_MIN = 0.94
CURRENT_ENV_ACE_DF_MAX = 1.06
CURRENT_ENV_BREAK_MIN = 0.92
CURRENT_ENV_BREAK_MAX = 1.08
CURRENT_ENV_TIEBREAK_MIN = 0.90
CURRENT_ENV_TIEBREAK_MAX = 1.12
CURRENT_ENV_MAX_WEIGHT = 0.10
CURRENT_ENV_FULL_MATCHES = 20.0
_CURRENT_EVENT_ROWS_CACHE: dict[
    tuple[str, tuple[str, ...]],
    tuple[list[dict[str, str]], list[dict[str, str]]],
] = {}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _read_current_event_rows(path: Path, tour_ids: set[str]) -> list[dict[str, str]]:
    """Read only rows belonging to scheduled events from a large OnCourt export."""
    if not path.exists() or not tour_ids:
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [
            row
            for row in csv.DictReader(f)
            if str(row.get("tour_id") or "").strip() in tour_ids
        ]


def load_current_event_rows(
    tour_lower: str,
    tour_ids: set[str],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Load current-event stat/game rows once per tour for all board features."""
    cache_key = (tour_lower, tuple(sorted(tour_ids)))
    cached = _CURRENT_EVENT_ROWS_CACHE.get(cache_key)
    if cached is not None:
        return cached

    rows = (
        _read_current_event_rows(ONCOURT_DIR / f"stat_{tour_lower}.csv", tour_ids),
        _read_current_event_rows(ONCOURT_DIR / f"games_{tour_lower}.csv", tour_ids),
    )
    _CURRENT_EVENT_ROWS_CACHE[cache_key] = rows
    return rows


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_env() -> None:
    for name in (".env.local", "env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            raw_line = raw_line.strip()
            if raw_line and not raw_line.startswith("#") and "=" in raw_line:
                key, value = raw_line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def norm_name(value: object) -> str:
    return normalize_player_name(value)


def parse_float(value: object, default: float | None = None) -> float | None:
    try:
        text = str(value or "").strip()
        if not text:
            return default
        return float(text)
    except (TypeError, ValueError):
        return default


def parse_int(value: object, default: int = 0) -> int:
    try:
        text = str(value or "").strip()
        if not text:
            return default
        return int(float(text))
    except (TypeError, ValueError):
        return default


def oncourt_service_points(stat: dict[str, str], prefix: str) -> int:
    """Return the clean OnCourt service-point denominator for one side.

    In the MDB export, FSOF is the service-point denominator. Some generated
    stat CSVs also include *_svpt, but older exports inflated it as
    FSOF + W2SOF, which double-counts second-serve points. Props use FSOF.
    """
    return parse_int(stat.get(f"{prefix}_fsof")) or parse_int(stat.get(f"{prefix}_svpt"))


def parse_score_total_games(value: object) -> int:
    """Return completed games from score strings like '6-4 3-6 7-6(4)'."""
    text = str(value or "")
    total = 0
    for left, right in re.findall(r"(\d+)\s*-\s*(\d+)", text):
        total += int(left) + int(right)
    return total


def parse_score_tiebreaks(value: object) -> tuple[int, int, int]:
    text = str(value or "")
    sets = re.findall(r"(\d+)\s*-\s*(\d+)(?:\s*\([^)]*\))?", text)
    if not sets:
        return 0, 0, 0
    flags = [1 if {int(left), int(right)} == {6, 7} else 0 for left, right in sets]
    return len(sets), flags[0] if flags else 0, 1 if any(flags) else 0


def add_stat_totals(
    target: dict[str, int],
    *,
    aces: object,
    dfs: object,
    svpt: object,
    breaks_for: object = 0,
    broken: object = 0,
) -> None:
    target["matches"] = target.get("matches", 0) + 1
    target["aces"] = target.get("aces", 0) + parse_int(aces)
    target["dfs"] = target.get("dfs", 0) + parse_int(dfs)
    target["svpt"] = target.get("svpt", 0) + parse_int(svpt)
    target["breaks_for"] = target.get("breaks_for", 0) + parse_int(breaks_for)
    target["broken"] = target.get("broken", 0) + parse_int(broken)


def fmt(value: float | None, digits: int = 3) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def fmt_rate_pct(value: object, digits: int = 1) -> str:
    parsed = parse_float(value)
    if parsed is None:
        return ""
    return fmt(parsed * 100.0, digits)


def append_note(value: str, note: str) -> str:
    notes = [part for part in str(value or "").split("|") if part]
    if note not in notes:
        notes.append(note)
    return "|".join(notes)


def break_fair_odds_ladder(mean: float | None, tour: str, scope: str) -> tuple[str, str, str]:
    if mean is None or mean <= 0:
        return "", "poisson", "OUTCOME_GATE_MISSING"
    distribution, alpha, passed = resolve_break_distribution(tour, scope)
    centre = math.floor(mean) + 0.5
    lines = sorted({max(0.5, centre - 1.0), max(0.5, centre), centre + 1.0})
    ladder: list[dict[str, object]] = []
    for line in lines:
        p_over, p_under, p_push = count_line_probabilities(
            line,
            mean,
            distribution=distribution,
            alpha=alpha,
            tour=tour,
            market=scope,
        )
        ladder.append(
            {
                "line": line,
                "over_pct": round(p_over * 100.0, 1),
                "under_pct": round(p_under * 100.0, 1),
                "fair_over": round(push_adjusted_fair_odds(p_over, p_push) or 0.0, 2),
                "fair_under": round(push_adjusted_fair_odds(p_under, p_push) or 0.0, 2),
            }
        )
    status = "OUTCOME_PASS_PRICE_FEED_MISSING" if passed else "OUTCOME_GATE_MISSING"
    return json.dumps(ladder, separators=(",", ":")), distribution, status


def normalize_match_break_totals(row_a: dict[str, str], row_b: dict[str, str]) -> None:
    """Break totals are match-level: A breaks + B breaks, identical on both rows."""
    a_breaks = parse_float(row_a.get("projected_breaks_for"))
    b_breaks = parse_float(row_b.get("projected_breaks_for"))
    if a_breaks is None or b_breaks is None:
        return
    total_breaks = a_breaks + b_breaks
    row_a["projected_broken"] = fmt(b_breaks)
    row_b["projected_broken"] = fmt(a_breaks)
    row_a["projected_total_breaks"] = fmt(total_breaks)
    row_b["projected_total_breaks"] = fmt(total_breaks)
    ladder, distribution, status = break_fair_odds_ladder(
        total_breaks,
        str(row_a.get("tour") or ""),
        "match_breaks",
    )
    for row in (row_a, row_b):
        row["match_break_fair_odds_json"] = ladder
        row["match_break_distribution"] = distribution
        row["match_break_model_status"] = status
    row_a["break_notes"] = append_note(row_a.get("break_notes", ""), "MATCH_LEVEL_TOTAL")
    row_b["break_notes"] = append_note(row_b.get("break_notes", ""), "MATCH_LEVEL_TOTAL")


def slam_name(value: object) -> str | None:
    lower = str(value or "").lower()
    if "roland garros" in lower or "french open" in lower:
        return "Roland Garros"
    if "wimbledon" in lower:
        return "Wimbledon"
    if "australian open" in lower:
        return "Australian Open"
    if "us open" in lower or "u.s. open" in lower:
        return "US Open"
    return None


def canonical_tournament_name(value: object) -> str | None:
    """Canonical tournament names for the tour-level events this board supports."""
    raw = str(value or "")
    lower = raw.lower()
    slam = slam_name(raw)
    if slam:
        return slam
    if "hertogenbosch" in lower or "rosmalen" in lower or "libema open" in lower:
        return "Hertogenbosch"
    if (
        "queen" in lower
        or "hsbc championships" in lower
        or "lta london championships" in lower
        or "cinch championships" in lower
        or "stella artois" in lower
    ):
        return "Queen's Club"
    if "stuttgart" in lower or "boss open" in lower:
        return "Stuttgart"
    if "halle" in lower or "terra wortmann" in lower or "gerry weber" in lower:
        return "Halle"
    if "nottingham" in lower:
        return "Nottingham"
    if "berlin" in lower and ("open" in lower or "tennis" in lower or "bett1" in lower):
        return "Berlin"
    if "eastbourne" in lower:
        return "Eastbourne"
    if "bad homburg" in lower:
        return "Bad Homburg"
    if "bastad" in lower or "nordea open" in lower:
        return "Bastad"
    if "gstaad" in lower or "swiss open" in lower:
        return "Gstaad"
    if "umag" in lower or "croatia open" in lower:
        return "Umag"
    if "estoril" in lower:
        return "Estoril"
    if "kitzbuhel" in lower or "kitzbühel" in lower:
        return "Kitzbuhel"
    if "iasi" in lower:
        return "Iasi"
    if "athens" in lower:
        return "Athens"
    return None


def scheduled_tournament_name(value: object) -> str | None:
    """Return a stable name for a supported main-tour schedule event.

    Known aliases keep their historical names. Unknown ATP/WTA main-tour
    events fall back to OnCourt's location suffix instead of disappearing
    from the board until an alias is added manually.
    """
    canonical = canonical_tournament_name(value)
    if canonical:
        return canonical
    raw = re.sub(r"\s+", " ", str(value or "")).strip()
    if not raw:
        return None
    parts = re.split(r"\s+-\s+", raw)
    fallback = parts[-1].strip(" -") if len(parts) > 1 else raw
    return fallback or None


def is_supported_main_tour(tour: dict[str, str]) -> bool:
    rank = parse_int(tour.get("rank"))
    if rank not in MAIN_TOUR_RANKS:
        return False
    name = f" {str(tour.get('name') or '').lower()} "
    return not any(fragment in name for fragment in EXCLUDED_TOUR_NAME_FRAGMENTS)


def round_label(round_id: object, tournament: str) -> str:
    rid = str(round_id or "").strip()
    if tournament not in SLAM_TOURNAMENTS:
        return {
            "4": "R32",
            "5": "R16",
            "9": "QF",
            "10": "SF",
            "12": "F",
        }.get(rid, rid)
    return SLAM_QUALIFYING_ROUND_BY_ID.get(rid, ROUND_BY_ID.get(rid, rid))


def is_placeholder_player(value: object) -> bool:
    name = norm_name(value)
    return name in {"unknown player", "bye"} or not name


def is_slam_qualifying_round(tournament: str, round_id: object) -> bool:
    round_number = parse_int(round_id)
    return tournament in SLAM_TOURNAMENTS and 0 < round_number < 4


def is_best_of_five(tour: str, tournament: str, round_id: object = None) -> bool:
    return (
        tour.upper() == "ATP"
        and tournament in SLAM_TOURNAMENTS
        and not is_slam_qualifying_round(tournament, round_id)
    )


def slam_main_draw_active_events(schedules: list[dict[str, str]]) -> set[tuple[str, str]]:
    """Events where the current board is main-draw Slam, not qualifying."""
    active: set[tuple[str, str]] = set()
    for row in schedules:
        tour = str(row.get("tour") or "").upper()
        tour_id = str(row.get("tour_id") or "").strip()
        tournament = str(row.get("tournament") or "").strip()
        round_id = parse_int(row.get("round_id_raw"))
        if tour in {"ATP", "WTA"} and tour_id and tournament in SLAM_TOURNAMENTS and round_id >= 4:
            active.add((tour, tour_id))
    return active


def skip_slam_qualifying_for_main_draw(main_draw_events: set[tuple[str, str]], tour: str, tour_id: str, round_id: object) -> bool:
    return (tour, tour_id) in main_draw_events and parse_int(round_id) < 4


def default_match_games(tour: str, tournament: str, round_id: object = None) -> float:
    if is_best_of_five(tour, tournament, round_id):
        return 35.0
    return 23.5 if tour.upper() == "ATP" else 21.5


def load_baseline(path: Path) -> dict[tuple[str, str, str], dict[str, dict[str, str]]]:
    out: dict[tuple[str, str, str], dict[str, dict[str, str]]] = defaultdict(dict)
    for row in read_csv(path):
        full_name_norm = norm_name(row.get("player_name"))
        key = (
            str(row.get("tour") or "").upper(),
            full_name_norm,
            str(row.get("surface") or "").strip(),
        )
        out[key][str(row.get("window") or "")] = row
    return out


def load_activity(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    out: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in read_csv(path):
        key = (
            str(row.get("tour") or "").upper(),
            norm_name(row.get("player_name")),
            str(row.get("window") or ""),
        )
        out[key] = row
    return out


def load_factors(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    factors: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in read_csv(path):
        if str(row.get("year") or "") != "ALL":
            continue
        key = (
            str(row.get("tour") or "").upper(),
            str(row.get("tournament") or "").strip(),
            str(row.get("surface") or "").strip(),
        )
        factors[key] = row
    return factors


def load_surface_baselines(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    baselines: dict[tuple[str, str], dict[str, str]] = {}
    for row in read_csv(path):
        if str(row.get("year") or "") != "ALL":
            continue
        key = (
            str(row.get("tour") or "").upper(),
            str(row.get("surface") or "").strip(),
        )
        baselines[key] = row
    return baselines


def surface_baseline_factor(
    *,
    tour: str,
    tournament: str,
    surface: str,
    surface_baselines: dict[tuple[str, str], dict[str, str]],
) -> dict[str, str]:
    row = surface_baselines.get((tour, surface)) or {}
    if not row:
        return {}
    return {
        "tour": tour,
        "tournament": tournament,
        "surface": surface,
        "year": "ALL",
        "matches": str(row.get("matches") or ""),
        "ace_rate": str(row.get("ace_rate") or ""),
        "df_rate": str(row.get("df_rate") or ""),
        "tiebreak_set_rate": str(row.get("tiebreak_set_rate") or ""),
        "first_set_tiebreak_rate": str(row.get("first_set_tiebreak_rate") or ""),
        "match_tiebreak_rate": str(row.get("match_tiebreak_rate") or ""),
        "svpt_per_svgame": str(row.get("svpt_per_svgame") or ""),
        "match_games_per_match": str(row.get("match_games_per_match") or ""),
        "tour_surface_baseline_ace": str(row.get("ace_rate") or ""),
        "tour_surface_baseline_df": str(row.get("df_rate") or ""),
        "tour_surface_baseline_tiebreak_set": str(row.get("tiebreak_set_rate") or ""),
        "tour_surface_baseline_first_set_tiebreak": str(row.get("first_set_tiebreak_rate") or ""),
        "tour_surface_baseline_match_tiebreak": str(row.get("match_tiebreak_rate") or ""),
        "ace_factor": "1.0000",
        "df_factor": "1.0000",
        "first_set_tiebreak_factor": "1.0000",
        "match_tiebreak_factor": "1.0000",
        "sample_flag": "SURFACE_BASELINE",
    }


def clipped_venue_factor_row(row: dict[str, str]) -> tuple[dict[str, str], bool]:
    """Cap venue multipliers so small warmup fields cannot dominate projections."""
    out = dict(row)
    clipped = False
    for field in ("ace_factor", "df_factor", "first_set_tiebreak_factor", "match_tiebreak_factor"):
        value = parse_float(out.get(field))
        if value is None:
            continue
        capped = max(VENUE_FACTOR_MIN, min(VENUE_FACTOR_MAX, value))
        if abs(capped - value) > 1e-9:
            out[field] = f"{capped:.4f}"
            clipped = True
    return out, clipped


def _clipped_ratio_factor(
    *,
    current_rate: float,
    baseline_rate: float | None,
    weight: float,
    low: float,
    high: float,
) -> float:
    if not baseline_rate or baseline_rate <= 0 or current_rate <= 0 or weight <= 0:
        return 1.0
    # Use a log-scale nudge so early event samples cannot force the whole board
    # into identical cap values. Venue history and player/opponent rates remain
    # the primary signal; same-edition stats are a small environment correction.
    raw_ratio = max(0.25, min(4.0, current_rate / baseline_rate))
    adjusted = math.exp(math.log(raw_ratio) * weight)
    return max(low, min(high, adjusted))


def current_env_weight(matches: int) -> float:
    if matches < 2:
        return 0.0
    return max(0.0, min(CURRENT_ENV_MAX_WEIGHT, matches / CURRENT_ENV_FULL_MATCHES * CURRENT_ENV_MAX_WEIGHT))


def load_aliases(path: Path) -> dict[tuple[str, str], str]:
    aliases: dict[tuple[str, str], str] = {}
    for row in read_csv(path):
        tour = str(row.get("tour") or "").upper()
        alias = norm_name(row.get("alias"))
        player_name = norm_name(row.get("player_name"))
        if tour and alias and player_name:
            aliases[(tour, alias)] = player_name
    return aliases


def load_oncourt_player_names(tour: str) -> dict[str, str]:
    names = {}
    for row in read_csv(ONCOURT_DIR / f"players_{tour.lower()}.csv"):
        pid = str(row.get("id") or "").strip()
        name = str(row.get("name") or "").strip()
        if pid and name:
            names[pid] = name
    return names


def load_oncourt_tours(tour: str) -> dict[str, dict[str, str]]:
    tours = {}
    for row in read_csv(ONCOURT_DIR / f"tours_{tour.lower()}.csv"):
        tid = str(row.get("id") or "").strip()
        if tid:
            tours[tid] = row
    return tours


def parse_date(value: object) -> date | None:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{8}", text):
        try:
            return datetime.strptime(text, "%Y%m%d").date()
        except ValueError:
            return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def load_tournament_samples(as_of: date) -> dict[tuple[str, str, str], int]:
    samples: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for tour in ("atp", "wta"):
        for path in sorted(SACKMANN_DIR.glob(f"{tour}_matches_*.csv")):
            if "qual_chall" in path.name:
                continue
            for row in read_csv(path):
                match_date = parse_date(row.get("tourney_date"))
                tournament = canonical_tournament_name(row.get("tourney_name"))
                if match_date is None or match_date >= as_of or not tournament:
                    continue
                winner_norm = norm_name(row.get("winner_name"))
                loser_norm = norm_name(row.get("loser_name"))
                key_w = (tour.upper(), winner_norm, tournament)
                key_l = (tour.upper(), loser_norm, tournament)
                match_id = "|".join(
                    [
                        str(row.get("tourney_id") or ""),
                        str(row.get("match_num") or ""),
                        str(row.get("winner_id") or ""),
                        str(row.get("loser_id") or ""),
                    ]
                )
                samples[key_w].add(match_id)
                samples[key_l].add(match_id)
    return {key: len(value) for key, value in samples.items()}


def oncourt_schedule_rows(
    tour_code: str,
    include_completed: bool,
    board_date: str,
    days_ahead: int = 1,
) -> list[dict[str, str]]:
    tour_lower = tour_code.lower()
    player_names = load_oncourt_player_names(tour_lower)
    tours = load_oncourt_tours(tour_lower)
    board_dt = parse_date(board_date) or date.today()
    horizon_dt = board_dt + timedelta(days=max(0, days_ahead))
    rows: list[dict[str, str]] = []
    for row in read_csv(ONCOURT_DIR / f"today_{tour_lower}.csv"):
        if not include_completed and str(row.get("result") or "").strip():
            continue
        tour = tours.get(str(row.get("tour_id") or "").strip()) or {}
        if not is_supported_main_tour(tour):
            continue
        row_date = parse_date(row.get("date"))
        if row_date:
            if row_date < board_dt or row_date > horizon_dt:
                continue
        tournament = scheduled_tournament_name(tour.get("name"))
        if not tournament:
            continue
        tour_start = parse_date(tour.get("date"))
        if (
            not row_date
            and tour_start
            and tour_start > horizon_dt
            and not is_slam_qualifying_round(tournament, row.get("round_id"))
        ):
            continue
        p1 = player_names.get(str(row.get("player1_id") or "").strip(), "")
        p2 = player_names.get(str(row.get("player2_id") or "").strip(), "")
        if not p1 or not p2:
            continue
        if is_placeholder_player(p1) or is_placeholder_player(p2):
            continue
        if "/" in p1 or "/" in p2:
            continue
        # OnCourt leaves upcoming match dates blank. The tournament start date
        # is not the match date and caused current lines to miss the daily board.
        confirmed_date = str(row.get("date") or "").strip()
        schedule_date = confirmed_date or board_date
        rows.append(
            {
                "date": schedule_date,
                "generation_date": board_date,
                "scheduled_date": confirmed_date,
                "scheduled_start_utc": "",
                "schedule_status": "confirmed" if confirmed_date else "tbd",
                "schedule_source": "oncourt_today" if confirmed_date else "oncourt_draw_undated",
                "tour": tour_code.upper(),
                "tour_id": str(row.get("tour_id") or "").strip(),
                "tournament": tournament,
                "round": round_label(row.get("round_id"), tournament),
                "round_id_raw": str(row.get("round_id") or "").strip(),
                "surface": SURFACE_BY_COURT.get(str(tour.get("court_id") or ""), "Clay"),
                "player1": p1,
                "player2": p2,
                "player1_id": str(row.get("player1_id") or "").strip(),
                "player2_id": str(row.get("player2_id") or "").strip(),
                "source": f"oncourt_today_{tour_lower}",
            }
        )
    return rows


def wta_schedule_rows(path: Path) -> list[dict[str, str]]:
    rows = []
    for row in read_csv(path):
        p1 = str(row.get("player1") or "").strip()
        p2 = str(row.get("player2") or "").strip()
        if not p1 or not p2:
            continue
        tournament = canonical_tournament_name(row.get("tournament")) or str(row.get("tournament") or "").strip()
        if not tournament:
            continue
        scheduled_date = str(row.get("date") or "").strip()
        rows.append(
            {
                "date": scheduled_date,
                "generation_date": scheduled_date,
                "scheduled_date": scheduled_date,
                "scheduled_start_utc": str(row.get("match_start_utc") or "").strip(),
                "schedule_status": "confirmed" if scheduled_date else "tbd",
                "schedule_source": str(path),
                "tour": "WTA",
                "tour_id": str(row.get("tour_id") or "").strip(),
                "tournament": tournament,
                "round": str(row.get("round") or "").strip(),
                "round_id_raw": str(row.get("round_id") or "").strip(),
                "surface": str(row.get("surface") or "Clay").strip() or "Clay",
                "player1": p1,
                "player2": p2,
                "player1_id": str(row.get("player1_id") or "").strip(),
                "player2_id": str(row.get("player2_id") or "").strip(),
                "source": str(path),
            }
        )
    return rows


def load_current_tournament_stats(schedules: list[dict[str, str]], as_of: date) -> dict[tuple[str, str, str], dict[str, str]]:
    """Same-edition aces/DFs from OnCourt completed matches."""
    tour_ids_by_tour: dict[str, set[str]] = defaultdict(set)
    main_draw_events = slam_main_draw_active_events(schedules)
    for row in schedules:
        tour = str(row.get("tour") or "").upper()
        tour_id = str(row.get("tour_id") or "").strip()
        if tour in {"ATP", "WTA"} and tour_id:
            tour_ids_by_tour[tour].add(tour_id)
    if not tour_ids_by_tour:
        return {}

    totals: dict[tuple[str, str, str], dict[str, int]] = defaultdict(dict)
    for tour, tour_ids in tour_ids_by_tour.items():
        tour_lower = tour.lower()
        stat_rows, game_rows = load_current_event_rows(tour_lower, tour_ids)
        stat_index: dict[tuple[str, str, str, str], dict[str, str]] = {}
        for row in stat_rows:
            tour_id = str(row.get("tour_id") or "").strip()
            key = (
                str(row.get("winner_id") or "").strip(),
                str(row.get("loser_id") or "").strip(),
                tour_id,
                str(row.get("round_id") or "").strip(),
            )
            stat_index.setdefault(key, row)

        for game in game_rows:
            tour_id = str(game.get("tour_id") or "").strip()
            match_date = parse_date(game.get("date"))
            if match_date is None or match_date >= as_of:
                continue
            winner_id = str(game.get("winner_id") or "").strip()
            loser_id = str(game.get("loser_id") or "").strip()
            round_id = str(game.get("round_id") or "").strip()
            if skip_slam_qualifying_for_main_draw(main_draw_events, tour, tour_id, round_id):
                continue
            if not winner_id or not loser_id or winner_id == loser_id:
                continue
            stat = stat_index.get((winner_id, loser_id, tour_id, round_id))
            if not stat:
                continue
            add_stat_totals(
                totals[(tour, tour_id, winner_id)],
                aces=stat.get("w_ace"),
                dfs=stat.get("w_df"),
                svpt=oncourt_service_points(stat, "w"),
                breaks_for=stat.get("w_bpw"),
                broken=max(0, parse_int(stat.get("w_bpfaced")) - parse_int(stat.get("w_bpsaved"))),
            )
            add_stat_totals(
                totals[(tour, tour_id, loser_id)],
                aces=stat.get("l_ace"),
                dfs=stat.get("l_df"),
                svpt=oncourt_service_points(stat, "l"),
                breaks_for=stat.get("l_bpw"),
                broken=max(0, parse_int(stat.get("l_bpfaced")) - parse_int(stat.get("l_bpsaved"))),
            )

    return {
        key: {field: str(value) for field, value in values.items()}
        for key, values in totals.items()
    }


def load_current_tournament_environment(
    schedules: list[dict[str, str]],
    as_of: date,
    factors: dict[tuple[str, str, str], dict[str, str]],
    surface_baselines: dict[tuple[str, str], dict[str, str]],
) -> dict[tuple[str, str], dict[str, str]]:
    """Same-edition tournament speed/volatility adjustment.

    This is deliberately conservative: completed matches nudge aces, DFs, and
    breaks toward how the event is playing this year, but venue history remains
    the base until the current sample is large enough.
    """
    meta_by_event: dict[tuple[str, str], dict[str, str]] = {}
    main_draw_events = slam_main_draw_active_events(schedules)
    for row in schedules:
        tour = str(row.get("tour") or "").upper()
        tour_id = str(row.get("tour_id") or "").strip()
        tournament = str(row.get("tournament") or "").strip()
        surface = str(row.get("surface") or "").strip()
        if tour in {"ATP", "WTA"} and tour_id and tournament and surface:
            meta_by_event[(tour, tour_id)] = {
                "tournament": tournament,
                "surface": surface,
            }
    if not meta_by_event:
        return {}

    totals: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    tour_ids_by_tour: dict[str, set[str]] = defaultdict(set)
    for tour, tour_id in meta_by_event:
        tour_ids_by_tour[tour].add(tour_id)

    for tour, tour_ids in tour_ids_by_tour.items():
        tour_lower = tour.lower()
        stat_rows, game_rows = load_current_event_rows(tour_lower, tour_ids)
        stat_index: dict[tuple[str, str, str, str], dict[str, str]] = {}
        for row in stat_rows:
            tour_id = str(row.get("tour_id") or "").strip()
            key = (
                str(row.get("winner_id") or "").strip(),
                str(row.get("loser_id") or "").strip(),
                tour_id,
                str(row.get("round_id") or "").strip(),
            )
            stat_index.setdefault(key, row)

        for game in game_rows:
            tour_id = str(game.get("tour_id") or "").strip()
            match_date = parse_date(game.get("date"))
            if match_date is None or match_date >= as_of:
                continue
            winner_id = str(game.get("winner_id") or "").strip()
            loser_id = str(game.get("loser_id") or "").strip()
            round_id = str(game.get("round_id") or "").strip()
            if skip_slam_qualifying_for_main_draw(main_draw_events, tour, tour_id, round_id):
                continue
            if not winner_id or not loser_id or winner_id == loser_id:
                continue
            stat = stat_index.get((winner_id, loser_id, tour_id, round_id))
            if not stat:
                continue
            svpt = oncourt_service_points(stat, "w") + oncourt_service_points(stat, "l")
            if svpt <= 0:
                continue
            match_games = parse_score_total_games(game.get("result"))
            sets_played, first_set_tb, match_tb = parse_score_tiebreaks(game.get("result"))
            breaks = parse_int(stat.get("w_bpw")) + parse_int(stat.get("l_bpw"))
            bucket = totals[(tour, tour_id)]
            bucket["matches"] += 1
            bucket["aces"] += parse_int(stat.get("w_ace")) + parse_int(stat.get("l_ace"))
            bucket["dfs"] += parse_int(stat.get("w_df")) + parse_int(stat.get("l_df"))
            bucket["svpt"] += svpt
            bucket["breaks"] += breaks
            bucket["match_games"] += match_games
            bucket["sets"] += sets_played
            bucket["first_set_tiebreaks"] += first_set_tb
            bucket["match_tiebreaks"] += match_tb

    out: dict[tuple[str, str], dict[str, str]] = {}
    for key, values in totals.items():
        tour, tour_id = key
        meta = meta_by_event.get(key) or {}
        tournament = meta.get("tournament") or ""
        surface = meta.get("surface") or ""
        matches = int(values.get("matches", 0))
        svpt = values.get("svpt", 0.0)
        if matches <= 0 or svpt <= 0:
            continue
        factor = factors.get((tour, tournament, surface)) or surface_baseline_factor(
            tour=tour,
            tournament=tournament,
            surface=surface,
            surface_baselines=surface_baselines,
        )
        weight = current_env_weight(matches)
        current_ace_rate = values.get("aces", 0.0) / svpt
        current_df_rate = values.get("dfs", 0.0) / svpt
        match_games = values.get("match_games", 0.0)
        current_break_rate = values.get("breaks", 0.0) / match_games if match_games > 0 else 0.0
        current_first_set_tb_rate = values.get("first_set_tiebreaks", 0.0) / matches if matches > 0 else 0.0
        current_match_tb_rate = values.get("match_tiebreaks", 0.0) / matches if matches > 0 else 0.0
        baseline_ace = parse_float(factor.get("ace_rate")) or parse_float(factor.get("tour_surface_baseline_ace"))
        baseline_df = parse_float(factor.get("df_rate")) or parse_float(factor.get("tour_surface_baseline_df"))
        baseline_first_set_tb = parse_float(factor.get("first_set_tiebreak_rate")) or parse_float(factor.get("tour_surface_baseline_first_set_tiebreak"))
        baseline_match_tb = parse_float(factor.get("match_tiebreak_rate")) or parse_float(factor.get("tour_surface_baseline_match_tiebreak"))
        baseline_break = 0.235 if tour == "ATP" else 0.285
        ace_factor = _clipped_ratio_factor(
            current_rate=current_ace_rate,
            baseline_rate=baseline_ace,
            weight=weight,
            low=CURRENT_ENV_ACE_DF_MIN,
            high=CURRENT_ENV_ACE_DF_MAX,
        )
        df_factor = _clipped_ratio_factor(
            current_rate=current_df_rate,
            baseline_rate=baseline_df,
            weight=weight,
            low=CURRENT_ENV_ACE_DF_MIN,
            high=CURRENT_ENV_ACE_DF_MAX,
        )
        break_factor = _clipped_ratio_factor(
            current_rate=current_break_rate,
            baseline_rate=baseline_break,
            weight=weight,
            low=CURRENT_ENV_BREAK_MIN,
            high=CURRENT_ENV_BREAK_MAX,
        )
        first_set_tiebreak_factor = _clipped_ratio_factor(
            current_rate=current_first_set_tb_rate,
            baseline_rate=baseline_first_set_tb,
            weight=weight,
            low=CURRENT_ENV_TIEBREAK_MIN,
            high=CURRENT_ENV_TIEBREAK_MAX,
        )
        match_tiebreak_factor = _clipped_ratio_factor(
            current_rate=current_match_tb_rate,
            baseline_rate=baseline_match_tb,
            weight=weight,
            low=CURRENT_ENV_TIEBREAK_MIN,
            high=CURRENT_ENV_TIEBREAK_MAX,
        )
        out[key] = {
            "matches": str(matches),
            "svpt": str(int(svpt)),
            "match_games": str(int(match_games)),
            "weight": f"{weight:.3f}",
            "ace_rate": f"{current_ace_rate:.5f}",
            "df_rate": f"{current_df_rate:.5f}",
            "break_rate": f"{current_break_rate:.5f}" if current_break_rate > 0 else "",
            "first_set_tiebreak_rate": f"{current_first_set_tb_rate:.5f}" if current_first_set_tb_rate > 0 else "",
            "match_tiebreak_rate": f"{current_match_tb_rate:.5f}" if current_match_tb_rate > 0 else "",
            "ace_factor": f"{ace_factor:.4f}",
            "df_factor": f"{df_factor:.4f}",
            "break_factor": f"{break_factor:.4f}",
            "first_set_tiebreak_factor": f"{first_set_tiebreak_factor:.4f}",
            "match_tiebreak_factor": f"{match_tiebreak_factor:.4f}",
            "sample_flag": "LIVE_OK" if matches >= 8 else "LIVE_LOW_SAMPLE",
        }
    return out


def _chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def load_fair_odds_expected_games(
    schedules: list[dict[str, str]],
    *,
    source: str,
) -> dict[tuple[str, str, str], dict[str, str]]:
    """Load match-specific expected total games from daily_fair_odds.

    Keyed by (tour_id, player1_id, player2_id). The board also indexes reversed
    order because projections are written as two player rows per match.
    """
    mode = (source or "").strip().lower()
    if mode in {"", "off", "none", "0", "false", "no"}:
        return {}
    tour_ids = sorted({str(row.get("tour_id") or "").strip() for row in schedules if str(row.get("tour_id") or "").strip()})
    if not tour_ids:
        return {}
    load_env()
    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    if not url or not key:
        if mode != "required":
            print("Fair-odds match totals: Supabase env missing; using venue/tournament match-length fallback.")
            return {}
        raise SystemExit("Fair-odds match totals required but NEXT_PUBLIC_SUPABASE_URL / SUPABASE key is missing.")

    try:
        import requests
    except ImportError as exc:
        if mode != "required":
            print(f"Fair-odds match totals: requests unavailable ({exc}); using fallback.")
            return {}
        raise

    base = url.rstrip("/") + "/rest/v1"
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    out: dict[tuple[str, str, str], dict[str, str]] = {}
    try:
        for chunk in _chunked(tour_ids, 120):
            response = requests.get(
                f"{base}/daily_fair_odds",
                headers=headers,
                params={
                    "select": "tour_id,player1_id,player2_id,expected_total_games,confidence",
                    "tour_id": f"in.({','.join(chunk)})",
                    "limit": 5000,
                },
                timeout=25,
            )
            response.raise_for_status()
            for row in response.json():
                expected = parse_float(row.get("expected_total_games"))
                if expected is None or expected < 12 or expected > 48:
                    continue
                tour_id = str(row.get("tour_id") or "").strip()
                p1 = str(row.get("player1_id") or "").strip()
                p2 = str(row.get("player2_id") or "").strip()
                if not tour_id or not p1 or not p2:
                    continue
                payload = {
                    "expected_total_games": f"{expected:.1f}",
                    "confidence": str(row.get("confidence") or ""),
                    "source": "fair_odds",
                }
                out[(tour_id, p1, p2)] = payload
                out[(tour_id, p2, p1)] = payload
    except Exception as exc:
        if mode == "required":
            raise
        print(f"Fair-odds match totals: load failed ({exc}); using venue/tournament match-length fallback.")
        return {}

    print(f"Fair-odds match totals: loaded {len(out) // 2} matches from daily_fair_odds.")
    return out


def load_current_tournament_logs(schedules: list[dict[str, str]], as_of: date) -> dict[tuple[str, str, str], list[dict[str, str]]]:
    """Per-round aces/DF logs for players still in the current tournament draw."""
    tour_ids_by_tour: dict[str, set[str]] = defaultdict(set)
    main_draw_events = slam_main_draw_active_events(schedules)
    for row in schedules:
        tour = str(row.get("tour") or "").upper()
        tour_id = str(row.get("tour_id") or "").strip()
        if tour in {"ATP", "WTA"} and tour_id:
            tour_ids_by_tour[tour].add(tour_id)
    if not tour_ids_by_tour:
        return {}

    tournament_names = {
        (str(row.get("tour") or "").upper(), str(row.get("tour_id") or "").strip()): str(
            row.get("tournament") or ""
        ).strip()
        for row in schedules
    }
    logs: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for tour, tour_ids in tour_ids_by_tour.items():
        tour_lower = tour.lower()
        player_names = load_oncourt_player_names(tour_lower)
        stat_rows, game_rows = load_current_event_rows(tour_lower, tour_ids)
        stat_index: dict[tuple[str, str, str, str], dict[str, str]] = {}
        for row in stat_rows:
            tour_id = str(row.get("tour_id") or "").strip()
            key = (
                str(row.get("winner_id") or "").strip(),
                str(row.get("loser_id") or "").strip(),
                tour_id,
                str(row.get("round_id") or "").strip(),
            )
            stat_index.setdefault(key, row)

        for game in game_rows:
            tour_id = str(game.get("tour_id") or "").strip()
            match_date = parse_date(game.get("date"))
            if match_date is None or match_date >= as_of:
                continue
            winner_id = str(game.get("winner_id") or "").strip()
            loser_id = str(game.get("loser_id") or "").strip()
            round_id = str(game.get("round_id") or "").strip()
            if skip_slam_qualifying_for_main_draw(main_draw_events, tour, tour_id, round_id):
                continue
            if not winner_id or not loser_id or winner_id == loser_id:
                continue
            stat = stat_index.get((winner_id, loser_id, tour_id, round_id))
            if not stat:
                continue
            winner_name = player_names.get(winner_id, winner_id)
            loser_name = player_names.get(loser_id, loser_id)
            tournament_name = tournament_names.get((tour, tour_id), "")
            base = {
                "date": match_date.isoformat(),
                "round": round_label(round_id, tournament_name),
                "result": str(game.get("result") or "").strip(),
            }
            _, first_set_tb, match_tb = parse_score_tiebreaks(game.get("result"))
            logs[(tour, tour_id, winner_id)].append(
                {
                    **base,
                    "opponent": loser_name,
                    "aces": str(parse_int(stat.get("w_ace"))),
                    "dfs": str(parse_int(stat.get("w_df"))),
                    "breaks_for": str(parse_int(stat.get("w_bpw"))),
                    "broken": str(max(0, parse_int(stat.get("w_bpfaced")) - parse_int(stat.get("w_bpsaved")))),
                    "total_breaks": str(
                        parse_int(stat.get("w_bpw"))
                        + max(0, parse_int(stat.get("w_bpfaced")) - parse_int(stat.get("w_bpsaved")))
                    ),
                    "first_set_tiebreak": str(first_set_tb),
                    "match_tiebreak": str(match_tb),
                    "svpt": str(oncourt_service_points(stat, "w")),
                }
            )
            logs[(tour, tour_id, loser_id)].append(
                {
                    **base,
                    "opponent": winner_name,
                    "aces": str(parse_int(stat.get("l_ace"))),
                    "dfs": str(parse_int(stat.get("l_df"))),
                    "breaks_for": str(parse_int(stat.get("l_bpw"))),
                    "broken": str(max(0, parse_int(stat.get("l_bpfaced")) - parse_int(stat.get("l_bpsaved")))),
                    "total_breaks": str(
                        parse_int(stat.get("l_bpw"))
                        + max(0, parse_int(stat.get("l_bpfaced")) - parse_int(stat.get("l_bpsaved")))
                    ),
                    "first_set_tiebreak": str(first_set_tb),
                    "match_tiebreak": str(match_tb),
                    "svpt": str(oncourt_service_points(stat, "l")),
                }
            )

    for player_logs in logs.values():
        player_logs.sort(key=lambda item: (item.get("date", ""), item.get("round", "")))
        for index, item in enumerate(player_logs, start=1):
            item["draw_round"] = item.get("round", "")
            item["round"] = f"Round {index}"
    return logs


def project_side(
    *,
    schedule: dict[str, str],
    player: str,
    opponent: str,
    player_id: str,
    baseline: dict[tuple[str, str, str], dict[str, dict[str, str]]],
    activity: dict[tuple[str, str, str], dict[str, str]],
    factors: dict[tuple[str, str, str], dict[str, str]],
    surface_baselines: dict[tuple[str, str], dict[str, str]],
    tournament_samples: dict[tuple[str, str, str], int],
    aliases: dict[tuple[str, str], str],
    baseline_names: dict[str, set[str]],
    current_tournament_stats: dict[tuple[str, str, str], dict[str, str]],
    current_tournament_logs: dict[tuple[str, str, str], list[dict[str, str]]],
    current_tournament_environment: dict[tuple[str, str], dict[str, str]],
    fair_odds_expected_games: dict[tuple[str, str, str], dict[str, str]],
) -> dict[str, str]:
    tour = schedule["tour"].upper()
    surface = schedule["surface"]
    tournament = schedule["tournament"]
    round_id = schedule.get("round_id_raw")
    player_resolution = resolve_baseline_name(
        tour=tour,
        value=player,
        available_names=baseline_names,
        aliases=aliases,
    )
    opponent_resolution = resolve_baseline_name(
        tour=tour,
        value=opponent,
        available_names=baseline_names,
        aliases=aliases,
    )
    player_lookup = player_resolution.name
    opponent_lookup = opponent_resolution.name
    player_rows = baseline.get((tour, player_lookup, surface), {})
    opponent_rows = baseline.get((tour, opponent_lookup, surface), {})
    player_all_rows = baseline.get((tour, player_lookup, "All"), {})
    opponent_all_rows = baseline.get((tour, opponent_lookup, "All"), {})
    player_activity_l12m = activity.get((tour, player_lookup, "L12M"), {})
    factor = factors.get((tour, tournament, surface)) or {}
    factor_source = "venue" if factor else ""
    factor_clipped = False
    if not factor:
        factor = surface_baseline_factor(
            tour=tour,
            tournament=tournament,
            surface=surface,
            surface_baselines=surface_baselines,
        )
        factor_source = "surface_baseline" if factor else ""
    elif factor_source == "venue":
        factor, factor_clipped = clipped_venue_factor_row(factor)
    match_games_default = default_match_games(tour, tournament, round_id)
    # Slam venue averages are best-of-five for ATP main draws. Qualifiers are
    # best-of-three, so reusing that match-length average materially inflates
    # ace and double-fault projections.
    fallback_expected_games = (
        match_games_default
        if is_slam_qualifying_round(tournament, round_id)
        else parse_float(factor.get("match_games_per_match"), match_games_default)
    )
    expected_games_source = "venue_avg" if factor_source == "venue" else ("surface_avg" if factor_source == "surface_baseline" else "default")
    expected_games_confidence = ""
    fair_total_row = fair_odds_expected_games.get(
        (
            str(schedule.get("tour_id") or ""),
            str(player_id or ""),
            str(schedule.get("player2_id") if str(schedule.get("player1_id") or "") == str(player_id or "") else schedule.get("player1_id") or ""),
        )
    )
    fair_expected_games = parse_float((fair_total_row or {}).get("expected_total_games"))
    if fair_expected_games is not None and 12.0 <= fair_expected_games <= 48.0:
        expected_games = fair_expected_games
        expected_games_source = "fair_odds"
        expected_games_confidence = str((fair_total_row or {}).get("confidence") or "")
    else:
        expected_games = fallback_expected_games
    tournament_n = tournament_samples.get((tour, player_lookup, tournament), 0)
    same_tournament_row = current_tournament_stats.get((tour, str(schedule.get("tour_id") or ""), player_id))
    same_tournament_log = current_tournament_logs.get((tour, str(schedule.get("tour_id") or ""), player_id), [])
    current_env_row = current_tournament_environment.get((tour, str(schedule.get("tour_id") or "")))
    projection = project_player(
        tour=tour,
        player_rows=player_rows,
        opponent_rows=opponent_rows,
        player_all_rows=player_all_rows,
        opponent_all_rows=opponent_all_rows,
        factor_row=factor,
        expected_match_games=expected_games or match_games_default,
        slam_matches=tournament_n,
        same_tournament_row=same_tournament_row,
        current_tournament_env_row=current_env_row,
    )
    player_break_ladder, player_break_distribution, player_break_status = break_fair_odds_ladder(
        projection.expected_breaks_for,
        tour,
        "player_breaks",
    )
    l12m = player_rows.get("L12M") or {}
    l24m = player_rows.get("L24M") or {}
    career = player_rows.get("career_4y") or {}
    notes = list(projection.notes)
    tiebreak_notes = list(projection.tiebreak_notes)
    if not player_resolution.resolved:
        notes.append("PLAYER_NAME_UNRESOLVED")
    if not opponent_resolution.resolved:
        notes.append("OPPONENT_NAME_UNRESOLVED")
    if factor_source == "surface_baseline":
        notes.append("SURFACE_BASELINE_ONLY")
    elif not factor:
        notes.append("NO_VENUE_FACTOR")
    if factor_clipped:
        notes.append("VENUE_FACTOR_CLIPPED")
    venue_sample = parse_int(factor.get("matches"))
    venue_first_set_rate = parse_float(factor.get("first_set_tiebreak_rate"))
    venue_match_rate = parse_float(factor.get("match_tiebreak_rate"))
    if (
        factor_source != "surface_baseline"
        and venue_sample >= 50
        and (
            (venue_first_set_rate is not None and abs(projection.first_set_tiebreak_prob - venue_first_set_rate) > 0.08)
            or (venue_match_rate is not None and abs(projection.match_tiebreak_prob - venue_match_rate) > 0.08)
        )
    ):
        tiebreak_notes.append("LOW_VENUE_AGREEMENT")
    return {
        "date": schedule["date"],
        "generation_date": str(schedule.get("generation_date") or schedule.get("date") or ""),
        "scheduled_date": str(schedule.get("scheduled_date") or ""),
        "scheduled_start_utc": str(schedule.get("scheduled_start_utc") or ""),
        "schedule_status": str(schedule.get("schedule_status") or "confirmed"),
        "schedule_source": str(schedule.get("schedule_source") or schedule.get("source") or ""),
        "tour": tour,
        "tour_id": str(schedule.get("tour_id") or ""),
        "tournament": tournament,
        "round": schedule["round"],
        "player": player,
        "opponent": opponent,
        "player_id": str(player_id or ""),
        "opponent_id": str(
            schedule.get("player2_id")
            if str(schedule.get("player1_id") or "") == str(player_id or "")
            else schedule.get("player1_id") or ""
        ),
        "surface": surface,
        "projected_aces": fmt(projection.expected_aces),
        "projected_dfs": fmt(projection.expected_dfs),
        "projected_breaks_for": fmt(projection.expected_breaks_for),
        "projected_broken": fmt(projection.expected_broken),
        "projected_total_breaks": fmt(projection.expected_total_breaks),
        "player_break_fair_odds_json": player_break_ladder,
        "player_break_distribution": player_break_distribution,
        "player_break_model_status": player_break_status,
        "match_break_fair_odds_json": "",
        "match_break_distribution": "",
        "match_break_model_status": "",
        "first_set_tiebreak_pct": fmt(projection.first_set_tiebreak_prob * 100.0, 1),
        "match_tiebreak_pct": fmt(projection.match_tiebreak_prob * 100.0, 1),
        "first_set_tiebreak_fair_yes": fmt(projection.first_set_tiebreak_fair_yes, 2),
        "match_tiebreak_fair_yes": fmt(projection.match_tiebreak_fair_yes, 2),
        "first_set_tiebreak_base_pct": fmt(projection.first_set_tiebreak_base_prob * 100.0, 1),
        "match_tiebreak_base_pct": fmt(projection.match_tiebreak_base_prob * 100.0, 1),
        "ace_confidence": projection.ace_confidence,
        "df_confidence": projection.df_confidence,
        "break_confidence": projection.break_confidence,
        "tiebreak_confidence": projection.tiebreak_confidence,
        "service_points_estimate": fmt(projection.expected_service_points, 1),
        "service_games_estimate": fmt(projection.expected_service_games, 1),
        "expected_match_games": fmt(expected_games or match_games_default, 1),
        "expected_match_games_source": expected_games_source,
        "expected_match_games_confidence": expected_games_confidence,
        "player_baseline_name": player_lookup,
        "opponent_baseline_name": opponent_lookup,
        "player_name_resolution": player_resolution.method,
        "opponent_name_resolution": opponent_resolution.method,
        "player_l12m_svpt_sample": str(parse_int(l12m.get("svpt"))),
        "player_l12m_matches": str(parse_int(l12m.get("matches"))),
        "player_l24m_svpt_sample": str(parse_int(l24m.get("svpt"))),
        "player_l24m_matches": str(parse_int(l24m.get("matches"))),
        "player_career4y_svpt_sample": str(parse_int(career.get("svpt"))),
        "player_career4y_matches": str(parse_int(career.get("matches"))),
        "player_activity_l12m_matches": str(parse_int(player_activity_l12m.get("matches"))),
        "player_activity_l12m_svpt": str(parse_int(player_activity_l12m.get("svpt"))),
        "player_activity_l12m_main_matches": str(parse_int(player_activity_l12m.get("main_matches"))),
        "player_activity_l12m_qual_chall_matches": str(parse_int(player_activity_l12m.get("qual_chall_matches"))),
        "player_activity_last_match_date": str(player_activity_l12m.get("last_match_date") or ""),
        "player_activity_days_since_last_match": str(player_activity_l12m.get("days_since_last_match") or ""),
        "player_surface_svpt_sample": str(parse_int(career.get("svpt"))),
        "player_surface_matches": str(parse_int(career.get("matches"))),
        "player_slam_sample": str(tournament_n),
        "same_tournament_matches": str(projection.same_tournament_matches),
        "same_tournament_svpt": str(projection.same_tournament_svpt),
        "same_tournament_ace_weight": fmt(projection.same_tournament_ace_weight, 3),
        "same_tournament_df_weight": fmt(projection.same_tournament_df_weight, 3),
        "same_tournament_breaks_for": str(projection.same_tournament_breaks_for),
        "same_tournament_broken": str(projection.same_tournament_broken),
        "same_tournament_total_breaks": str(projection.same_tournament_total_breaks),
        "tournament_round_log": json.dumps(same_tournament_log, ensure_ascii=True, separators=(",", ":")),
        "venue_ace_factor": str(factor.get("ace_factor") or ""),
        "venue_df_factor": str(factor.get("df_factor") or ""),
        "venue_first_set_tiebreak_factor": fmt(projection.venue_first_set_tiebreak_factor, 4),
        "venue_match_tiebreak_factor": fmt(projection.venue_match_tiebreak_factor, 4),
        "player_tiebreak_factor": fmt(projection.player_tiebreak_factor, 4),
        "player_tiebreak_sample": str(projection.player_tiebreak_sample),
        "player_match_tiebreak_actual_pct": fmt(projection.player_match_tiebreak_rate * 100.0, 1),
        "opponent_match_tiebreak_actual_pct": fmt(projection.opponent_match_tiebreak_rate * 100.0, 1),
        "venue_first_set_tiebreak_actual_pct": fmt_rate_pct(factor.get("first_set_tiebreak_rate"), 1),
        "venue_match_tiebreak_actual_pct": fmt_rate_pct(factor.get("match_tiebreak_rate"), 1),
        "venue_factor_source": factor_source,
        "venue_sample_flag": str(factor.get("sample_flag") or ""),
        "current_env_matches": str(projection.current_env_matches),
        "current_env_svpt": str(projection.current_env_svpt),
        "current_env_weight": fmt(projection.current_env_weight, 3),
        "current_env_ace_factor": fmt(projection.current_env_ace_factor, 4),
        "current_env_df_factor": fmt(projection.current_env_df_factor, 4),
        "current_env_break_factor": fmt(projection.current_env_break_factor, 4),
        "current_env_first_set_tiebreak_factor": fmt(projection.current_env_first_set_tiebreak_factor, 4),
        "current_env_match_tiebreak_factor": fmt(projection.current_env_match_tiebreak_factor, 4),
        "current_env_first_set_tiebreak_actual_pct": fmt_rate_pct((current_env_row or {}).get("first_set_tiebreak_rate"), 1),
        "current_env_match_tiebreak_actual_pct": fmt_rate_pct((current_env_row or {}).get("match_tiebreak_rate"), 1),
        "current_env_sample_flag": str((current_env_row or {}).get("sample_flag") or ""),
        "ace_rate_adj": fmt(projection.ace_rate, 5),
        "df_rate_adj": fmt(projection.df_rate, 5),
        "break_rate_adj": fmt(projection.break_rate, 5),
        "broken_rate_adj": fmt(projection.broken_rate, 5),
        "service_point_win": fmt(projection.player_service_point_win, 4),
        "opponent_service_point_win": fmt(projection.opponent_service_point_win, 4),
        "break_notes": "|".join(dict.fromkeys(projection.break_notes)),
        "tiebreak_notes": "|".join(dict.fromkeys(tiebreak_notes)),
        "notes": "|".join(dict.fromkeys(notes)),
        "source": schedule["source"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    parser.add_argument("--activity", default=str(DEFAULT_ACTIVITY))
    parser.add_argument("--factors", default=str(DEFAULT_FACTORS))
    parser.add_argument("--surface-baselines", default=str(DEFAULT_SURFACE_BASELINES))
    parser.add_argument("--aliases", default=str(DEFAULT_ALIASES))
    parser.add_argument("--wta-schedule", default="")
    parser.add_argument("--include-completed", action="store_true")
    parser.add_argument(
        "--days-ahead",
        type=int,
        default=3,
        help="Include scheduled matches through this many calendar days after --as-of.",
    )
    parser.add_argument(
        "--fair-odds-totals-source",
        default=DEFAULT_FAIR_ODDS_TOTALS_SOURCE,
        choices=("auto", "required", "off"),
        help="Use daily_fair_odds.expected_total_games when available; fallback unless 'required'.",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    as_of = datetime.strptime(args.as_of, "%Y-%m-%d").date()
    baseline = load_baseline(Path(args.baseline))
    activity = load_activity(Path(args.activity))
    baseline_names = baseline_names_by_tour(baseline)
    factors = load_factors(Path(args.factors))
    surface_baselines = load_surface_baselines(Path(args.surface_baselines))
    aliases = load_aliases(Path(args.aliases))
    tournament_samples = load_tournament_samples(as_of)

    schedules = oncourt_schedule_rows("ATP", args.include_completed, args.as_of, args.days_ahead)
    schedules.extend(oncourt_schedule_rows("WTA", args.include_completed, args.as_of, args.days_ahead))
    oncourt_wta_count = sum(1 for row in schedules if row.get("source") == "oncourt_today_wta")
    if args.wta_schedule:
        schedules.extend(wta_schedule_rows(Path(args.wta_schedule)))
    fair_odds_expected_games = load_fair_odds_expected_games(
        schedules,
        source=args.fair_odds_totals_source,
    )
    current_tournament_stats = load_current_tournament_stats(schedules, as_of)
    current_tournament_logs = load_current_tournament_logs(schedules, as_of)
    current_tournament_environment = load_current_tournament_environment(
        schedules,
        as_of,
        factors,
        surface_baselines,
    )

    rows: list[dict[str, str]] = []
    for schedule in schedules:
        row_a = project_side(
            schedule=schedule,
            player=schedule["player1"],
            opponent=schedule["player2"],
            player_id=str(schedule.get("player1_id") or ""),
            baseline=baseline,
            activity=activity,
            factors=factors,
            surface_baselines=surface_baselines,
            tournament_samples=tournament_samples,
            aliases=aliases,
            baseline_names=baseline_names,
            current_tournament_stats=current_tournament_stats,
            current_tournament_logs=current_tournament_logs,
            current_tournament_environment=current_tournament_environment,
            fair_odds_expected_games=fair_odds_expected_games,
        )
        row_b = project_side(
            schedule=schedule,
            player=schedule["player2"],
            opponent=schedule["player1"],
            player_id=str(schedule.get("player2_id") or ""),
            baseline=baseline,
            activity=activity,
            factors=factors,
            surface_baselines=surface_baselines,
            tournament_samples=tournament_samples,
            aliases=aliases,
            baseline_names=baseline_names,
            current_tournament_stats=current_tournament_stats,
            current_tournament_logs=current_tournament_logs,
            current_tournament_environment=current_tournament_environment,
            fair_odds_expected_games=fair_odds_expected_games,
        )
        normalize_match_break_totals(row_a, row_b)
        rows.extend([row_a, row_b])

    fieldnames = [
        "date",
        "generation_date",
        "scheduled_date",
        "scheduled_start_utc",
        "schedule_status",
        "schedule_source",
        "tour",
        "tour_id",
        "tournament",
        "round",
        "player",
        "opponent",
        "player_id",
        "opponent_id",
        "surface",
        "projected_aces",
        "projected_dfs",
        "projected_breaks_for",
        "projected_broken",
        "projected_total_breaks",
        "player_break_fair_odds_json",
        "player_break_distribution",
        "player_break_model_status",
        "match_break_fair_odds_json",
        "match_break_distribution",
        "match_break_model_status",
        "first_set_tiebreak_pct",
        "match_tiebreak_pct",
        "first_set_tiebreak_fair_yes",
        "match_tiebreak_fair_yes",
        "first_set_tiebreak_base_pct",
        "match_tiebreak_base_pct",
        "ace_confidence",
        "df_confidence",
        "break_confidence",
        "tiebreak_confidence",
        "service_points_estimate",
        "service_games_estimate",
        "expected_match_games",
        "expected_match_games_source",
        "expected_match_games_confidence",
        "player_baseline_name",
        "opponent_baseline_name",
        "player_name_resolution",
        "opponent_name_resolution",
        "player_l12m_svpt_sample",
        "player_l12m_matches",
        "player_l24m_svpt_sample",
        "player_l24m_matches",
        "player_career4y_svpt_sample",
        "player_career4y_matches",
        "player_activity_l12m_matches",
        "player_activity_l12m_svpt",
        "player_activity_l12m_main_matches",
        "player_activity_l12m_qual_chall_matches",
        "player_activity_last_match_date",
        "player_activity_days_since_last_match",
        "player_surface_svpt_sample",
        "player_surface_matches",
        "player_slam_sample",
        "same_tournament_matches",
        "same_tournament_svpt",
        "same_tournament_ace_weight",
        "same_tournament_df_weight",
        "same_tournament_breaks_for",
        "same_tournament_broken",
        "same_tournament_total_breaks",
        "tournament_round_log",
        "venue_ace_factor",
        "venue_df_factor",
        "venue_first_set_tiebreak_factor",
        "venue_match_tiebreak_factor",
        "player_tiebreak_factor",
        "player_tiebreak_sample",
        "player_match_tiebreak_actual_pct",
        "opponent_match_tiebreak_actual_pct",
        "venue_first_set_tiebreak_actual_pct",
        "venue_match_tiebreak_actual_pct",
        "venue_factor_source",
        "venue_sample_flag",
        "current_env_matches",
        "current_env_svpt",
        "current_env_weight",
        "current_env_ace_factor",
        "current_env_df_factor",
        "current_env_break_factor",
        "current_env_first_set_tiebreak_factor",
        "current_env_match_tiebreak_factor",
        "current_env_first_set_tiebreak_actual_pct",
        "current_env_match_tiebreak_actual_pct",
        "current_env_sample_flag",
        "ace_rate_adj",
        "df_rate_adj",
        "break_rate_adj",
        "broken_rate_adj",
        "service_point_win",
        "opponent_service_point_win",
        "break_notes",
        "tiebreak_notes",
        "notes",
        "source",
    ]
    write_csv(Path(args.out), rows, fieldnames)
    print(f"Saved {len(rows)} rows: {args.out}")
    if oncourt_wta_count:
        print(f"WTA schedule source: OnCourt today_wta ({oncourt_wta_count} matches)")
    elif not args.wta_schedule:
        print("WTA schedule source missing: OnCourt today_wta had no usable supported rows; manual fallback not provided.")


if __name__ == "__main__":
    main()

