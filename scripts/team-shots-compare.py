#!/usr/bin/env python3
"""
Compare team-shots model fair odds against archived bookmaker odds (team total shots).

For each match+team+line in the odds archive, join to the model prediction
and compute edge / EV.

Usage:
  python scripts/team-shots-compare.py
  python scripts/team-shots-compare.py --bookmaker Bet365 --min-edge 0.05
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ODDS = ROOT / "data" / "team-shots" / "team-shots-odds-history.csv"
DEFAULT_PREDICTIONS = ROOT / "data" / "team-shots" / "team-shots-predictions.csv"
DEFAULT_UPCOMING = ROOT / "data" / "team-shots" / "team-shots-upcoming.csv"
DEFAULT_OUTPUT = ROOT / "data" / "team-shots" / "team-shots-comparison.csv"
DEFAULT_SUMMARY = ROOT / "data" / "team-shots" / "team-shots-comparison.txt"
DEFAULT_CAL_PARAMS = ROOT / "data" / "team-shots" / "team-shots-calibration-params.json"

COMPARE_FIELDS = [
    "date", "league", "home_team", "away_team", "team", "venue",
    "bookmaker", "line", "side", "book_odds",
    "model_prob", "model_prob_raw", "model_fair_odds",
    "edge", "ev", "actual_shots", "won", "pnl",
]


def _pf(val, default=0.0):
    text = str(val or "").strip()
    try:
        return float(text) if text else default
    except ValueError:
        return default


TEAM_ALIASES = {
    "liverpool": "liverpool",
    "liverpool fc": "liverpool",
    "fulham": "fulham",
    "fulham fc": "fulham",
    "nottingham forest": "nottingham forest",
    "aston villa": "aston villa",
    "aston villa fc": "aston villa",
    "manchester united": "manchester united",
    "manchester united fc": "manchester united",
    "man utd": "manchester united",
    "leeds united": "leeds united",
    "leeds united fc": "leeds united",
    "fc barcelona": "barcelona",
    "barcelona": "barcelona",
    "espanyol": "espanyol",
    "espanyol barcelona": "espanyol",
    "real sociedad": "sociedad",
    "real sociedad san sebastian": "sociedad",
    "deportivo alaves": "alaves",
    "deportivo alaves sad": "alaves",
    "alaves": "alaves",
    "alav s": "alaves",
    "ca osasuna": "osasuna",
    "osasuna": "osasuna",
    "real betis": "real betis",
    "real betis seville": "real betis",
    "real betis balompie": "real betis",
    "rc celta de vigo": "celta vigo",
    "celta de vigo": "celta vigo",
    "celta vigo": "celta vigo",
    "real oviedo": "oviedo",
    "oviedo": "oviedo",
    "athletic club bilbao": "athletic club",
    "athletic club": "athletic club",
    "athletic bilbao": "athletic club",
    "villarreal cf": "villarreal",
    "villarreal": "villarreal",
    "sevilla fc": "sevilla",
    "atletico madrid": "atletico madrid",
    "atletico de madrid": "atletico madrid",
    "elche cf": "elche",
    "valencia cf": "valencia",
    "sunderland afc": "sunderland",
    "tottenham hotspur": "tottenham",
    "wolverhampton wanderers": "wolves",
    "west ham united": "west ham",
    "newcastle united": "newcastle",
    "1 fc heidenheim": "heidenheim",
    "1 fc koln": "fc koln",
    "1 fc cologne": "fc koln",
    "fc st pauli": "st pauli",
    "brighton and hove albion": "brighton",
}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFD", (text or "").strip().lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    text = " ".join(
        token
        for token in text.split()
        if token not in {"fc", "afc", "sc", "cf", "ac", "club", "ca", "rc"}
    )
    return text.strip()


def _norm_team(text: str) -> str:
    normalized = _norm(text or "")
    return TEAM_ALIASES.get(normalized, normalized)


def _logit(p: float) -> float:
    p = max(1e-7, min(1.0 - 1e-7, p))
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    if x >= 0.0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)


def calibrate_prob(p_raw: float, a: float, b: float) -> float:
    return _sigmoid(a * _logit(p_raw) + b)


def load_calibration_params(
    path: Path,
) -> Optional[Dict[str, Tuple[float, float]]]:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    result: Dict[str, Tuple[float, float]] = {}
    for line_str, ab in data.get("lines", {}).items():
        result[line_str] = (ab["a"], ab["b"])
    return result or None


def load_predictions(path: Path) -> Dict[str, dict]:
    """Index predictions by (date, league, team)."""
    index: Dict[str, dict] = {}
    if not path.exists():
        return index
    with open(path, "r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = f"{row.get('date', '')}|{_norm(row.get('league', ''))}|{_norm_team(row.get('team', ''))}"
            index[key] = row
    return index


def load_upcoming(path: Path) -> Dict[str, dict]:
    """Index upcoming rows in the same shape as historical prediction rows."""
    index: Dict[str, dict] = {}
    if not path.exists():
        return index

    with open(path, "r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            kickoff_iso = (row.get("kickoff_iso") or "").strip()
            match_date = kickoff_iso[:10] if kickoff_iso else ""
            league = row.get("league", "")
            home_team = row.get("home_team", "")
            away_team = row.get("away_team", "")
            if not match_date or not league or not home_team or not away_team:
                continue

            for side in ("home", "away"):
                team = home_team if side == "home" else away_team
                lam = row.get(f"{side}_lambda", "")
                pred_row = {
                    "date": match_date,
                    "league": league,
                    "team": team,
                    "opponent": away_team if side == "home" else home_team,
                    "venue": side,
                    "home_team": home_team,
                    "away_team": away_team,
                    "lambda_shots": lam,
                    "xg_lambda": "",
                    "actual_shots": "",
                    "actual_sot": "",
                }
                # Must match columns in team-shots-upcoming.csv (books often quote 12.5/13.5).
                for line in (9.5, 10.5, 11.5, 12.5, 13.5):
                    pred_row[f"p_over_{line}"] = row.get(f"{side}_p_over_{line}", "")
                    pred_row[f"fair_over_{line}"] = row.get(f"{side}_fair_over_{line}", "")
                    pred_row[f"fair_under_{line}"] = row.get(f"{side}_fair_under_{line}", "")

                key = f"{match_date}|{_norm(league)}|{_norm_team(team)}"
                index[key] = pred_row

    return index


def load_odds(path: Path, bookmaker_filter: str = "") -> List[dict]:
    keyed_rows: Dict[str, dict] = {}
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if bookmaker_filter:
                if _norm(row.get("bookmaker", "")) != _norm(bookmaker_filter):
                    continue
            key = "|".join(
                [
                    (row.get("match_date") or "")[:10],
                    _norm_team(row.get("home_team", "")),
                    _norm_team(row.get("away_team", "")),
                    _norm_team(row.get("team", "")),
                    str(row.get("line", "")),
                    _norm(row.get("side", "")),
                    _norm(row.get("bookmaker", "")),
                ]
            )
            captured_at = row.get("captured_at", "") or ""
            existing = keyed_rows.get(key)
            if existing is None or captured_at >= (existing.get("captured_at", "") or ""):
                keyed_rows[key] = row
    return list(keyed_rows.values())


def compare(
    predictions_index: Dict[str, dict],
    odds_rows: List[dict],
    min_edge: float = 0.0,
    cal_params: Optional[Dict[str, Tuple[float, float]]] = None,
) -> List[dict]:
    results: List[dict] = []

    for odds_row in odds_rows:
        match_date = (odds_row.get("match_date") or "")[:10]
        home = odds_row.get("home_team", "")
        away = odds_row.get("away_team", "")
        team = odds_row.get("team", "")
        line = _pf(odds_row.get("line"))
        side = (odds_row.get("side") or "").strip().lower()
        book_odds = _pf(odds_row.get("odds_decimal"))
        bookmaker = odds_row.get("bookmaker", "")
        competition = odds_row.get("competition", "")

        if book_odds <= 1.0 or not side:
            continue

        league_norm = _norm(competition)
        team_norm = _norm_team(team)

        pred = None
        for league_try in [league_norm, "epl", "serie-a", "la-liga", "bundesliga", "ligue-1"]:
            key = f"{match_date}|{league_try}|{team_norm}"
            pred = predictions_index.get(key)
            if pred:
                break

        if not pred:
            for pkey, pval in predictions_index.items():
                if pkey.startswith(match_date) and team_norm in pkey:
                    pred = pval
                    break

        if not pred:
            continue

        # Skip no_state rows (no historical data for this team)
        if not str(pred.get("lambda_shots", "")).strip():
            continue

        p_over_key = f"p_over_{line}"
        fair_over_key = f"fair_over_{line}"
        fair_under_key = f"fair_under_{line}"

        if p_over_key not in pred:
            continue

        p_over_raw_str = str(pred.get(p_over_key, "")).strip()
        if not p_over_raw_str:
            continue

        model_p_over_raw = _pf(pred.get(p_over_key))
        model_p_under_raw = 1.0 - model_p_over_raw

        # Apply Platt calibration if params available for this line
        ab = cal_params.get(str(line)) if cal_params else None
        if ab:
            model_p_over = calibrate_prob(model_p_over_raw, ab[0], ab[1])
            model_p_under = 1.0 - model_p_over
        else:
            model_p_over = model_p_over_raw
            model_p_under = model_p_under_raw

        if side == "over":
            model_prob = model_p_over
            model_prob_raw = model_p_over_raw
            model_fair = (1.0 / model_prob) if model_prob > 0 else 0.0
        else:
            model_prob = model_p_under
            model_prob_raw = model_p_under_raw
            model_fair = (1.0 / model_prob) if model_prob > 0 else 0.0

        edge = model_prob * book_odds - 1.0
        ev = edge

        if edge < min_edge:
            continue

        actual_raw = pred.get("actual_shots", "")
        actual_shots = int(_pf(actual_raw, 0)) if str(actual_raw or "").strip() else ""
        if actual_shots == "":
            won = ""
            pnl = ""
        else:
            if side == "over":
                won = actual_shots > line
            else:
                won = actual_shots < line
            pnl = (book_odds - 1.0) if won else -1.0

        venue = pred.get("venue", "")

        results.append({
            "date": match_date,
            "league": pred.get("league", ""),
            "home_team": home,
            "away_team": away,
            "team": team,
            "venue": venue,
            "bookmaker": bookmaker,
            "line": line,
            "side": side,
            "book_odds": round(book_odds, 3),
            "model_prob": round(model_prob, 4),
            "model_prob_raw": round(model_prob_raw, 4),
            "model_fair_odds": round(model_fair, 3),
            "edge": round(edge, 4),
            "ev": round(ev, 4),
            "actual_shots": actual_shots,
            "won": won,
            "pnl": round(pnl, 3) if pnl != "" else "",
        })

    return results


def build_summary(results: List[dict]) -> str:
    lines: List[str] = []
    lines.append("=" * 60)
    lines.append("  TEAM SHOTS -- MODEL vs BOOKMAKER COMPARISON")
    lines.append("=" * 60)
    lines.append(f"  Comparisons: {len(results)}")

    if not results:
        lines.append("  No comparisons available (odds archive may be empty).")
        lines.append("=" * 60)
        return "\n".join(lines)

    settled = [r for r in results if r.get("pnl", "") != ""]
    pending = [r for r in results if r.get("pnl", "") == ""]

    total_pnl = sum(_pf(r["pnl"]) for r in settled)
    wins = sum(1 for r in settled if r["won"])
    roi = total_pnl / len(settled) * 100 if settled else 0.0

    lines.append(f"  Settled:  {len(settled)}")
    lines.append(f"  Pending:  {len(pending)}")
    if settled:
        lines.append(f"  PnL:      {total_pnl:+.1f}u")
        lines.append(f"  ROI:      {roi:+.1f}%")
        lines.append(f"  Win rate: {wins}/{len(settled)} ({wins/len(settled)*100:.1f}%)")
    lines.append(f"  Avg edge: {sum(r['edge'] for r in results)/len(results):.3f}")
    lines.append(f"  Avg odds: {sum(r['book_odds'] for r in results)/len(results):.3f}")
    lines.append("=" * 60)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare team shots model vs bookmaker odds")
    parser.add_argument("--odds", type=Path, default=DEFAULT_ODDS)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--upcoming", type=Path, default=DEFAULT_UPCOMING)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CAL_PARAMS)
    parser.add_argument("--no-calibration", action="store_true")
    parser.add_argument("--bookmaker", default="")
    parser.add_argument("--min-edge", type=float, default=0.0)
    args = parser.parse_args()

    print(f"Loading predictions from {args.predictions}")
    pred_index = load_predictions(args.predictions)
    print(f"  {len(pred_index)} team-date entries indexed")

    print(f"Loading upcoming rows from {args.upcoming}")
    upcoming_index = load_upcoming(args.upcoming)
    print(f"  {len(upcoming_index)} upcoming team-date entries indexed")
    pred_index.update(upcoming_index)

    print(f"Loading odds from {args.odds}")
    odds_rows = load_odds(args.odds, args.bookmaker)
    print(f"  {len(odds_rows)} odds rows loaded")

    cal_params = None
    if not args.no_calibration:
        cal_params = load_calibration_params(args.calibration)
        if cal_params:
            print(f"Calibration params loaded from {args.calibration} "
                  f"(lines: {', '.join(sorted(cal_params))})")
        else:
            print(f"No calibration params found at {args.calibration} — using raw probs")

    results = compare(pred_index, odds_rows, args.min_edge, cal_params=cal_params)
    print(f"  {len(results)} comparisons with edge >= {args.min_edge}")

    if results:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=COMPARE_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)
        print(f"  Written to {args.output}")

    summary = build_summary(results)
    print(summary)
    with open(args.summary, "w", encoding="utf-8") as fh:
        fh.write(summary)


if __name__ == "__main__":
    main()
