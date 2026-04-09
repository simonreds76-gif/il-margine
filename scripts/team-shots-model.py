#!/usr/bin/env python3
"""
Team shots prediction model using Poisson regression.

For each team in every match, the model estimates expected total shots (lambda)
using rolling team attack/defence averages with exponential decay, then derives
fair over/under probabilities for standard lines.

Supports two input formats:
  --input (legacy): data/team-shots/historical/all-historical-matches.csv
  --fbref          : data/team-shots/fbref/all-fbref-matches.csv (xG-enriched)

When the FBref file is provided, the model uses xG-based features (rolling xG
attack/defence ratios) blended with shot-volume features for a richer lambda.

Outputs:
  data/team-shots/team-shots-predictions.csv
  data/team-shots/team-shots-calibration.txt
"""

from __future__ import annotations

import argparse
import csv
import math
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "team-shots" / "historical" / "all-historical-matches.csv"
DEFAULT_FBREF = ROOT / "data" / "team-shots" / "fbref" / "all-fbref-matches.csv"
DEFAULT_OUTPUT = ROOT / "data" / "team-shots" / "team-shots-predictions.csv"
DEFAULT_CALIBRATION = ROOT / "data" / "team-shots" / "team-shots-calibration.txt"

XG_WEIGHT = 0.35

ROLLING_WINDOW = 20
MIN_MATCHES = 6
DECAY = 0.93
HOME_ATTACK_BOOST = 1.06
HOME_DEFENCE_BOOST = 0.96

LEAGUE_BASELINES: Dict[str, Dict[str, float]] = {
    "epl":        {"avg_shots": 12.8, "avg_sot": 4.5},
    "serie-a":    {"avg_shots": 12.5, "avg_sot": 4.3},
    "la-liga":    {"avg_shots": 12.2, "avg_sot": 4.1},
    "bundesliga": {"avg_shots": 12.9, "avg_sot": 4.4},
    "ligue-1":    {"avg_shots": 12.3, "avg_sot": 4.2},
}
DEFAULT_BASELINE = {"avg_shots": 12.5, "avg_sot": 4.3}

STANDARD_LINES = [7.5, 8.5, 9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5]


def _parse_float(val: Any, default: float = 0.0) -> float:
    text = str(val or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _parse_int(val: Any, default: int = 0) -> int:
    return int(_parse_float(val, float(default)))


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


def poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def poisson_cdf(k: int, lam: float) -> float:
    return sum(poisson_pmf(i, lam) for i in range(k + 1))


def prob_over(line: float, lam: float) -> float:
    """P(shots > line). For line=10.5, this is P(shots >= 11)."""
    k = int(line)
    return 1.0 - poisson_cdf(k, lam)


def fair_odds(prob: float) -> float:
    if prob <= 0:
        return 999.0
    if prob >= 1:
        return 1.001
    return round(1.0 / prob, 3)


@dataclass
class TeamState:
    shots_history: List[float] = field(default_factory=list)
    sot_history: List[float] = field(default_factory=list)
    conceded_shots_history: List[float] = field(default_factory=list)
    conceded_sot_history: List[float] = field(default_factory=list)
    corners_history: List[float] = field(default_factory=list)
    goals_history: List[float] = field(default_factory=list)
    conceded_goals_history: List[float] = field(default_factory=list)
    xg_history: List[float] = field(default_factory=list)
    conceded_xg_history: List[float] = field(default_factory=list)

    def add_match(self, shots: float, sot: float, conc_shots: float,
                  conc_sot: float, corners: float, goals: float, conc_goals: float,
                  xg: float = 0.0, conc_xg: float = 0.0) -> None:
        self.shots_history.append(shots)
        self.sot_history.append(sot)
        self.conceded_shots_history.append(conc_shots)
        self.conceded_sot_history.append(conc_sot)
        self.corners_history.append(corners)
        self.goals_history.append(goals)
        self.conceded_goals_history.append(conc_goals)
        self.xg_history.append(xg)
        self.conceded_xg_history.append(conc_xg)

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
        return len(self.shots_history)

    def avg_shots(self) -> Optional[float]:
        return self._ema(self.shots_history)

    def avg_sot(self) -> Optional[float]:
        return self._ema(self.sot_history)

    def avg_conceded_shots(self) -> Optional[float]:
        return self._ema(self.conceded_shots_history)

    def avg_conceded_sot(self) -> Optional[float]:
        return self._ema(self.conceded_sot_history)

    def avg_corners(self) -> Optional[float]:
        return self._ema(self.corners_history)

    def avg_goals(self) -> Optional[float]:
        return self._ema(self.goals_history)

    def avg_conceded_goals(self) -> Optional[float]:
        return self._ema(self.conceded_goals_history)

    def avg_xg(self) -> Optional[float]:
        valid = [v for v in self.xg_history if v > 0]
        if len(valid) < MIN_MATCHES:
            return None
        return self._ema(self.xg_history)

    def avg_conceded_xg(self) -> Optional[float]:
        valid = [v for v in self.conceded_xg_history if v > 0]
        if len(valid) < MIN_MATCHES:
            return None
        return self._ema(self.conceded_xg_history)


@dataclass
class MatchRow:
    match_date: date
    league: str
    season: str
    home_team: str
    away_team: str
    home_shots: int
    away_shots: int
    home_sot: int
    away_sot: int
    home_corners: int
    away_corners: int
    home_goals: int
    away_goals: int
    home_xg: float = 0.0
    away_xg: float = 0.0
    b365h: float = 0.0
    b365d: float = 0.0
    b365a: float = 0.0


def load_matches(path: Path) -> List[MatchRow]:
    rows: List[MatchRow] = []
    with open(path, "r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            d = _parse_date(row.get("Date", ""))
            if d is None:
                continue
            hs = _parse_int(row.get("HS"))
            as_ = _parse_int(row.get("AS"))
            if hs == 0 and as_ == 0:
                continue
            rows.append(MatchRow(
                match_date=d,
                league=row.get("league", ""),
                season=row.get("season", ""),
                home_team=row.get("HomeTeam", ""),
                away_team=row.get("AwayTeam", ""),
                home_shots=hs,
                away_shots=as_,
                home_sot=_parse_int(row.get("HST")),
                away_sot=_parse_int(row.get("AST")),
                home_corners=_parse_int(row.get("HC")),
                away_corners=_parse_int(row.get("AC")),
                home_goals=_parse_int(row.get("FTHG")),
                away_goals=_parse_int(row.get("FTAG")),
            ))
    rows.sort(key=lambda m: m.match_date)
    return rows


def load_fbref_matches(path: Path) -> List[MatchRow]:
    """Load the xG-enriched CSV from fbref-download-shooting.py."""
    rows: List[MatchRow] = []
    with open(path, "r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            d = _parse_date(row.get("date", ""))
            if d is None:
                continue
            hs = _parse_int(row.get("home_shots"))
            as_ = _parse_int(row.get("away_shots"))
            if hs == 0 and as_ == 0:
                continue
            rows.append(MatchRow(
                match_date=d,
                league=row.get("league", ""),
                season=row.get("season", ""),
                home_team=row.get("home_team", ""),
                away_team=row.get("away_team", ""),
                home_shots=hs,
                away_shots=as_,
                home_sot=_parse_int(row.get("home_sot")),
                away_sot=_parse_int(row.get("away_sot")),
                home_corners=_parse_int(row.get("home_corners")),
                away_corners=_parse_int(row.get("away_corners")),
                home_goals=_parse_int(row.get("home_goals")),
                away_goals=_parse_int(row.get("away_goals")),
                home_xg=_parse_float(row.get("home_xg")),
                away_xg=_parse_float(row.get("away_xg")),
                b365h=_parse_float(row.get("B365H")),
                b365d=_parse_float(row.get("B365D")),
                b365a=_parse_float(row.get("B365A")),
            ))
    rows.sort(key=lambda m: m.match_date)
    return rows


def compute_league_avg(matches: List[MatchRow]) -> Dict[str, Dict[str, float]]:
    """Compute actual league averages from the data."""
    league_shots: Dict[str, List[float]] = defaultdict(list)
    league_sot: Dict[str, List[float]] = defaultdict(list)
    league_xg: Dict[str, List[float]] = defaultdict(list)
    for m in matches:
        league_shots[m.league].append(m.home_shots)
        league_shots[m.league].append(m.away_shots)
        league_sot[m.league].append(m.home_sot)
        league_sot[m.league].append(m.away_sot)
        if m.home_xg > 0:
            league_xg[m.league].append(m.home_xg)
        if m.away_xg > 0:
            league_xg[m.league].append(m.away_xg)

    result: Dict[str, Dict[str, float]] = {}
    for league in league_shots:
        shots = league_shots[league]
        sot = league_sot[league]
        xg = league_xg.get(league, [])
        result[league] = {
            "avg_shots": sum(shots) / len(shots) if shots else 12.5,
            "avg_sot": sum(sot) / len(sot) if sot else 4.3,
            "avg_xg": sum(xg) / len(xg) if xg else 1.35,
        }
    return result


def predict_lambda(
    team_state: TeamState,
    opp_state: TeamState,
    league_avg: Dict[str, float],
    is_home: bool,
) -> Optional[Tuple[float, float]]:
    """
    Predict expected shots for `team` against `opp`.

    Shot-volume signal:
      lam_shots = avg_shots * (team_attack / avg) * (opp_weakness / avg) * venue
    xG signal (when available):
      lam_xg   = avg_shots * (team_xg_attack / avg_xg) * (opp_xg_weakness / avg_xg) * venue
    Final:
      lambda = (1 - XG_WEIGHT) * lam_shots + XG_WEIGHT * lam_xg

    Returns (model_lambda, xg_lambda_or_0) or None if insufficient data.
    """
    team_attack = team_state.avg_shots()
    opp_defence = opp_state.avg_conceded_shots()
    avg = league_avg.get("avg_shots", 12.5)

    if team_attack is None or opp_defence is None:
        return None

    attack_strength = team_attack / avg if avg > 0 else 1.0
    defence_weakness = opp_defence / avg if avg > 0 else 1.0
    lam_shots = avg * attack_strength * defence_weakness

    venue_mult = HOME_ATTACK_BOOST if is_home else (1.0 / HOME_ATTACK_BOOST)
    lam_shots *= venue_mult

    xg_lam = 0.0
    team_xg = team_state.avg_xg()
    opp_conc_xg = opp_state.avg_conceded_xg()
    avg_xg = league_avg.get("avg_xg", 1.35)

    if team_xg is not None and opp_conc_xg is not None and avg_xg > 0:
        xg_attack = team_xg / avg_xg
        xg_def_weakness = opp_conc_xg / avg_xg
        xg_lam = avg * xg_attack * xg_def_weakness * venue_mult
        lam = (1 - XG_WEIGHT) * lam_shots + XG_WEIGHT * xg_lam
    else:
        lam = lam_shots

    lam = max(3.0, min(lam, 30.0))
    xg_lam = max(3.0, min(xg_lam, 30.0)) if xg_lam > 0 else 0.0
    return lam, xg_lam


_MIN_LEAGUE_OBS = 40  # 40 per-team observations = 20 matches per league


def run_model(
    matches: List[MatchRow],
    *,
    holdout_start: Optional[date] = None,
) -> Tuple[List[dict], Dict[str, Dict[str, float]]]:
    team_states: Dict[str, TeamState] = defaultdict(TeamState)
    predictions: List[dict] = []

    # Causal league averages — accumulated match-by-match, no future look-ahead
    league_shots_sum: Dict[str, float] = defaultdict(float)
    league_shots_count: Dict[str, int] = defaultdict(int)
    league_sot_sum: Dict[str, float] = defaultdict(float)
    league_xg_sum: Dict[str, float] = defaultdict(float)
    league_xg_count: Dict[str, int] = defaultdict(int)

    def _causal_league_avg(league: str) -> Dict[str, float]:
        n = league_shots_count[league]
        if n < _MIN_LEAGUE_OBS:
            baseline = LEAGUE_BASELINES.get(league, DEFAULT_BASELINE)
            return {**baseline, "avg_xg": 1.35}
        nxg = league_xg_count[league]
        return {
            "avg_shots": league_shots_sum[league] / n,
            "avg_sot": league_sot_sum[league] / n,
            "avg_xg": (league_xg_sum[league] / nxg) if nxg > 0 else 1.35,
        }

    for m in matches:
        league_avg = _causal_league_avg(m.league)
        home_key = f"{m.league}:{m.home_team}"
        away_key = f"{m.league}:{m.away_team}"
        home_state = team_states[home_key]
        away_state = team_states[away_key]

        if holdout_start is None or m.match_date >= holdout_start:
            home_result = predict_lambda(home_state, away_state, league_avg, is_home=True)
            away_result = predict_lambda(away_state, home_state, league_avg, is_home=False)

            if home_result is not None:
                home_lambda, home_xg_lam = home_result
                pred = _build_prediction(m, m.home_team, m.away_team, "home",
                                         home_lambda, m.home_shots, m.home_sot,
                                         xg_lambda=home_xg_lam)
                predictions.append(pred)

            if away_result is not None:
                away_lambda, away_xg_lam = away_result
                pred = _build_prediction(m, m.away_team, m.home_team, "away",
                                         away_lambda, m.away_shots, m.away_sot,
                                         xg_lambda=away_xg_lam)
                predictions.append(pred)

        # Update causal accumulators after observing this match
        league_shots_sum[m.league] += m.home_shots + m.away_shots
        league_shots_count[m.league] += 2
        league_sot_sum[m.league] += m.home_sot + m.away_sot
        if m.home_xg > 0:
            league_xg_sum[m.league] += m.home_xg
            league_xg_count[m.league] += 1
        if m.away_xg > 0:
            league_xg_sum[m.league] += m.away_xg
            league_xg_count[m.league] += 1

        home_state.add_match(
            m.home_shots, m.home_sot, m.away_shots, m.away_sot,
            m.home_corners, m.home_goals, m.away_goals,
            xg=m.home_xg, conc_xg=m.away_xg,
        )
        away_state.add_match(
            m.away_shots, m.away_sot, m.home_shots, m.home_sot,
            m.away_corners, m.away_goals, m.home_goals,
            xg=m.away_xg, conc_xg=m.home_xg,
        )

    # Return final causal league averages for reporting
    final_avgs: Dict[str, Dict[str, float]] = {}
    for league in league_shots_count:
        n = league_shots_count[league]
        nxg = league_xg_count[league]
        final_avgs[league] = {
            "avg_shots": league_shots_sum[league] / n if n > 0 else 12.5,
            "avg_sot": league_sot_sum[league] / n if n > 0 else 4.3,
            "avg_xg": (league_xg_sum[league] / nxg) if nxg > 0 else 1.35,
        }
    return predictions, final_avgs


def _build_prediction(
    m: MatchRow, team: str, opponent: str, venue: str,
    lam: float, actual_shots: int, actual_sot: int,
    xg_lambda: float = 0.0,
) -> dict:
    is_home = (venue == "home")
    pred: dict = {
        "date": m.match_date.isoformat(),
        "league": m.league,
        "season": m.season,
        "team": team,
        "opponent": opponent,
        "venue": venue,
        "home_team": m.home_team,
        "away_team": m.away_team,
        "lambda_shots": round(lam, 2),
        "xg_lambda": round(xg_lambda, 2),
        "actual_shots": actual_shots,
        "actual_sot": actual_sot,
        "b365h": m.b365h if m.b365h > 0 else "",
        "b365d": m.b365d if m.b365d > 0 else "",
        "b365a": m.b365a if m.b365a > 0 else "",
    }

    for line in STANDARD_LINES:
        p_over = prob_over(line, lam)
        p_under = 1.0 - p_over
        pred[f"p_over_{line}"] = round(p_over, 4)
        pred[f"fair_over_{line}"] = fair_odds(p_over)
        pred[f"fair_under_{line}"] = fair_odds(p_under)

    return pred


def calibration_report(predictions: List[dict]) -> str:
    lines_report: List[str] = []
    lines_report.append("=" * 70)
    lines_report.append("  TEAM SHOTS MODEL -- CALIBRATION REPORT")
    lines_report.append("=" * 70)
    lines_report.append(f"  Total predictions: {len(predictions)}")
    lines_report.append("")

    if not predictions:
        return "\n".join(lines_report)

    lambdas = [p["lambda_shots"] for p in predictions]
    actuals = [p["actual_shots"] for p in predictions]
    lines_report.append(f"  Mean predicted lambda: {sum(lambdas)/len(lambdas):.2f}")
    lines_report.append(f"  Mean actual shots:     {sum(actuals)/len(actuals):.2f}")
    lines_report.append("")

    mae = sum(abs(a - l) for a, l in zip(actuals, lambdas)) / len(predictions)
    mse = sum((a - l) ** 2 for a, l in zip(actuals, lambdas)) / len(predictions)
    lines_report.append(f"  MAE:  {mae:.2f}")
    lines_report.append(f"  RMSE: {math.sqrt(mse):.2f}")
    lines_report.append("")

    for line in STANDARD_LINES:
        key = f"p_over_{line}"
        actual_overs = sum(1 for p in predictions if p["actual_shots"] > line)
        pred_prob_sum = sum(p[key] for p in predictions)
        n = len(predictions)

        actual_rate = actual_overs / n if n > 0 else 0
        predicted_rate = pred_prob_sum / n if n > 0 else 0

        lines_report.append(
            f"  Line {line:5.1f}: predicted={predicted_rate:.3f}  "
            f"actual={actual_rate:.3f}  diff={predicted_rate - actual_rate:+.3f}  "
            f"(n={n})"
        )

    # Calibration by probability bins
    lines_report.append("")
    lines_report.append("  Calibration by probability bins (over 10.5):")
    bins = [(0.0, 0.2), (0.2, 0.35), (0.35, 0.5), (0.5, 0.65), (0.65, 0.8), (0.8, 1.0)]
    for lo, hi in bins:
        subset = [p for p in predictions if lo <= p.get("p_over_10.5", 0) < hi]
        if not subset:
            continue
        actual_over = sum(1 for p in subset if p["actual_shots"] > 10.5)
        pred_avg = sum(p.get("p_over_10.5", 0) for p in subset) / len(subset)
        actual_rate = actual_over / len(subset)
        lines_report.append(
            f"    [{lo:.2f}, {hi:.2f}): n={len(subset):5d}  "
            f"predicted={pred_avg:.3f}  actual={actual_rate:.3f}  "
            f"diff={pred_avg - actual_rate:+.3f}"
        )

    # Per-league breakdown
    lines_report.append("")
    lines_report.append("  Per-league breakdown:")
    leagues = sorted(set(p["league"] for p in predictions))
    for league in leagues:
        lp = [p for p in predictions if p["league"] == league]
        mean_lam = sum(p["lambda_shots"] for p in lp) / len(lp)
        mean_actual = sum(p["actual_shots"] for p in lp) / len(lp)
        league_mae = sum(abs(p["actual_shots"] - p["lambda_shots"]) for p in lp) / len(lp)
        lines_report.append(
            f"    {league:15s}: n={len(lp):5d}  "
            f"pred={mean_lam:.2f}  actual={mean_actual:.2f}  MAE={league_mae:.2f}"
        )

    lines_report.append("")
    lines_report.append("=" * 70)
    return "\n".join(lines_report)


OUTPUT_FIELDS = [
    "date", "league", "season", "team", "opponent", "venue",
    "home_team", "away_team", "lambda_shots", "xg_lambda",
    "actual_shots", "actual_sot",
    "b365h", "b365d", "b365a",
] + [
    col
    for line in STANDARD_LINES
    for col in [f"p_over_{line}", f"fair_over_{line}", f"fair_under_{line}"]
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Team shots prediction model")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--fbref", type=Path, default=None,
                        help="xG-enriched CSV from fbref-download-shooting.py")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--holdout-start", type=str, default=None,
                        help="Only output predictions from this date (YYYY-MM-DD)")
    args = parser.parse_args()

    fbref_path = args.fbref or DEFAULT_FBREF
    if fbref_path.exists():
        print(f"Loading xG-enriched matches from {fbref_path}")
        matches = load_fbref_matches(fbref_path)
        xg_count = sum(1 for m in matches if m.home_xg > 0)
        print(f"  {len(matches)} matches loaded ({xg_count} with xG)")
    else:
        print(f"Loading matches from {args.input}")
        matches = load_matches(args.input)
        print(f"  {len(matches)} matches loaded (no xG)")

    holdout = None
    if args.holdout_start:
        holdout = date.fromisoformat(args.holdout_start)
        print(f"  Holdout start: {holdout}")

    predictions, league_avgs = run_model(matches, holdout_start=holdout)
    print(f"  {len(predictions)} predictions generated")

    print(f"\nLeague averages (shots per team per match):")
    for league, avgs in sorted(league_avgs.items()):
        print(f"  {league:15s}: shots={avgs['avg_shots']:.2f}  sot={avgs['avg_sot']:.2f}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(predictions)
    print(f"\nPredictions written to {args.output}")

    report = calibration_report(predictions)
    print(report)
    with open(args.calibration, "w", encoding="utf-8") as fh:
        fh.write(report)
    print(f"Calibration report saved to {args.calibration}")


if __name__ == "__main__":
    main()
