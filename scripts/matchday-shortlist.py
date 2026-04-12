#!/usr/bin/env python3
"""
Matchday shortlist: identify value bets across corners + shots markets.

This is the daily workflow script. Run it on the morning of a matchday:

  python scripts/matchday-shortlist.py
  python scripts/matchday-shortlist.py --league epl
  python scripts/matchday-shortlist.py --all-leagues --min-edge 0.08
  python scripts/matchday-shortlist.py --side under --lines 8.5,9.5

It will:
  1. Load the corners model predictions for upcoming fixtures
  2. Fetch real-time corner O/U odds from The Odds API
  3. Compare model fair odds vs bookmaker prices
  4. Highlight value bets with edge >= threshold
  5. Apply tiered staking (0.5-2u by edge band; Ligue 1 capped at 0.5u)
  6. Output a clean shortlist for manual betting

Also logs everything to data/shortlist/ for ongoing tracking.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent

# Model imports

import sys
sys.path.insert(0, str(ROOT / "scripts"))

from the_odds_api_client import OddsApiClient, SPORT_KEYS, CORNER_MARKET
from corners_poisson import (  # noqa: E402
    calibrate_prob,
    fair_decimal,
    load_calibration_params,
    match_total_prob_over,
    poisson_pmf,
)


# Constants

DEFAULT_PREDICTIONS = ROOT / "data" / "corners-ou" / "corners-ou-predictions.csv"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "shortlist"
DEFAULT_EDGE_THRESHOLD = 0.10
CALIBRATION_PARAMS_PATH = ROOT / "data" / "corners-ou" / "corners-calibration-params.json"
LIGUE1_MAX_STAKE = 0.5  # DD risk: Ligue 1 backtest max DD ~133u vs ~36u Serie A

# League stake multipliers - applied to tier stake before Ligue 1 cap.
# Based on calibrated backtest (synthetic market, edge >= 5%):
#   Serie A  +16.3% ROI  DD 35.9u   La Liga  +15.5%  DD 45.8u
#   Bundesliga +11.3%     DD 46.0u   EPL +7.2%        DD 75.5u
#   Ligue 1  +6.9%        DD 132.8u
LEAGUE_STAKE_MULTIPLIERS: dict = {
    "serie-a":    1.5,
    "la-liga":    1.25,
    "bundesliga": 1.0,
    "epl":        0.75,
    "ligue-1":    0.75,   # multiplier before LIGUE1_MAX_STAKE cap
}
DEFAULT_LEAGUE_MULTIPLIER = 1.0

STAKE_TIERS = [
    (0.25, 2.0, "MAX"),
    (0.20, 1.5, "HIGH"),
    (0.15, 1.0, "MEDIUM"),
    (0.12, 0.5, "LOW"),
    (0.10, 0.25, "TINY"),  # 10-12% edge: smallest tier, high volume
]

CORNER_LINES = [8.5, 9.5, 10.5, 11.5]
VALUE_BET_FIELDS = [
    "match", "kick_off", "league", "market", "line", "side",
    "model_prob", "model_fair", "bookmaker", "bookie_odds",
    "edge", "stake", "stake_label", "lambda_h", "lambda_a",
]


# (poisson_pmf, match_total_prob_over, fair_decimal, calibrate_prob,
#  load_calibration_params imported from corners_poisson)


# Team name normalization

def _norm(text: str) -> str:
    text = (text or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


TEAM_ALIASES = {
    "wolves": "wolverhampton wanderers",
    "wolverhampton": "wolverhampton wanderers",
    "wolverhampton wanderers": "wolverhampton wanderers",
    "man utd": "man united",
    "manchester utd": "man united",
    "manchester united": "man united",
    "man united": "man united",
    "man city": "manchester city",
    "manchester city": "manchester city",
    "spurs": "tottenham",
    "tottenham hotspur": "tottenham",
    "tottenham": "tottenham",
    "west ham united": "west ham",
    "west ham": "west ham",
    "nott'm forest": "nottingham forest",
    "nottingham forest": "nottingham forest",
    "newcastle utd": "newcastle",
    "newcastle united": "newcastle",
    "newcastle": "newcastle",
    "sheffield utd": "sheffield united",
    "sheffield united": "sheffield united",
    "brighton": "brighton",
    "brighton and hove albion": "brighton",
    "leicester": "leicester",
    "leicester city": "leicester",
    "ipswich": "ipswich",
    "ipswich town": "ipswich",
    "ac milan": "milan",
    "milan": "milan",
    "inter": "inter",
    "inter milan": "inter",
    "internazionale": "inter",
    "as roma": "roma",
    "roma": "roma",
    "napoli": "napoli",
    "ssc napoli": "napoli",
    "juventus": "juventus",
    "lazio": "lazio",
    "ss lazio": "lazio",
    "atalanta": "atalanta",
    "atalanta bc": "atalanta",
    "fiorentina": "fiorentina",
    "acf fiorentina": "fiorentina",
    "bologna": "bologna",
    "bologna fc": "bologna",
    "torino": "torino",
    "torino fc": "torino",
    "hellas verona": "verona",
    "verona": "verona",
    "paris saint germain": "paris sg",
    "paris saint-germain": "paris sg",
    "psg": "paris sg",
    "paris sg": "paris sg",
    "olympique marseille": "marseille",
    "marseille": "marseille",
    "olympique lyonnais": "lyon",
    "lyon": "lyon",
    "as monaco": "monaco",
    "monaco": "monaco",
    "atletico madrid": "ath madrid",
    "ath madrid": "ath madrid",
    "atletico de madrid": "ath madrid",
    "athletic bilbao": "ath bilbao",
    "ath bilbao": "ath bilbao",
    "real betis": "betis",
    "betis": "betis",
    "real sociedad": "sociedad",
    "sociedad": "sociedad",
    "villarreal": "villarreal",
    "villarreal cf": "villarreal",
    "celta vigo": "celta",
    "celta": "celta",
    "bayern munich": "bayern munich",
    "fc bayern munich": "bayern munich",
    "bayern munchen": "bayern munich",
    "borussia dortmund": "dortmund",
    "dortmund": "dortmund",
    "rb leipzig": "leipzig",
    "rasenballsport leipzig": "leipzig",
    "leipzig": "leipzig",
    "bayer leverkusen": "leverkusen",
    "leverkusen": "leverkusen",
    "eintracht frankfurt": "ein frankfurt",
    "ein frankfurt": "ein frankfurt",
    "vfl wolfsburg": "wolfsburg",
    "wolfsburg": "wolfsburg",
    # Bundesliga additional
    "1 fc heidenheim": "heidenheim",
    "heidenheim": "heidenheim",
    "1 fc koln": "fc koln",
    "fc koln": "fc koln",
    "borussia monchengladbach": "m gladbach",
    "m gladbach": "m gladbach",
    "fc st pauli": "st pauli",
    "st pauli": "st pauli",
    "fsv mainz 05": "mainz",
    "mainz": "mainz",
    "hamburger sv": "hamburg",
    "hamburg": "hamburg",
    "sc freiburg": "freiburg",
    "freiburg": "freiburg",
    "tsg hoffenheim": "hoffenheim",
    "hoffenheim": "hoffenheim",
    "vfb stuttgart": "stuttgart",
    "stuttgart": "stuttgart",
    # EPL additional
    "leeds united": "leeds",
    "leeds": "leeds",
    "nottingham forest": "nott m forest",
    "nott m forest": "nott m forest",
    "nott'm forest": "nott m forest",
    # La Liga additional
    "ca osasuna": "osasuna",
    "osasuna": "osasuna",
    "elche cf": "elche",
    "elche": "elche",
    "espanyol": "espanol",
    "espanol": "espanol",
    "rayo vallecano": "vallecano",
    "vallecano": "vallecano",
    # Ligue 1 additional
    "rc lens": "lens",
    "lens": "lens",
}


def normalize_team(name: str) -> str:
    normed = _norm(name)
    return TEAM_ALIASES.get(normed, normed)


# Corners model: compute lambdas for a fixture

ROLLING_WINDOW = 20
MIN_MATCHES = 6
DECAY = 0.93
HOME_BOOST = 1.08

LEAGUE_AVG_CORNERS = {
    "epl": 5.212, "serie-a": 5.002, "la-liga": 4.778,
    "bundesliga": 4.818, "ligue-1": 4.760,
}
DEFAULT_AVG = 4.92


class TeamCornerStats:
    def __init__(self) -> None:
        self.won: List[float] = []
        self.conceded: List[float] = []

    def add(self, won: float, conceded: float) -> None:
        self.won.append(won)
        self.conceded.append(conceded)

    def _ema(self, history: List[float]) -> Optional[float]:
        recent = history[-ROLLING_WINDOW:]
        if len(recent) < MIN_MATCHES:
            return None
        total = 0.0
        w_sum = 0.0
        for i, val in enumerate(recent):
            w = DECAY ** (len(recent) - 1 - i)
            total += val * w
            w_sum += w
        return total / w_sum if w_sum > 0 else None

    @property
    def n_matches(self) -> int:
        return len(self.won)

    def avg_won(self) -> Optional[float]:
        return self._ema(self.won)

    def avg_conceded(self) -> Optional[float]:
        return self._ema(self.conceded)


def load_historical_corner_stats() -> Dict[str, TeamCornerStats]:
    """Load all historical matches and build team corner stats."""
    import csv as _csv
    stats: Dict[str, TeamCornerStats] = defaultdict(TeamCornerStats)
    hist_path = ROOT / "data" / "team-shots" / "historical" / "all-historical-matches.csv"
    if not hist_path.exists():
        return stats

    with open(hist_path, "r", encoding="utf-8") as fh:
        reader = _csv.DictReader(fh)
        rows = []
        for row in reader:
            hc = (row.get("HC") or "").strip()
            ac = (row.get("AC") or "").strip()
            if not hc or not ac:
                continue
            rows.append(row)
        rows.sort(key=lambda r: r.get("Date", ""))

        for row in rows:
            league = row.get("league", "")
            home = row.get("HomeTeam", "") or row.get("home_team", "")
            away = row.get("AwayTeam", "") or row.get("away_team", "")
            hc = int(row["HC"])
            ac = int(row["AC"])
            h_key = f"{league}:{normalize_team(home)}"
            a_key = f"{league}:{normalize_team(away)}"
            stats[h_key].add(hc, ac)
            stats[a_key].add(ac, hc)
    return stats


def predict_corners_lambda(
    team_stats: TeamCornerStats, opp_stats: TeamCornerStats,
    league_avg: float, is_home: bool,
) -> Optional[float]:
    attack = team_stats.avg_won()
    defence = opp_stats.avg_conceded()
    if attack is None or defence is None:
        return None
    avg = league_avg if league_avg > 0 else DEFAULT_AVG
    venue = HOME_BOOST if is_home else (1.0 / HOME_BOOST)
    lam = avg * (attack / avg) * (defence / avg) * venue
    return max(1.0, min(lam, 15.0))


# Staking (tiered, 0.5-2u)

def tier_stake(edge: float) -> Tuple[float, str]:
    """Map edge to stake tier. Returns (stake_units, label)."""
    for threshold, stake, label in STAKE_TIERS:
        if edge >= threshold:
            return stake, label
    return 0.0, ""


# Value detection

def find_value_bets(
    home_team: str, away_team: str, league: str,
    h_lam: float, a_lam: float,
    bookmaker_lines: List[dict],
    min_edge: float = DEFAULT_EDGE_THRESHOLD,
    cal_params: Optional[Dict[str, Tuple[float, float]]] = None,
    allowed_sides: "frozenset[str]" = frozenset({"over", "under"}),
    allowed_lines: Optional["frozenset[float]"] = None,
    kick_off: str = "",
) -> List[dict]:
    """
    Compare model probabilities against real bookmaker lines.

    If cal_params is provided, applies per-line Platt scaling to the raw
    Poisson probability before computing edge and stake tier.  The raw
    probability is still logged as model_prob_raw for diagnostics.

    Ligue 1 stakes are capped at LIGUE1_MAX_STAKE regardless of edge tier
    (backtest path risk: max DD ~313u vs ~123u for EPL at same edge thresholds).
    """
    value_bets = []
    # Derive lines to evaluate from whatever the bookmaker actually offers.
    # This covers all lines Pinnacle posts (e.g. 7.5, 8.0, 9.0, 12.5, 15.5...)
    # rather than a hardcoded subset.
    available_bm_lines = sorted({round(bl["line"], 2) for bl in bookmaker_lines})
    lines_to_check = (
        [l for l in available_bm_lines if l in allowed_lines]
        if allowed_lines is not None
        else available_bm_lines
    )

    for line_val in lines_to_check:
        p_over_raw = match_total_prob_over(line_val, h_lam, a_lam)
        if cal_params is not None:
            ab = cal_params.get(str(line_val))
            p_over = calibrate_prob(p_over_raw, ab[0], ab[1]) if ab else p_over_raw
        else:
            p_over = p_over_raw
        p_under = 1.0 - p_over

        for bl in bookmaker_lines:
            if abs(bl["line"] - line_val) > 0.01:
                continue
            bm = bl["bookmaker"]
            over_odds = bl["over_odds"]
            under_odds = bl["under_odds"]

            implied_over = 1.0 / over_odds if over_odds > 1 else 1.0
            implied_under = 1.0 / under_odds if under_odds > 1 else 1.0

            edge_over = p_over - implied_over
            edge_under = p_under - implied_under

            league_mult = LEAGUE_STAKE_MULTIPLIERS.get(league, DEFAULT_LEAGUE_MULTIPLIER)

            if "over" in allowed_sides and edge_over >= min_edge:
                stake_u, stake_label = tier_stake(edge_over)
                stake_u = round(stake_u * league_mult, 2)
                if league == "ligue-1":
                    stake_u = min(stake_u, LIGUE1_MAX_STAKE)
                value_bets.append({
                    "match": f"{home_team} vs {away_team}",
                    "kick_off": kick_off,
                    "league": league,
                    "market": "corners",
                    "line": line_val,
                    "side": "over",
                    "model_prob": round(p_over, 4),
                    "model_prob_raw": round(p_over_raw, 4),
                    "model_fair": fair_decimal(p_over),
                    "bookmaker": bm,
                    "bookie_odds": over_odds,
                    "edge": round(edge_over, 4),
                    "stake": stake_u,
                    "stake_label": stake_label,
                    "lambda_h": round(h_lam, 2),
                    "lambda_a": round(a_lam, 2),
                })

            if "under" in allowed_sides and edge_under >= min_edge:
                stake_u, stake_label = tier_stake(edge_under)
                stake_u = round(stake_u * league_mult, 2)
                if league == "ligue-1":
                    stake_u = min(stake_u, LIGUE1_MAX_STAKE)
                value_bets.append({
                    "match": f"{home_team} vs {away_team}",
                    "kick_off": kick_off,
                    "league": league,
                    "market": "corners",
                    "line": line_val,
                    "side": "under",
                    "model_prob": round(p_under, 4),
                    "model_prob_raw": round(1.0 - p_over_raw, 4),
                    "model_fair": fair_decimal(p_under),
                    "bookmaker": bm,
                    "bookie_odds": under_odds,
                    "edge": round(edge_under, 4),
                    "stake": stake_u,
                    "stake_label": stake_label,
                    "lambda_h": round(h_lam, 2),
                    "lambda_a": round(a_lam, 2),
                })

    return value_bets


# Pretty output

def format_shortlist(
    value_bets: List[dict],
    credits_remaining: Optional[int] = None,
) -> str:
    lines: List[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append("=" * 78)
    lines.append(f"  MATCHDAY SHORTLIST -- {now}")
    lines.append("=" * 78)

    if credits_remaining is not None:
        lines.append(f"  Odds API credits remaining: {credits_remaining}")
    lines.append("")

    if not value_bets:
        lines.append("  No value bets found above the edge threshold.")
        lines.append("=" * 78)
        return "\n".join(lines)

    sorted_bets = sorted(value_bets, key=lambda b: -b["edge"])

    lines.append(f"  {'Match':<30s}  {'Line':>6s}  {'Side':>5s}  {'Fair':>6s}  {'Ref':>6s}  {'Edge':>6s}  {'Stake':>6s}  {'Tier':>6s}")
    lines.append(f"  {'-'*30}  {'-'*6}  {'-'*5}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*6}")

    total_stake = 0.0
    for b in sorted_bets:
        match_name = b["match"][:30]
        lines.append(
            f"  {match_name:<30s}  {b['line']:>5.1f}  {b['side']:>5s}  "
            f"{b['model_fair']:>6.2f}  {b['bookie_odds']:>6.2f}  "
            f"{b['edge']:>+5.1%}  {b['stake']:>5.1f}u  {b['stake_label']:>6s}"
        )
        total_stake += b["stake"]

    lines.append("")
    lines.append(f"  Total bets: {len(sorted_bets)}  |  Total stake: {total_stake:.1f}u")

    by_league = defaultdict(list)
    for b in sorted_bets:
        by_league[b["league"]].append(b)
    if len(by_league) > 1:
        lines.append("")
        for lg in sorted(by_league):
            n = len(by_league[lg])
            avg_edge = sum(b["edge"] for b in by_league[lg]) / n
            lines.append(f"    {lg}: {n} bets, avg edge {avg_edge:+.1%}")

    lines.append("")
    lines.append("  Ref odds = Pinnacle (sharpest market). Bet on bet365/Paddy Power if similar or better.")
    lines.append("  Base tiers: 0.25u (10-12%) | 0.5u (12-15%) | 1u (15-20%) | 1.5u (20-25%) | 2u (25%+)")
    lines.append("  League multipliers: Serie A x1.5 | La Liga x1.25 | Bundesliga x1.0 | EPL x0.75 | Ligue 1 x0.75 (cap 0.5u)")
    lines.append("=" * 78)
    return "\n".join(lines)


# Main

def main() -> None:
    parser = argparse.ArgumentParser(description="Matchday value shortlist")
    parser.add_argument("--league", choices=sorted(SPORT_KEYS), default=None,
                        help="Single league to check")
    parser.add_argument("--all-leagues", action="store_true",
                        help="Check all Big 5 leagues")
    parser.add_argument("--min-edge", type=float, default=DEFAULT_EDGE_THRESHOLD,
                        help=f"Min edge to qualify (default {DEFAULT_EDGE_THRESHOLD})")
    parser.add_argument("--side", choices=["over", "under", "both"], default="both",
                        help="Only emit over, under, or both sides (default: both)")
    parser.add_argument("--lines", default="",
                        help="Comma-separated corner lines to include, e.g. 8.5,9.5 (default: all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip API calls, use model only")
    parser.add_argument("--regions", default="eu",
                        help="Bookmaker regions (default eu for Pinnacle; use uk,eu for more bookies but 2x credits)")
    parser.add_argument("--days-ahead", type=int, default=7,
                        help="Only fetch odds for matches within N days (saves credits)")
    args = parser.parse_args()

    leagues = list(SPORT_KEYS.keys()) if args.all_leagues else [args.league or "epl"]

    allowed_sides: frozenset = (
        frozenset({"over", "under"}) if args.side == "both" else frozenset({args.side})
    )
    allowed_lines: Optional[frozenset] = None
    if args.lines:
        try:
            allowed_lines = frozenset(
                float(l.strip()) for l in args.lines.split(",") if l.strip()
            )
        except ValueError:
            print(f"  [warn] --lines value '{args.lines}' could not be parsed; using all lines")

    print("Loading historical corner stats...")
    team_stats = load_historical_corner_stats()
    total_teams = len(team_stats)
    print(f"  {total_teams} team histories loaded")

    print("\nLoading calibration params...")
    cal_params = load_calibration_params(CALIBRATION_PARAMS_PATH)

    if args.dry_run:
        print("\n[DRY RUN] Skipping API calls. Showing model predictions only.\n")
        _dry_run_shortlist(leagues, team_stats)
        return

    print("\nConnecting to The Odds API...")
    try:
        client = OddsApiClient()
    except RuntimeError as e:
        print(f"  ERROR: {e}")
        print("\n  To set up: sign up free at https://the-odds-api.com")
        print("  Then add to .env.local:  THE_ODDS_API_KEY=your_key_here")
        return

    all_value_bets: List[dict] = []
    all_signals: List[dict] = []

    for league in leagues:
        sport_key = SPORT_KEYS[league]
        league_avg = LEAGUE_AVG_CORNERS.get(league, DEFAULT_AVG)
        print(f"\n--- {league.upper()} ---")

        events = client.get_upcoming_events(sport_key)

        cutoff = datetime.now(timezone.utc) + timedelta(days=args.days_ahead)
        nearby = []
        for ev in events:
            ko = ev.get("commence_time", "")
            try:
                ko_dt = datetime.fromisoformat(ko.replace("Z", "+00:00"))
                if ko_dt <= cutoff:
                    nearby.append(ev)
            except (ValueError, TypeError):
                nearby.append(ev)
        print(f"  {len(events)} upcoming, {len(nearby)} within {args.days_ahead} days")

        for event in nearby:
            home = event.get("home_team", "")
            away = event.get("away_team", "")
            event_id = event.get("id", "")
            kick_off = event.get("commence_time", "")

            h_key = f"{league}:{normalize_team(home)}"
            a_key = f"{league}:{normalize_team(away)}"
            h_stats = team_stats.get(h_key)
            a_stats = team_stats.get(a_key)

            if not h_stats or not a_stats:
                print(f"  {home} vs {away}: no historical corner data, skipping")
                continue

            h_lam = predict_corners_lambda(h_stats, a_stats, league_avg, is_home=True)
            a_lam = predict_corners_lambda(a_stats, h_stats, league_avg, is_home=False)
            if h_lam is None or a_lam is None:
                print(f"  {home} vs {away}: insufficient matches for EMA, skipping")
                continue

            total_lam = h_lam + a_lam
            print(f"  {home} vs {away}: lam_H={h_lam:.2f} lam_A={a_lam:.2f} total={total_lam:.2f}")

            try:
                event_odds = client.get_event_corner_odds(event_id, sport_key, regions=args.regions)
                bm_lines = OddsApiClient.extract_corner_lines(event_odds)
                print(f"    {len(bm_lines)} corner lines from {len(set(l['bookmaker'] for l in bm_lines))} bookmakers")
            except Exception as e:
                print(f"    No corner odds available: {e}")
                bm_lines = []

            if bm_lines:
                value = find_value_bets(
                    home, away, league, h_lam, a_lam, bm_lines,
                    min_edge=args.min_edge,
                    cal_params=cal_params,
                    allowed_sides=allowed_sides,
                    allowed_lines=allowed_lines,
                    kick_off=kick_off,
                )
                all_value_bets.extend(value)
                if value:
                    print(f"    >>> {len(value)} VALUE BETS FOUND <<<")

            signal = {
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "kick_off": kick_off,
                "league": league,
                "home_team": home,
                "away_team": away,
                "lambda_home": round(h_lam, 3),
                "lambda_away": round(a_lam, 3),
                "lambda_total": round(total_lam, 3),
                "home_matches": h_stats.n_matches,
                "away_matches": a_stats.n_matches,
            }
            for line_val in CORNER_LINES:
                p_over = match_total_prob_over(line_val, h_lam, a_lam)
                signal[f"p_over_{line_val}"] = round(p_over, 4)
                signal[f"fair_over_{line_val}"] = fair_decimal(p_over)
                signal[f"fair_under_{line_val}"] = fair_decimal(1.0 - p_over)
            all_signals.append(signal)

    # One bet per match: keep only the highest-edge qualifying bet.
    # Backing multiple correlated lines on the same fixture dilutes bankroll
    # with correlated outcomes - take the single best opportunity per game.
    best_by_match: dict[str, dict] = {}
    for bet in all_value_bets:
        key = f'{bet.get("league", "")}|{bet.get("match", "")}|{bet.get("kick_off", "")}'
        if key not in best_by_match or bet["edge"] > best_by_match[key]["edge"]:
            best_by_match[key] = bet
    all_value_bets = sorted(best_by_match.values(), key=lambda b: -b["edge"])

    shortlist = format_shortlist(all_value_bets, client.get_credits_remaining())
    print("\n" + shortlist)

    output_dir = DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    shortlist_path = output_dir / f"shortlist-{today}.txt"
    with open(shortlist_path, "w", encoding="utf-8") as fh:
        fh.write(shortlist)
    print(f"Shortlist saved to {shortlist_path}")

    bets_path = output_dir / f"value-bets-{today}.csv"
    bet_fields = list(all_value_bets[0].keys()) if all_value_bets else VALUE_BET_FIELDS
    with open(bets_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=bet_fields)
        writer.writeheader()
        if all_value_bets:
            writer.writerows(all_value_bets)
    if all_value_bets:
        print(f"Value bets CSV saved to {bets_path}")
    else:
        print(f"Value bets CSV saved empty to {bets_path}")

    if all_signals:
        signals_path = output_dir / f"signals-{today}.csv"
        fields = list(all_signals[0].keys())
        with open(signals_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            writer.writerows(all_signals)
        print(f"Signals CSV saved to {signals_path}")


def _dry_run_shortlist(leagues: List[str], team_stats: Dict[str, TeamCornerStats]) -> None:
    """Show model predictions without API calls."""
    for league in leagues:
        prefix = f"{league}:"
        teams_in_league = [k for k in team_stats if k.startswith(prefix)]
        print(f"\n{league.upper()} -- {len(teams_in_league)} teams tracked")

        for team_key in sorted(teams_in_league):
            ts = team_stats[team_key]
            team_name = team_key.split(":", 1)[1]
            won = ts.avg_won()
            conc = ts.avg_conceded()
            if won is None or conc is None:
                continue
            print(f"  {team_name:<25s}  won={won:.2f}  conc={conc:.2f}  n={ts.n_matches}")


if __name__ == "__main__":
    main()
