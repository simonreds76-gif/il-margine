#!/usr/bin/env python3
"""
Build team total shots estimates for upcoming fixtures (Big 5).

Uses the same rolling EMA + Poisson logic as team-shots-model.py, with team
names aligned to historical data via the same normalisation as matchday-shortlist.

Outputs:
  data/team-shots/team-shots-upcoming.csv   â€” per-match model output
  data/team-shots/team-shots-scanner.csv    â€” scanner: one row per team+line+side
                                              joined with latest inbox odds

Usage:
  python scripts/team_shots_upcoming.py
  python scripts/team_shots_upcoming.py --days-ahead 7
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from settlement_utils import normalize_team_name
from team_shots_probability import fair_odds, prob_over as surface_prob_over

DEFAULT_OUT     = ROOT / "data" / "team-shots" / "team-shots-upcoming.csv"
DEFAULT_CAL     = ROOT / "data" / "team-shots" / "team-shots-calibration-params.json"
INBOX_DIR       = ROOT / "data" / "team-shots" / "inbox"
SCANNER_OUT     = ROOT / "data" / "team-shots" / "team-shots-scanner.csv"

# Lines exported in the upcoming file â€” matches the lines books actually quote
DISPLAY_LINES = [8.5, 9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5, 17.5, 19.5, 20.5]

SUPPORTED_LIVE_LEAGUES = {"epl", "serie-a", "la-liga", "bundesliga"}
INBOX_COMPETITION_TO_LEAGUE = {
    "premier league": "epl",
    "serie a": "serie-a",
    "la liga": "la-liga",
    "bundesliga": "bundesliga",
    "ligue 1": "ligue-1",
}

SHADOW_THRESHOLD = 0.12
ACTION_THRESHOLD = 0.12
CONFLICT_SKIP_THRESHOLD = 0.12
ALIGNED_MAX_DIVERGENCE = 0.15
DIVERGENT_MAX_DIVERGENCE = 0.30

SCANNER_FIELDS = [
    "kickoff_iso", "league", "home_team", "away_team", "team", "venue",
    "line", "side", "model_prob", "model_fair", "book_odds", "bookmaker",
    "edge", "captured_at",
    "lambda_venue", "lambda_recent", "divergence", "consensus",
    "effective_stake", "preferred",
]


def inclusive_days_cutoff(days_ahead: int) -> datetime:
    target_day = datetime.now(timezone.utc).date() + timedelta(days=max(days_ahead, 0))
    return datetime.combine(target_day, datetime.max.time(), tzinfo=timezone.utc)


# â”€â”€ Calibration helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _logit(p: float) -> float:
    p = max(1e-7, min(1.0 - 1e-7, p))
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    if x >= 0.0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)


def _calibrate(p_raw: float, a: float, b: float) -> float:
    return _sigmoid(a * _logit(p_raw) + b)


def _load_cal(path: Path) -> Dict[str, Tuple[float, float]]:
    """Load Platt calibration params; returns {} if file absent."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return {k: (float(v["a"]), float(v["b"])) for k, v in data.get("lines", {}).items()}


# â”€â”€ Team name normalisation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _norm_competition(text: str) -> str:
    nfkd = unicodedata.normalize("NFD", (text or "").lower())
    ascii_only = "".join(ch for ch in nfkd if unicodedata.category(ch) != "Mn")
    cleaned = re.sub(r"[^\w\s]", " ", ascii_only)
    return " ".join(cleaned.split())


# â”€â”€ Inbox odds loader â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _load_inbox_odds(inbox_dir: Path) -> Dict[Tuple, dict]:
    """
    Read all inbox CSVs; keep the most-recent capture for each
    (date, norm_home, norm_away, norm_team, line, side, bookmaker).
    """
    keyed: Dict[Tuple, dict] = {}
    if not inbox_dir.exists():
        return keyed
    for fpath in sorted(inbox_dir.glob("*.csv")):
        with open(fpath, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                key: Tuple = (
                    (row.get("match_date") or "")[:10],
                    normalize_team_name(row.get("home_team") or ""),
                    normalize_team_name(row.get("away_team") or ""),
                    normalize_team_name(row.get("team") or ""),
                    str(row.get("line") or ""),
                    (row.get("side") or "").strip().lower(),
                    (row.get("bookmaker") or "").strip(),
                )
                captured = row.get("captured_at") or ""
                existing = keyed.get(key)
                if existing is None or captured >= (existing.get("captured_at") or ""):
                    keyed[key] = row
    return keyed


def _stake_for_edge(edge: float) -> float:
    if edge >= 0.25:
        return 2.0
    if edge >= 0.20:
        return 1.5
    if edge >= 0.16:
        return 1.0
    if edge >= 0.12:
        return 0.5
    return 0.0


def _downgrade_one_band(stake_units: float) -> float:
    if stake_units >= 2.0:
        return 1.5
    if stake_units >= 1.5:
        return 1.0
    if stake_units >= 1.0:
        return 0.5
    if stake_units >= 0.5:
        return 0.5
    return 0.0


def _recent_consensus(lam_venue: float, lam_recent: float, recent_is_genuine: bool) -> Tuple[float, str]:
    if not recent_is_genuine or lam_venue <= 0:
        return 0.0, "aligned"

    divergence = abs(lam_recent - lam_venue) / lam_venue
    if divergence <= ALIGNED_MAX_DIVERGENCE:
        return divergence, "aligned"
    if divergence <= DIVERGENT_MAX_DIVERGENCE:
        return divergence, "divergent"
    return divergence, "conflict"


def _effective_stake(
    edge: float,
    consensus: str,
    side: str,
    lambda_venue: float,
    lambda_recent: float,
) -> float:
    base_stake = _stake_for_edge(edge)
    if base_stake <= 0:
        return 0.0
    if side == "under" and lambda_recent > 0 and lambda_venue > lambda_recent * 1.10:
        return 0.0
    if consensus == "aligned":
        return base_stake
    if consensus == "divergent":
        return _downgrade_one_band(base_stake)
    if edge < CONFLICT_SKIP_THRESHOLD:
        return 0.0
    return _downgrade_one_band(base_stake)


def _build_scanner(
    upcoming_rows: List[Dict[str, Any]],
    inbox_index: Dict[Tuple, dict],
) -> List[Dict[str, Any]]:
    """
    For every upcoming match row, walk all DISPLAY_LINES Ã— {over, under} and
    look up the most recent bookmaker price from the inbox index.
    Returns one scanner row per team Ã— line Ã— side where odds exist.
    """
    scanner: List[Dict[str, Any]] = []

    for row in upcoming_rows:
        kickoff = row.get("kickoff_iso") or ""
        match_date = kickoff[:10]
        league = row.get("league") or ""
        home_raw = row.get("home_team") or ""
        away_raw = row.get("away_team") or ""
        norm_home = normalize_team_name(home_raw)
        norm_away = normalize_team_name(away_raw)

        for venue, team_raw in (("home", home_raw), ("away", away_raw)):
            norm_team = normalize_team_name(team_raw)
            consensus = str(row.get(f"{venue}_consensus") or "aligned").strip().lower() or "aligned"
            divergence = float(row.get(f"{venue}_divergence") or 0.0)
            lambda_venue = float(row.get(f"{venue}_lambda_venue") or row.get(f"{venue}_lambda") or 0.0)
            lambda_recent = float(row.get(f"{venue}_lambda_recent") or lambda_venue or 0.0)

            for line in DISPLAY_LINES:
                line_str = f"{line:.1f}"
                model_p_over = row.get(f"{venue}_p_over_{line}")
                if model_p_over is None or model_p_over == "":
                    continue
                model_p_over = float(model_p_over)

                for side in ("over", "under"):
                    model_prob = model_p_over if side == "over" else 1.0 - model_p_over
                    if model_prob <= 0:
                        continue
                    model_fair = round(1.0 / model_prob, 3)

                    # Look up inbox odds â€” try all bookmakers for this line+side
                    best_row: Optional[dict] = None
                    for bk_key, odds_row in inbox_index.items():
                        if (
                            bk_key[0] == match_date
                            and bk_key[1] == norm_home
                            and bk_key[2] == norm_away
                            and bk_key[3] == norm_team
                            and bk_key[4] == line_str
                            and bk_key[5] == side
                        ):
                            if best_row is None or float(odds_row.get("odds_decimal") or 0) > float(best_row.get("odds_decimal") or 0):
                                best_row = odds_row

                    if best_row is None:
                        continue

                    book_odds = float(best_row.get("odds_decimal") or 0)
                    if book_odds <= 1.0:
                        continue

                    edge = round(model_prob * book_odds - 1.0, 4)
                    effective_stake = _effective_stake(
                        edge,
                        consensus,
                        side,
                        lambda_venue,
                        lambda_recent,
                    )
                    preferred = (
                        side == "under"
                        and edge >= ACTION_THRESHOLD
                        and effective_stake > 0
                        and consensus == "aligned"
                    )

                    scanner.append({
                        "kickoff_iso": kickoff,
                        "league": league,
                        "home_team": home_raw,
                        "away_team": away_raw,
                        "team": team_raw,
                        "venue": venue,
                        "line": line,
                        "side": side,
                        "model_prob": round(model_prob, 4),
                        "model_fair": model_fair,
                        "book_odds": round(book_odds, 3),
                        "bookmaker": best_row.get("bookmaker") or "",
                        "edge": edge,
                        "captured_at": best_row.get("captured_at") or "",
                        "lambda_venue": round(lambda_venue, 2),
                        "lambda_recent": round(lambda_recent, 2),
                        "divergence": round(divergence, 4),
                        "consensus": consensus,
                        "effective_stake": round(effective_stake, 1),
                        "preferred": preferred,
                    })

    # Preferred under signals first; suppressed conflict rows sink to the bottom.
    scanner.sort(
        key=lambda r: (
            1 if float(r.get("effective_stake") or 0.0) <= 0 else 0,
            0 if bool(r.get("preferred")) else 1,
            -float(r["edge"]),
            r.get("kickoff_iso") or "",
        )
    )
    return scanner


def _league_key_from_competition(competition: str) -> Optional[str]:
    comp_norm = _norm_competition(competition)
    if not comp_norm:
        return None
    return INBOX_COMPETITION_TO_LEAGUE.get(comp_norm)


def _load_upcoming_events_from_inbox(
    inbox_index: Dict[Tuple, dict],
    cutoff: datetime,
) -> List[Dict[str, str]]:
    now = datetime.now(timezone.utc)
    events: Dict[Tuple[str, str, str, str], Dict[str, str]] = {}

    for odds_row in inbox_index.values():
        league = _league_key_from_competition(str(odds_row.get("competition") or ""))
        if league not in SUPPORTED_LIVE_LEAGUES:
            continue

        kickoff_iso = str(odds_row.get("kickoff_at") or "").strip()
        if not kickoff_iso:
            continue
        try:
            kickoff_dt = datetime.fromisoformat(kickoff_iso.replace("Z", "+00:00"))
        except ValueError:
            continue
        if kickoff_dt > cutoff:
            continue
        if kickoff_dt < now - timedelta(hours=6):
            continue

        home_team = str(odds_row.get("home_team") or "").strip()
        away_team = str(odds_row.get("away_team") or "").strip()
        if not home_team or not away_team:
            continue

        event_key = (league, kickoff_iso, home_team, away_team)
        events[event_key] = {
            "league": league,
            "commence_time": kickoff_iso,
            "home_team": home_team,
            "away_team": away_team,
        }

    return sorted(
        events.values(),
        key=lambda row: (row.get("commence_time") or "", row.get("league") or ""),
    )


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    parser = argparse.ArgumentParser(description="Upcoming team shots estimates (Big 5)")
    parser.add_argument("--days-ahead", type=int, default=10)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--scanner", type=Path, default=SCANNER_OUT)
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CAL)
    parser.add_argument(
        "--prob-surface",
        choices=("venue_poisson", "lambda_shots_nb"),
        default="venue_poisson",
        help="Probability surface for upcoming O/U prices. Default keeps current production.",
    )
    parser.add_argument("--nb-alpha", type=float, default=0.25)
    parser.add_argument("--no-calibration", action="store_true")
    args = parser.parse_args()

    tsm = _load_module("team_shots_model", ROOT / "scripts" / "team-shots-model.py")

    cal: Dict[str, Tuple[float, float]] = {}
    if not args.no_calibration:
        cal = _load_cal(args.calibration)
        if cal:
            print(f"Calibration params loaded from {args.calibration} (lines: {', '.join(sorted(cal))})")
        else:
            print("No calibration params found - using raw Poisson probabilities")

    fbref_path = tsm.DEFAULT_FBREF
    fallback_matches: List[Any] = []
    primary_matches: List[Any] = []
    if tsm.DEFAULT_INPUT.exists():
        fallback_matches = tsm.load_matches(tsm.DEFAULT_INPUT)
    if fbref_path.exists():
        primary_matches = tsm.load_fbref_matches(fbref_path)
    if primary_matches and fallback_matches:
        matches = tsm.merge_match_sources(primary_matches, fallback_matches)
        print(
            f"Merged match history: {len(primary_matches)} xG rows + "
            f"{len(fallback_matches)} fallback rows -> {len(matches)} unique matches"
        )
    elif primary_matches:
        matches = primary_matches
    else:
        matches = fallback_matches

    team_states: Dict[str, tsm.TeamState] = defaultdict(tsm.TeamState)
    league_avgs = tsm.compute_league_avg(matches)

    for m in matches:
        league_avg = league_avgs.get(m.league, tsm.DEFAULT_BASELINE)
        hk = f"{m.league}:{normalize_team_name(m.home_team)}"
        ak = f"{m.league}:{normalize_team_name(m.away_team)}"
        hs = team_states[hk]
        as_ = team_states[ak]
        hs.add_match(
            m.home_shots, m.home_sot, m.away_shots, m.away_sot,
            m.home_corners, m.home_goals, m.away_goals,
            xg=m.home_xg, conc_xg=m.away_xg, is_home=True,
        )
        as_.add_match(
            m.away_shots, m.away_sot, m.home_shots, m.home_sot,
            m.away_corners, m.away_goals, m.home_goals,
            xg=m.away_xg, conc_xg=m.home_xg, is_home=False,
        )

    cutoff = inclusive_days_cutoff(args.days_ahead)
    inbox_index = _load_inbox_odds(INBOX_DIR)
    print(f"Inbox odds loaded: {len(inbox_index)} entries")
    events = _load_upcoming_events_from_inbox(inbox_index, cutoff)
    print(f"Upcoming fixtures inferred from inbox odds: {len(events)}")

    rows_out: List[Dict[str, Any]] = []
    for ev in events:
        league = str(ev.get("league") or "")
        ko = str(ev.get("commence_time") or "")
        home_raw = str(ev.get("home_team") or "")
        away_raw = str(ev.get("away_team") or "")
        hk = f"{league}:{normalize_team_name(home_raw)}"
        ak = f"{league}:{normalize_team_name(away_raw)}"
        h_state = team_states.get(hk)
        a_state = team_states.get(ak)
        league_avg = league_avgs.get(league, tsm.DEFAULT_BASELINE)

        if not h_state or not a_state:
            rows_out.append({
                "league": league,
                "kickoff_iso": ko,
                "home_team": home_raw,
                "away_team": away_raw,
                "home_lambda": "",
                "away_lambda": "",
                "home_consensus": "",
                "away_consensus": "",
                "home_divergence": "",
                "away_divergence": "",
                "note": "no_state",
            })
            continue

        home_res = tsm.predict_lambda(h_state, a_state, league_avg, is_home=True)
        away_res = tsm.predict_lambda(a_state, h_state, league_avg, is_home=False)
        if home_res is None or away_res is None:
            rows_out.append({
                "league": league,
                "kickoff_iso": ko,
                "home_team": home_raw,
                "away_team": away_raw,
                "home_lambda": "",
                "away_lambda": "",
                "home_consensus": "",
                "away_consensus": "",
                "home_divergence": "",
                "away_divergence": "",
                "note": "insufficient_ema",
            })
            continue

        h_lam, _, h_lam_venue, h_lam_recent = home_res
        a_lam, _, a_lam_venue, a_lam_recent = away_res
        home_recent_genuine = len(h_state.home_shots_history) >= tsm.RECENT_MIN
        away_recent_genuine = len(a_state.away_shots_history) >= tsm.RECENT_MIN
        home_divergence, home_consensus = _recent_consensus(
            h_lam_venue,
            h_lam_recent,
            home_recent_genuine,
        )
        away_divergence, away_consensus = _recent_consensus(
            a_lam_venue,
            a_lam_recent,
            away_recent_genuine,
        )
        row: Dict[str, Any] = {
            "league": league,
            "kickoff_iso": ko,
            "home_team": home_raw,
            "away_team": away_raw,
            "home_lambda": round(h_lam, 2),
            "away_lambda": round(a_lam, 2),
            "home_lambda_venue": round(h_lam_venue, 2),
            "away_lambda_venue": round(a_lam_venue, 2),
            "home_lambda_recent": round(h_lam_recent, 2),
            "away_lambda_recent": round(a_lam_recent, 2),
            "home_consensus": home_consensus,
            "away_consensus": away_consensus,
            "home_divergence": round(home_divergence, 4),
            "away_divergence": round(away_divergence, 4),
            "note": "",
        }

        for line in DISPLAY_LINES:
            line_key = f"{line:.1f}"
            if args.prob_surface == "lambda_shots_nb":
                p_h_raw = surface_prob_over(line, h_lam, distribution="negative_binomial", alpha=args.nb_alpha)
                p_a_raw = surface_prob_over(line, a_lam, distribution="negative_binomial", alpha=args.nb_alpha)
            else:
                p_h_raw = tsm.prob_over(line, h_lam_venue)
                p_a_raw = tsm.prob_over(line, a_lam_venue)

            ab = cal.get(line_key)
            if ab:
                p_h = _calibrate(p_h_raw, ab[0], ab[1])
                p_a = _calibrate(p_a_raw, ab[0], ab[1])
            else:
                p_h = p_h_raw
                p_a = p_a_raw

            row[f"home_p_over_{line}"] = round(p_h, 4)
            row[f"home_fair_over_{line}"] = fair_odds(p_h)
            row[f"home_fair_under_{line}"] = fair_odds(1.0 - p_h)
            row[f"away_p_over_{line}"] = round(p_a, 4)
            row[f"away_fair_over_{line}"] = fair_odds(p_a)
            row[f"away_fair_under_{line}"] = fair_odds(1.0 - p_a)

        rows_out.append(row)

    rows_out.sort(key=lambda r: (r.get("kickoff_iso") or "", r.get("league") or ""))

    fields = [
        "league", "kickoff_iso", "home_team", "away_team",
        "home_lambda", "away_lambda",
        "home_lambda_venue", "away_lambda_venue",
        "home_lambda_recent", "away_lambda_recent",
        "home_consensus", "away_consensus",
        "home_divergence", "away_divergence",
        "note",
    ]
    for line in DISPLAY_LINES:
        fields.extend([
            f"home_p_over_{line}", f"home_fair_over_{line}", f"home_fair_under_{line}",
            f"away_p_over_{line}", f"away_fair_over_{line}", f"away_fair_under_{line}",
        ])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows_out)
    print(f"Wrote {len(rows_out)} upcoming rows -> {args.output}")

    match_rows = [r for r in rows_out if r.get("home_lambda") != ""]
    scanner_rows = _build_scanner(match_rows, inbox_index)
    args.scanner.parent.mkdir(parents=True, exist_ok=True)
    with open(args.scanner, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=SCANNER_FIELDS, extrasaction="ignore")
        writer.writeheader()
        if scanner_rows:
            writer.writerows(scanner_rows)

    if scanner_rows:
        positive = sum(1 for r in scanner_rows if r["edge"] > 0)
        print(f"Wrote {len(scanner_rows)} scanner rows ({positive} positive edge) -> {args.scanner}")
    else:
        print(f"Wrote 0 scanner rows -> {args.scanner}")


if __name__ == "__main__":
    main()
