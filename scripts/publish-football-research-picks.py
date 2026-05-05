#!/usr/bin/env python3
"""Publish open research picks for the football canonical lanes.

The CLV monitors already know how to join published rows to captured prices.
This script is the missing feed: it scores upcoming fixtures with the promoted
research formulas and writes the published-picks CSVs consumed by the monitor.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import re
import subprocess
import sys
import unicodedata
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from settlement_utils import normalize_team_name  # noqa: E402


DEFAULT_TEAM_BASE = ROOT / "data" / "football-form" / "team-match-base.csv"
DEFAULT_TEAM_ODDS = ROOT / "data" / "team-shots" / "team-shots-odds-history.csv"
DEFAULT_TEAM_CURRENT_FIXTURES = ROOT / "data" / "team-shots" / "team-shots-upcoming.v2-nb-raw.csv"
DEFAULT_TEAM_ALLOWED = ROOT / "data" / "football-form" / "team-shots-v3-ema20-allowed-leagues.json"
DEFAULT_TEAM_OUT = ROOT / "data" / "football-form" / "team-shots-v3-ema20-published-picks.csv"
DEFAULT_CORNERS_PINNACLE = ROOT / "data" / "corners-ou" / "pinnacle-corners-odds.csv"
DEFAULT_CORNERS_ALLOWED = ROOT / "data" / "football-form" / "corners-v0-allowed-leagues.json"
DEFAULT_CORNERS_OUT = ROOT / "data" / "football-form" / "corners-v0-published-picks.csv"

TEAM_MODEL = "canonical_form_v3_ema20_nb"
TEAM_MIN_EDGE = 0.05
CORNERS_MODEL = "canonical_form_v0"
CORNERS_MIN_EDGE = 0.05
CORNERS_ALLOWED_SIDES = {"over"}
MAX_PICKS_PER_FIXTURE = 1

PUBLISHED_FIELDS = [
    "pick_id",
    "published_at_utc",
    "kickoff_utc",
    "match_id",
    "match_date",
    "league",
    "match",
    "home_team",
    "away_team",
    "team",
    "bookmaker",
    "selection",
    "line",
    "side",
    "model",
    "model_fair_odds",
    "model_implied_prob",
    "book_odds",
    "edge",
    "current_model_would_have_priced",
    "confidence_guard_applied",
    "blocked_reason",
    "result",
    "pnl_units",
]

LEAGUE_ALIASES = {
    "premier league": "epl",
    "england premier league": "epl",
    "epl": "epl",
    "serie a": "serie-a",
    "italy serie a": "serie-a",
    "serie-a": "serie-a",
    "la liga": "la-liga",
    "spain la liga": "la-liga",
    "la-liga": "la-liga",
    "bundesliga": "bundesliga",
    "germany bundesliga": "bundesliga",
    "ligue 1": "ligue-1",
    "france ligue 1": "ligue-1",
    "ligue-1": "ligue-1",
}

TEAM_KEY_ALIASES = {
    "acf fiorentina": "fiorentina",
    "borussia dortmund": "dortmund",
    "borussia monchengladbach": "m gladbach",
    "cagliari": "cagliari",
    "cagliari calcio": "cagliari",
    "ca osasuna": "osasuna",
    "como": "como",
    "como 1907": "como",
    "elche": "elche",
    "fc barcelona": "barcelona",
    "manchester united": "man united",
    "man utd": "man united",
    "real oviedo": "oviedo",
    "real sociedad san sebastian": "sociedad",
    "rc celta de vigo": "celta",
    "sunderland afc": "sunderland",
    "torino": "torino",
    "torino fc": "torino",
    "vfb stuttgart": "stuttgart",
    "villarreal cf": "villarreal",
}

EXTRA_GENERIC_TOKENS = {
    "1",
    "ac",
    "acf",
    "afc",
    "as",
    "bc",
    "ca",
    "calcio",
    "cf",
    "cfc",
    "club",
    "fc",
    "football",
    "rc",
    "sc",
    "ssc",
    "ud",
    "us",
    "vfb",
    "vfl",
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


FORM_BUILD = load_module("football_form_build", SCRIPTS / "build-football-form-layer.py")
BACKTEST = load_module("football_form_backtest", SCRIPTS / "backtest-football-form-layer.py")


def clean_text(value: str) -> str:
    text = (value or "").strip().lower().replace("(corners)", "")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def clean_display_team(value: str) -> str:
    return re.sub(r"\s*\(corners\)\s*", "", value or "", flags=re.IGNORECASE).strip()


def team_key(value: str) -> str:
    raw = clean_text(value)
    if raw in TEAM_KEY_ALIASES:
        return TEAM_KEY_ALIASES[raw]
    normalized = normalize_team_name(value)
    if normalized in TEAM_KEY_ALIASES:
        return TEAM_KEY_ALIASES[normalized]
    stripped = " ".join(token for token in raw.split() if token not in EXTRA_GENERIC_TOKENS).strip()
    if stripped in TEAM_KEY_ALIASES:
        return TEAM_KEY_ALIASES[stripped]
    return stripped or normalized or raw


def league_slug(value: str) -> str:
    raw = clean_text(value).replace(" ", "-")
    text = clean_text(value)
    return LEAGUE_ALIASES.get(text, LEAGUE_ALIASES.get(raw, raw))


def parse_dt(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_date(value: Any) -> date | None:
    dt = parse_dt(value)
    if dt:
        return dt.date()
    raw = str(value or "").strip()[:10]
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError:
        return None


def fmt_dt(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def pf(value: Any) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def line_label(value: Any) -> str:
    parsed = pf(value)
    return f"{parsed:.1f}" if parsed is not None else str(value or "").strip()


def fair_odds(prob: float) -> float:
    prob = max(1e-6, min(1.0 - 1e-6, prob))
    return 1.0 / prob


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PUBLISHED_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def ensure_team_base(path: Path) -> None:
    """Build the canonical football form layer instead of silently publishing zero fresh picks."""
    if path.exists():
        return
    print(f"{path.relative_to(ROOT)} missing; rebuilding canonical football form layer.")
    subprocess.run([sys.executable, str(SCRIPTS / "build-football-form-layer.py")], check=True)
    if not path.exists():
        raise SystemExit(f"Required team base still missing after rebuild: {path}")


def load_allowed(path: Path) -> set[str]:
    if not path.exists():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {league_slug(str(item)) for item in payload.get("allowed_leagues", [])}


def fixture_key(match_date: str, league: str, home: str, away: str) -> str:
    return "|".join([match_date, league_slug(league), team_key(home), team_key(away)])


def team_fixture_key(match_date: str, league: str, home: str, away: str, team: str) -> str:
    return "|".join([fixture_key(match_date, league, home, away), team_key(team)])


def season_label(day: date) -> str:
    if day.month >= 7:
        return f"{day.year}-{day.year + 1}"
    return f"{day.year - 1}-{day.year}"


def avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def build_base_indexes(rows: list[dict[str, str]]):
    by_team: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    by_league: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        league = league_slug(row.get("league", ""))
        key = row.get("team_key") or team_key(row.get("team", ""))
        row["league"] = league
        row["team_key"] = key
        by_team[(league, key)].append(row)
        by_league[league].append(row)
    for bucket in list(by_team.values()) + list(by_league.values()):
        bucket.sort(key=lambda item: (item.get("date", ""), item.get("team", "")))
    return by_team, by_league


def league_baseline(rows: list[dict[str, str]], fixture_date: date) -> dict[str, Any]:
    prior = [row for row in rows if (parsed := parse_date(row.get("date"))) and parsed < fixture_date]
    t12_cutoff = fixture_date - timedelta(days=365)
    trailing = [row for row in prior if (parsed := parse_date(row.get("date"))) and parsed >= t12_cutoff]

    def metric_avg(source: list[dict[str, str]], field: str) -> str:
        values = [value for row in source if (value := pf(row.get(field))) is not None]
        value = avg(values)
        return f"{value:.4f}".rstrip("0").rstrip(".") if value is not None else ""

    return {
        "league_prior_rows": len(prior),
        "league_prior_shots_for_avg": metric_avg(prior, "shots_for"),
        "league_prior_shots_against_avg": metric_avg(prior, "shots_against"),
        "league_prior_corners_for_avg": metric_avg(prior, "corners_for"),
        "league_prior_corners_against_avg": metric_avg(prior, "corners_against"),
        "league_prior_xg_for_avg": metric_avg(prior, "xg_for"),
        "league_prior_xg_against_avg": metric_avg(prior, "xg_against"),
        "league_t12_rows": len(trailing),
        "league_t12_shots_for_avg": metric_avg(trailing, "shots_for"),
        "league_t12_shots_against_avg": metric_avg(trailing, "shots_against"),
        "league_t12_corners_for_avg": metric_avg(trailing, "corners_for"),
        "league_t12_corners_against_avg": metric_avg(trailing, "corners_against"),
        "league_t12_xg_for_avg": metric_avg(trailing, "xg_for"),
        "league_t12_xg_against_avg": metric_avg(trailing, "xg_against"),
    }


def live_form_row(
    *,
    by_team: dict[tuple[str, str], list[dict[str, str]]],
    by_league: dict[str, list[dict[str, str]]],
    league: str,
    fixture_date: date,
    team: str,
    opponent: str,
    venue: str,
    home: str,
    away: str,
) -> dict[str, Any] | None:
    key = team_key(team)
    history = [
        row for row in by_team.get((league, key), [])
        if (parsed := parse_date(row.get("date"))) and parsed < fixture_date
    ]
    if not history:
        return None

    out: dict[str, Any] = {
        "date": fixture_date.isoformat(),
        "league": league,
        "season": season_label(fixture_date),
        "team": team,
        "team_key": key,
        "opponent": opponent,
        "opponent_key": team_key(opponent),
        "venue": venue,
        "home_team": home,
        "away_team": away,
        "current_goals_for": "",
        "current_goals_against": "",
        "current_xg_for": "",
        "current_xg_against": "",
        "current_shots_for": "",
        "current_shots_against": "",
        "current_sot_for": "",
        "current_sot_against": "",
        "current_corners_for": "",
        "current_corners_against": "",
        # Live 1X2 odds are not currently captured with the team-shots feed.
        # Leaving these blank makes the v3 game-state adjustment neutral.
        "market_team_win_prob": "",
        "market_opp_win_prob": "",
    }
    out.update(league_baseline(by_league.get(league, []), fixture_date))
    for window in FORM_BUILD.WINDOWS:
        out.update(FORM_BUILD.summarize_window(history, window))
        out.update(FORM_BUILD.relative_window_fields(out, window))
    out.update(FORM_BUILD.summarize_ema_window(history))
    return out


def alpha_for_league(rows: list[dict[str, str]], league: str, fixture_date: date) -> float:
    values = [
        value for row in rows
        if league_slug(row.get("league", "")) == league
        and (parsed := parse_date(row.get("date"))) is not None
        and parsed < fixture_date
        and (value := pf(row.get("shots_for"))) is not None
    ]
    alpha = BACKTEST.estimate_alpha(values)
    if alpha <= 0:
        all_values = [
            value for row in rows
            if (parsed := parse_date(row.get("date"))) is not None
            and parsed < fixture_date
            and (value := pf(row.get("shots_for"))) is not None
        ]
        alpha = BACKTEST.estimate_alpha(all_values)
    return alpha


def latest_team_shots_odds(rows: list[dict[str, str]], now: datetime) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        kickoff = parse_dt(row.get("kickoff_at"))
        captured = parse_dt(row.get("captured_at"))
        if not kickoff or not captured or kickoff <= now:
            continue
        league = league_slug(row.get("competition") or row.get("league", ""))
        home = clean_display_team(row.get("home_team", "").strip())
        away = clean_display_team(row.get("away_team", "").strip())
        team = row.get("team", "").strip()
        side = row.get("side", "").strip().lower()
        odds = pf(row.get("odds_decimal"))
        if not (league and home and away and team and side in {"over", "under"} and odds and odds > 1):
            continue
        line = line_label(row.get("line"))
        bookmaker = row.get("bookmaker", "").strip() or "Bet365"
        key = "|".join([
            fixture_key(kickoff.date().isoformat(), league, home, away),
            team_key(team),
            line,
            side,
            clean_text(bookmaker),
        ])
        current = latest.get(key)
        if current is None or captured > current["captured_at_dt"]:
            latest[key] = {
                **row,
                "home_team": home,
                "away_team": away,
                "league_slug": league,
                "kickoff": kickoff,
                "captured_at_dt": captured,
                "odds": odds,
                "line_label": line,
                "bookmaker": bookmaker,
            }
    return list(latest.values())


def current_team_fixture_set(rows: list[dict[str, str]], now: datetime) -> set[str]:
    keys: set[str] = set()
    for row in rows:
        kickoff = parse_dt(row.get("kickoff_iso") or row.get("kickoff_at"))
        if not kickoff or kickoff <= now:
            continue
        league = league_slug(row.get("league") or row.get("competition") or "")
        match_date = kickoff.date().isoformat()
        home = row.get("home_team", "")
        away = row.get("away_team", "")
        if not (league and home and away):
            continue
        keys.add(fixture_key(match_date, league, home, away))
        keys.add(team_fixture_key(match_date, league, home, away, home))
        keys.add(team_fixture_key(match_date, league, home, away, away))
    return keys


def publish_team_shots(args: argparse.Namespace, by_team, by_league, base_rows: list[dict[str, str]], now: datetime) -> list[dict[str, Any]]:
    allowed = load_allowed(args.team_allowed)
    current_fixtures = current_team_fixture_set(load_csv(args.team_current_fixtures), now)
    odds_rows = latest_team_shots_odds(load_csv(args.team_odds), now)
    picks: list[dict[str, Any]] = []

    for row in odds_rows:
        league = row["league_slug"]
        if league not in allowed:
            continue
        kickoff: datetime = row["kickoff"]
        fixture_date = kickoff.date()
        home = clean_display_team(row.get("home_team", "").strip())
        away = clean_display_team(row.get("away_team", "").strip())
        team = row.get("team", "").strip()
        opp = away if team_key(team) == team_key(home) else home
        venue = "home" if team_key(team) == team_key(home) else "away"
        team_form = live_form_row(
            by_team=by_team,
            by_league=by_league,
            league=league,
            fixture_date=fixture_date,
            team=team,
            opponent=opp,
            venue=venue,
            home=home,
            away=away,
        )
        opp_form = live_form_row(
            by_team=by_team,
            by_league=by_league,
            league=league,
            fixture_date=fixture_date,
            team=opp,
            opponent=team,
            venue="away" if venue == "home" else "home",
            home=home,
            away=away,
        )
        if team_form is None or opp_form is None:
            continue
        lam = BACKTEST.canonical_team_shots_ema20_lambda(team_form, opp_form, use_market=True)
        if lam is None:
            continue
        line = pf(row["line_label"])
        if line is None:
            continue
        alpha = alpha_for_league(base_rows, league, fixture_date)
        prob_over = BACKTEST.negative_binomial_prob_over(line, lam, alpha)
        side = row.get("side", "").strip().lower()
        model_prob = prob_over if side == "over" else 1.0 - prob_over
        edge = (model_prob * row["odds"]) - 1.0
        if edge < args.team_min_edge:
            continue

        match_date = fixture_date.isoformat()
        fx_key = fixture_key(match_date, league, home, away)
        team_fx_key = team_fixture_key(match_date, league, home, away, team)
        current_priced = fx_key in current_fixtures or team_fx_key in current_fixtures
        blocked = [] if current_priced else ["canonical_only_guard"]
        pick_id = "|".join([TEAM_MODEL, team_fx_key, row["line_label"], side])
        picks.append({
            "pick_id": pick_id,
            "published_at_utc": fmt_dt(row["captured_at_dt"]),
            "kickoff_utc": fmt_dt(kickoff),
            "match_id": fx_key,
            "match_date": match_date,
            "league": league,
            "match": f"{home} vs {away}",
            "home_team": home,
            "away_team": away,
            "team": team,
            "bookmaker": row["bookmaker"],
            "selection": f"{team} {side} {row['line_label']}",
            "line": row["line_label"],
            "side": side,
            "model": TEAM_MODEL,
            "model_fair_odds": round(fair_odds(model_prob), 6),
            "model_implied_prob": round(model_prob, 6),
            "book_odds": round(row["odds"], 6),
            "edge": round(edge, 6),
            "current_model_would_have_priced": "true" if current_priced else "false",
            "confidence_guard_applied": "true" if blocked else "false",
            "blocked_reason": ";".join(blocked),
            "result": "",
            "pnl_units": "",
        })

    return cap_fixture_volume(picks)


def latest_corners_odds(rows: list[dict[str, str]], now: datetime) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        kickoff = parse_dt(row.get("kickoff_iso"))
        captured = parse_dt(row.get("captured_at"))
        if not kickoff or not captured or kickoff <= now:
            continue
        league = league_slug(row.get("league", ""))
        home = clean_display_team(row.get("home_team", "").strip())
        away = clean_display_team(row.get("away_team", "").strip())
        side = row.get("side", "").strip().lower()
        odds = pf(row.get("odds_decimal"))
        line = pf(row.get("line"))
        if line is None or not math.isclose(line % 1.0, 0.5, abs_tol=1e-9):
            continue
        if not (league and home and away and side in {"over", "under"} and odds and odds > 1):
            continue
        label = line_label(line)
        key = "|".join([fixture_key(kickoff.date().isoformat(), league, home, away), label, side])
        current = latest.get(key)
        if current is None or captured > current["captured_at_dt"]:
            latest[key] = {
                **row,
                "home_team": home,
                "away_team": away,
                "league_slug": league,
                "kickoff": kickoff,
                "captured_at_dt": captured,
                "odds": odds,
                "line_label": label,
            }
    return list(latest.values())


def publish_corners(args: argparse.Namespace, by_team, by_league, now: datetime) -> list[dict[str, Any]]:
    allowed = load_allowed(args.corners_allowed)
    odds_rows = latest_corners_odds(load_csv(args.corners_pinnacle), now)
    league_shots_avg = {
        league: avg([value for row in rows if (value := pf(row.get("shots_for"))) is not None]) or 0.0
        for league, rows in by_league.items()
    }
    picks: list[dict[str, Any]] = []

    for row in odds_rows:
        league = row["league_slug"]
        if league not in allowed:
            continue
        kickoff: datetime = row["kickoff"]
        fixture_date = kickoff.date()
        home = clean_display_team(row.get("home_team", "").strip())
        away = clean_display_team(row.get("away_team", "").strip())
        home_form = live_form_row(
            by_team=by_team,
            by_league=by_league,
            league=league,
            fixture_date=fixture_date,
            team=home,
            opponent=away,
            venue="home",
            home=home,
            away=away,
        )
        away_form = live_form_row(
            by_team=by_team,
            by_league=by_league,
            league=league,
            fixture_date=fixture_date,
            team=away,
            opponent=home,
            venue="away",
            home=home,
            away=away,
        )
        if home_form is None or away_form is None:
            continue
        home_lam = BACKTEST.canonical_corners_lambda(home_form, away_form, league_shots_avg.get(league, 0.0))
        away_lam = BACKTEST.canonical_corners_lambda(away_form, home_form, league_shots_avg.get(league, 0.0))
        if home_lam is None or away_lam is None:
            continue
        total_lam = home_lam + away_lam
        line = pf(row["line_label"])
        if line is None:
            continue
        prob_over = BACKTEST.poisson_prob_over(line, total_lam)
        side = row.get("side", "").strip().lower()
        if side not in CORNERS_ALLOWED_SIDES:
            continue
        model_prob = prob_over if side == "over" else 1.0 - prob_over
        edge = (model_prob * row["odds"]) - 1.0
        if edge < args.corners_min_edge:
            continue

        match_date = fixture_date.isoformat()
        fx_key = fixture_key(match_date, league, home, away)
        pick_id = "|".join([CORNERS_MODEL, fx_key, row["line_label"], side])
        picks.append({
            "pick_id": pick_id,
            "published_at_utc": fmt_dt(row["captured_at_dt"]),
            "kickoff_utc": fmt_dt(kickoff),
            "match_id": fx_key,
            "match_date": match_date,
            "league": league,
            "match": f"{home} vs {away}",
            "home_team": home,
            "away_team": away,
            "team": "",
            "bookmaker": "Pinnacle",
            "selection": f"{side} {row['line_label']}",
            "line": row["line_label"],
            "side": side,
            "model": CORNERS_MODEL,
            "model_fair_odds": round(fair_odds(model_prob), 6),
            "model_implied_prob": round(model_prob, 6),
            "book_odds": round(row["odds"], 6),
            "edge": round(edge, 6),
            "current_model_would_have_priced": "true",
            "confidence_guard_applied": "false",
            "blocked_reason": "",
            "result": "",
            "pnl_units": "",
        })

    return cap_fixture_volume(picks)


def cap_fixture_volume(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only the strongest research signal per fixture.

    These lanes are monitored like possible future products, so a fixture must
    not publish multiple lines/sides from the same model. If over 8.5 and over
    9.5 both clear the edge threshold, only the higher EV row survives.
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("match_id", ""))].append(row)
    kept: list[dict[str, Any]] = []
    for fixture_rows in grouped.values():
        kept.extend(
            sorted(
                fixture_rows,
                key=lambda item: (
                    float(item.get("edge") or 0.0),
                    float(item.get("model_implied_prob") or 0.0),
                    float(item.get("book_odds") or 0.0),
                ),
                reverse=True,
            )[:MAX_PICKS_PER_FIXTURE]
        )
    return sorted(kept, key=lambda item: (item.get("kickoff_utc", ""), item.get("match", ""), -float(item.get("edge") or 0.0)))


def row_is_open_published(row: dict[str, Any]) -> bool:
    result = str(row.get("result") or "").strip()
    blocked = str(row.get("blocked_reason") or "").strip()
    guarded = str(row.get("confidence_guard_applied") or "").strip().lower() == "true"
    return not result and not blocked and not guarded


def merge_published_ledger(existing_rows: list[dict[str, str]], fresh_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Append/merge new picks without dropping already-published open picks.

    The feed is a publication ledger, not only today's upcoming scanner. If a
    row was published before kickoff and has not settled yet, it must stay in
    the monitor after kickoff. After merging, enforce the product rule that
    only the strongest open EV signal per fixture remains visible.
    """
    merged_by_id: dict[str, dict[str, Any]] = {}
    for row in existing_rows:
        pick_id = str(row.get("pick_id") or "").strip()
        if pick_id:
            merged_by_id[pick_id] = dict(row)
    for row in fresh_rows:
        pick_id = str(row.get("pick_id") or "").strip()
        if pick_id:
            merged_by_id[pick_id] = dict(row)

    grouped_open: dict[str, list[dict[str, Any]]] = defaultdict(list)
    passthrough: list[dict[str, Any]] = []
    for row in merged_by_id.values():
        if row_is_open_published(row):
            grouped_open[str(row.get("match_id", ""))].append(row)
        else:
            passthrough.append(row)

    kept_open: list[dict[str, Any]] = []
    for fixture_rows in grouped_open.values():
        kept_open.extend(
            sorted(
                fixture_rows,
                key=lambda item: (
                    float(item.get("edge") or 0.0),
                    float(item.get("model_implied_prob") or 0.0),
                    float(item.get("book_odds") or 0.0),
                ),
                reverse=True,
            )[:MAX_PICKS_PER_FIXTURE]
        )

    return sorted(
        passthrough + kept_open,
        key=lambda item: (
            item.get("kickoff_utc", ""),
            item.get("match", ""),
            -float(item.get("edge") or 0.0),
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish football research pick feeds")
    parser.add_argument("--team-base", type=Path, default=DEFAULT_TEAM_BASE)
    parser.add_argument("--team-odds", type=Path, default=DEFAULT_TEAM_ODDS)
    parser.add_argument("--team-current-fixtures", type=Path, default=DEFAULT_TEAM_CURRENT_FIXTURES)
    parser.add_argument("--team-allowed", type=Path, default=DEFAULT_TEAM_ALLOWED)
    parser.add_argument("--team-output", type=Path, default=DEFAULT_TEAM_OUT)
    parser.add_argument("--team-min-edge", type=float, default=TEAM_MIN_EDGE)
    parser.add_argument("--corners-pinnacle", type=Path, default=DEFAULT_CORNERS_PINNACLE)
    parser.add_argument("--corners-allowed", type=Path, default=DEFAULT_CORNERS_ALLOWED)
    parser.add_argument("--corners-output", type=Path, default=DEFAULT_CORNERS_OUT)
    parser.add_argument("--corners-min-edge", type=float, default=CORNERS_MIN_EDGE)
    parser.add_argument("--now", default="", help="UTC ISO timestamp override for deterministic tests")
    args = parser.parse_args()

    now = parse_dt(args.now) if args.now else datetime.now(UTC)
    if now is None:
        raise SystemExit(f"Invalid --now value: {args.now}")

    ensure_team_base(args.team_base)
    base_rows = load_csv(args.team_base)
    by_team, by_league = build_base_indexes(base_rows)
    team_picks = publish_team_shots(args, by_team, by_league, base_rows, now)
    corners_picks = publish_corners(args, by_team, by_league, now)
    team_picks = merge_published_ledger(load_csv(args.team_output), team_picks)
    corners_picks = merge_published_ledger(load_csv(args.corners_output), corners_picks)
    write_csv(args.team_output, team_picks)
    write_csv(args.corners_output, corners_picks)
    print(f"Wrote {args.team_output.relative_to(ROOT)} ({len(team_picks)} rows)")
    print(f"Wrote {args.corners_output.relative_to(ROOT)} ({len(corners_picks)} rows)")


if __name__ == "__main__":
    main()
