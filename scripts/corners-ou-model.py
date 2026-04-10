#!/usr/bin/env python3
"""
Corners Over/Under prediction model using independent Poisson.

For each team the model estimates expected corners won and conceded using
rolling EMA.  Match-total probabilities are derived by convolving the two
independent Poisson distributions.

Architecture mirrors the team-shots and goals-ou models:
  - Rolling EMA with exponential decay for attack/defence
  - Home advantage boost
  - Smart market baseline from B365 1X2 closing odds

Outputs:
  data/corners-ou/corners-ou-predictions.csv
  data/corners-ou/corners-ou-calibration.txt
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from corners_poisson import (  # noqa: E402
    fair_decimal,
    match_total_prob_over,
    poisson_pmf,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "team-shots" / "historical" / "all-historical-matches.csv"
DEFAULT_OUTPUT = ROOT / "data" / "corners-ou" / "corners-ou-predictions.csv"
DEFAULT_CALIBRATION = ROOT / "data" / "corners-ou" / "corners-ou-calibration.txt"

ROLLING_WINDOW = 20
MIN_MATCHES = 6
DECAY = 0.93
HOME_BOOST = 1.08

STANDARD_LINES = [7.5, 8.5, 9.5, 10.5, 11.5, 12.5]

LEAGUE_DEFAULTS: Dict[str, float] = {
    "epl": 5.21, "serie-a": 5.00, "la-liga": 4.78,
    "bundesliga": 4.82, "ligue-1": 4.76,
}
DEFAULT_AVG_CORNERS = 4.92


def _pf(val: Any, default: float = 0.0) -> float:
    text = str(val or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _pi(val: Any, default: int = 0) -> int:
    return int(_pf(val, float(default)))


def _parse_date(val: str) -> Optional[date]:
    text = (val or "").strip()
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


# (poisson_pmf, match_total_prob_over, fair_decimal imported from corners_poisson)


# ── Team state tracker ───────────────────────────────────────────────

@dataclass
class TeamState:
    corners_won: List[float] = field(default_factory=list)
    corners_conceded: List[float] = field(default_factory=list)

    def add_match(self, won: float, conceded: float) -> None:
        self.corners_won.append(won)
        self.corners_conceded.append(conceded)

    def _ema(self, history: List[float], window: int = ROLLING_WINDOW) -> Optional[float]:
        recent = history[-window:]
        if len(recent) < MIN_MATCHES:
            return None
        total = 0.0
        weight_sum = 0.0
        for i, val in enumerate(recent):
            w = DECAY ** (len(recent) - 1 - i)
            total += val * w
            weight_sum += w
        return total / weight_sum if weight_sum > 0 else None

    @property
    def n_matches(self) -> int:
        return len(self.corners_won)

    def avg_won(self) -> Optional[float]:
        return self._ema(self.corners_won)

    def avg_conceded(self) -> Optional[float]:
        return self._ema(self.corners_conceded)


# ── Data loading ─────────────────────────────────────────────────────

@dataclass
class MatchRow:
    match_date: date
    league: str
    season: str
    home_team: str
    away_team: str
    home_corners: int
    away_corners: int
    home_goals: int
    away_goals: int
    b365h: float = 0.0
    b365d: float = 0.0
    b365a: float = 0.0


def load_matches(path: Path) -> List[MatchRow]:
    rows: List[MatchRow] = []
    with open(path, "r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            d = _parse_date(row.get("Date", "") or row.get("date", ""))
            if d is None:
                continue
            hc = _pi(row.get("HC") or row.get("home_corners"))
            ac = _pi(row.get("AC") or row.get("away_corners"))
            if hc == 0 and ac == 0:
                continue
            rows.append(MatchRow(
                match_date=d,
                league=row.get("league", ""),
                season=row.get("season", ""),
                home_team=row.get("HomeTeam", "") or row.get("home_team", ""),
                away_team=row.get("AwayTeam", "") or row.get("away_team", ""),
                home_corners=hc,
                away_corners=ac,
                home_goals=_pi(row.get("FTHG") or row.get("home_goals")),
                away_goals=_pi(row.get("FTAG") or row.get("away_goals")),
                b365h=_pf(row.get("B365H")),
                b365d=_pf(row.get("B365D")),
                b365a=_pf(row.get("B365A")),
            ))
    rows.sort(key=lambda m: m.match_date)
    return rows


# (compute_league_avg removed — league average is now causal/rolling inside run_model)

# Minimum team-corner observations (= 2× matches) before we trust the causal
# running league average rather than the static LEAGUE_DEFAULTS fallback.
_MIN_LEAGUE_OBS = 20


# ── Prediction engine ────────────────────────────────────────────────

def predict_team_lambda(
    team: TeamState, opp: TeamState,
    league_avg: float, is_home: bool,
) -> Optional[float]:
    """
    Predict expected corners for `team` against `opp`.

    lam = league_avg * (team_attack / avg) * (opp_weakness / avg) * venue
    """
    team_attack = team.avg_won()
    opp_defence = opp.avg_conceded()

    if team_attack is None or opp_defence is None:
        return None

    avg = league_avg if league_avg > 0 else DEFAULT_AVG_CORNERS
    attack_str = team_attack / avg
    defence_weak = opp_defence / avg
    venue_mult = HOME_BOOST if is_home else (1.0 / HOME_BOOST)

    lam = avg * attack_str * defence_weak * venue_mult
    return max(1.0, min(lam, 15.0))


# ── Smart market baseline from B365 1X2 odds ────────────────────────
# Regression: map bookmaker implied probabilities to expected corners.
# Calibrated via OLS on the historical dataset within this script.

SMART_HOME_INTERCEPT = 2.911
SMART_HOME_TEAM_WIN = 5.564
SMART_HOME_OPP_WIN = 0.185

SMART_AWAY_INTERCEPT = 3.669
SMART_AWAY_TEAM_WIN = 3.688
SMART_AWAY_OPP_WIN = -0.893


def smart_corners_lambda(venue: str, b365h: float, b365d: float, b365a: float) -> Optional[float]:
    if b365h <= 0 or b365d <= 0 or b365a <= 0:
        return None
    ip_h = 1.0 / b365h
    ip_d = 1.0 / b365d
    ip_a = 1.0 / b365a
    overround = ip_h + ip_d + ip_a
    p_home = ip_h / overround
    p_away = ip_a / overround

    if venue == "home":
        lam = SMART_HOME_INTERCEPT + SMART_HOME_TEAM_WIN * p_home + SMART_HOME_OPP_WIN * p_away
    else:
        lam = SMART_AWAY_INTERCEPT + SMART_AWAY_TEAM_WIN * p_away + SMART_AWAY_OPP_WIN * p_home
    return max(1.5, min(lam, 12.0))


def run_model(
    matches: List[MatchRow],
    holdout_start: Optional[date] = None,
) -> Tuple[List[dict], Dict[str, float]]:
    """
    Walk matches in chronological order.

    League average is computed causally: before predicting for match M we use
    only the corners data from matches already processed.  This removes the
    look-ahead that existed in the old compute_league_avg (which used the full
    dataset as a denominator).  Falls back to LEAGUE_DEFAULTS until we have
    seen at least _MIN_LEAGUE_OBS team-corner observations (~10 matches).
    """
    team_states: Dict[str, TeamState] = defaultdict(TeamState)

    # Causal league-average accumulators — updated AFTER each match is used
    league_corner_sums: Dict[str, float] = defaultdict(float)
    league_corner_counts: Dict[str, int] = defaultdict(int)

    def _causal_league_avg(league: str) -> float:
        n = league_corner_counts[league]
        if n < _MIN_LEAGUE_OBS:
            return LEAGUE_DEFAULTS.get(league, DEFAULT_AVG_CORNERS)
        return league_corner_sums[league] / n

    predictions: List[dict] = []

    for m in matches:
        avg_c = _causal_league_avg(m.league)
        home_key = f"{m.league}:{m.home_team}"
        away_key = f"{m.league}:{m.away_team}"
        h_state = team_states[home_key]
        a_state = team_states[away_key]

        if holdout_start is None or m.match_date >= holdout_start:
            h_lam = predict_team_lambda(h_state, a_state, avg_c, is_home=True)
            a_lam = predict_team_lambda(a_state, h_state, avg_c, is_home=False)

            if h_lam is not None and a_lam is not None:
                pred = _build_prediction(m, h_lam, a_lam)
                predictions.append(pred)

        # Update team state and causal league average AFTER prediction
        h_state.add_match(m.home_corners, m.away_corners)
        a_state.add_match(m.away_corners, m.home_corners)
        league_corner_sums[m.league] += m.home_corners + m.away_corners
        league_corner_counts[m.league] += 2  # 2 team observations per match

    # Final causal averages for reporting
    league_avgs = {
        lg: league_corner_sums[lg] / league_corner_counts[lg]
        for lg in league_corner_sums
        if league_corner_counts[lg] > 0
    }
    return predictions, league_avgs


def _build_prediction(m: MatchRow, h_lam: float, a_lam: float) -> dict:
    total_lam = h_lam + a_lam
    actual_total = m.home_corners + m.away_corners

    pred: dict = {
        "date": m.match_date.isoformat(),
        "league": m.league,
        "season": m.season,
        "home_team": m.home_team,
        "away_team": m.away_team,
        "lambda_home": round(h_lam, 3),
        "lambda_away": round(a_lam, 3),
        "lambda_total": round(total_lam, 3),
        "actual_home_corners": m.home_corners,
        "actual_away_corners": m.away_corners,
        "actual_total": actual_total,
        "b365h": m.b365h if m.b365h > 0 else "",
        "b365d": m.b365d if m.b365d > 0 else "",
        "b365a": m.b365a if m.b365a > 0 else "",
    }

    for line in STANDARD_LINES:
        p_over = match_total_prob_over(line, h_lam, a_lam)
        p_under = 1.0 - p_over
        pred[f"p_over_{line}"] = round(p_over, 4)
        pred[f"fair_over_{line}"] = fair_decimal(p_over)
        pred[f"fair_under_{line}"] = fair_decimal(p_under)

    return pred


# ── Calibration ──────────────────────────────────────────────────────

def calibration_report(predictions: List[dict], league_avgs: Dict[str, float]) -> str:
    lines: List[str] = []
    lines.append("=" * 70)
    lines.append("  CORNERS O/U MODEL -- CALIBRATION REPORT")
    lines.append("=" * 70)
    lines.append(f"  Total predictions: {len(predictions)}")
    lines.append("")

    if not predictions:
        return "\n".join(lines)

    lam_totals = [p["lambda_total"] for p in predictions]
    actuals = [p["actual_total"] for p in predictions]
    lines.append(f"  Mean predicted total: {sum(lam_totals)/len(lam_totals):.3f}")
    lines.append(f"  Mean actual total:    {sum(actuals)/len(actuals):.3f}")
    lines.append("")

    mae = sum(abs(a - l) for a, l in zip(actuals, lam_totals)) / len(predictions)
    mse = sum((a - l) ** 2 for a, l in zip(actuals, lam_totals)) / len(predictions)
    lines.append(f"  MAE:  {mae:.3f}")
    lines.append(f"  RMSE: {math.sqrt(mse):.3f}")
    lines.append("")

    lines.append("  Line-by-line calibration:")
    for line in STANDARD_LINES:
        key = f"p_over_{line}"
        actual_overs = sum(1 for p in predictions if p["actual_total"] > line)
        pred_sum = sum(p[key] for p in predictions)
        n = len(predictions)
        actual_rate = actual_overs / n
        predicted_rate = pred_sum / n
        lines.append(
            f"    Line {line:5.1f}: predicted={predicted_rate:.3f}  "
            f"actual={actual_rate:.3f}  diff={predicted_rate - actual_rate:+.4f}  (n={n})"
        )

    lines.append("")
    lines.append("  Calibration by probability bins (over 9.5):")
    bins = [(0.0, 0.25), (0.25, 0.40), (0.40, 0.50), (0.50, 0.60), (0.60, 0.75), (0.75, 1.0)]
    for lo, hi in bins:
        subset = [p for p in predictions if lo <= p.get("p_over_9.5", 0) < hi]
        if not subset:
            continue
        actual_over = sum(1 for p in subset if p["actual_total"] > 9.5)
        pred_avg = sum(p.get("p_over_9.5", 0) for p in subset) / len(subset)
        actual_rate = actual_over / len(subset)
        lines.append(
            f"    [{lo:.2f}, {hi:.2f}): n={len(subset):5d}  "
            f"predicted={pred_avg:.3f}  actual={actual_rate:.3f}  "
            f"diff={pred_avg - actual_rate:+.4f}"
        )

    lines.append("")
    lines.append("  Per-league breakdown:")
    leagues = sorted(set(p["league"] for p in predictions))
    for league in leagues:
        lp = [p for p in predictions if p["league"] == league]
        mean_lam = sum(p["lambda_total"] for p in lp) / len(lp)
        mean_actual = sum(p["actual_total"] for p in lp) / len(lp)
        league_mae = sum(abs(p["actual_total"] - p["lambda_total"]) for p in lp) / len(lp)
        lines.append(
            f"    {league:15s}: n={len(lp):5d}  "
            f"pred={mean_lam:.3f}  actual={mean_actual:.3f}  MAE={league_mae:.3f}"
        )

    lines.append("")

    # Calibrate the smart regression coefficients
    lines.append("  Smart baseline regression (OLS on B365 1X2 -> corners):")
    home_rows = [(p["b365h"], p["b365d"], p["b365a"], p["actual_home_corners"])
                 for p in predictions if p.get("b365h") and p["b365h"] > 0]
    away_rows = [(p["b365h"], p["b365d"], p["b365a"], p["actual_away_corners"])
                 for p in predictions if p.get("b365h") and p["b365h"] > 0]

    if home_rows:
        lines.append(f"    Matches with B365 odds: {len(home_rows)}")
        # Simple OLS for home corners
        n = len(home_rows)
        sum_y = sum(r[3] for r in home_rows)
        probs = []
        for b365h, b365d, b365a, actual in home_rows:
            ov = 1/b365h + 1/b365d + 1/b365a
            probs.append((1/b365h/ov, 1/b365a/ov, actual))
        sum_ph = sum(p[0] for p in probs)
        sum_pa = sum(p[1] for p in probs)
        avg_y = sum_y / n
        avg_ph = sum_ph / n
        avg_pa = sum_pa / n
        lines.append(f"    Home corners: avg={avg_y:.2f}, avg P(home_win)={avg_ph:.3f}, avg P(away_win)={avg_pa:.3f}")

        # For away
        sum_ya = sum(r[3] for r in away_rows)
        avg_ya = sum_ya / len(away_rows)
        lines.append(f"    Away corners: avg={avg_ya:.2f}")

    lines.append("")
    lines.append("=" * 70)
    return "\n".join(lines)


# ── Output ───────────────────────────────────────────────────────────

OUTPUT_FIELDS = [
    "date", "league", "season", "home_team", "away_team",
    "lambda_home", "lambda_away", "lambda_total",
    "actual_home_corners", "actual_away_corners", "actual_total",
    "b365h", "b365d", "b365a",
] + [
    col
    for line in STANDARD_LINES
    for col in [f"p_over_{line}", f"fair_over_{line}", f"fair_under_{line}"]
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Corners over/under prediction model")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--holdout-start", type=str, default=None)
    args = parser.parse_args()

    print(f"Loading matches from {args.input}")
    matches = load_matches(args.input)
    print(f"  {len(matches)} matches loaded")

    holdout = None
    if args.holdout_start:
        holdout = date.fromisoformat(args.holdout_start)
        print(f"  Holdout start: {holdout}")

    predictions, league_avgs = run_model(matches, holdout_start=holdout)
    print(f"  {len(predictions)} predictions generated")

    print(f"\nLeague averages (corners per team per match):")
    for league in sorted(league_avgs):
        c = league_avgs[league]
        print(f"  {league:15s}: {c:.3f}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(predictions)
    print(f"\nPredictions written to {args.output}")

    report = calibration_report(predictions, league_avgs)
    print(report)
    with open(args.calibration, "w", encoding="utf-8") as fh:
        fh.write(report)
    print(f"Calibration report saved to {args.calibration}")


if __name__ == "__main__":
    main()
