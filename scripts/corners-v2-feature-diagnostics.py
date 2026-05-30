#!/usr/bin/env python3
"""Feature diagnostics for corners v2 real-odds backtest.

This script explains where the v2 NB/market-anchored model is gaining or
losing against real Pinnacle prices. It uses the real-odds backtest output as
the source of selections and joins strictly past-only pre-match team features
from the historical match file.

Important: actual match shots are only reported in explicitly labelled
post-match diagnostic columns. They are not pre-match model features.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKTEST = ROOT / "data" / "corners-ou" / "corners-real-odds-backtest-results.csv"
DEFAULT_HISTORICAL = ROOT / "data" / "corners-ou" / "historical" / "all-historical-matches.csv"
DEFAULT_OUTPUT = ROOT / "data" / "corners-ou" / "corners-v2-feature-diagnostics.csv"
DEFAULT_REPORT = ROOT / "data" / "corners-ou" / "corners-v2-feature-diagnostics.txt"

TEAM_ALIASES = {
    "ath bilbao": "athletic bilbao",
    "ath madrid": "atletico madrid",
    "betis": "real betis",
    "borussia monchengladbach": "m gladbach",
    "dortmund": "borussia dortmund",
    "ein frankfurt": "eintracht frankfurt",
    "espanol": "espanyol",
    "hamburg": "hamburger sv",
    "inter": "internazionale",
    "leeds": "leeds united",
    "leverkusen": "bayer leverkusen",
    "man city": "manchester city",
    "man united": "manchester united",
    "milan": "ac milan",
    "newcastle": "newcastle united",
    "nott m forest": "nottingham forest",
    "oviedo": "real oviedo",
    "paris sg": "paris saint germain",
    "sociedad": "real sociedad",
    "st pauli": "st pauli",
    "tottenham": "tottenham hotspur",
    "vallecano": "rayo vallecano",
    "verona": "hellas verona",
    "west ham": "west ham united",
}

OUTPUT_FIELDS = [
    "match_date", "league", "home_team", "away_team", "line", "selected_side", "selected_ev",
    "selected_odds", "selected_close_odds", "bet_result", "pnl_units", "published_to_close_clv",
    "actual_total", "result_side", "lambda_poisson", "market_lambda", "lambda_v2", "lambda_gap_model_market",
    "p_market_over", "p_v2_over", "line_bucket", "line_type", "side_line", "side_league", "edge_bucket", "lambda_gap_bucket",
    "fav_side", "fav_prob", "fav_gap", "fav_bucket", "pre_home_shot_pressure", "pre_away_shot_pressure",
    "pre_total_shot_pressure", "pre_total_sot_pressure", "pre_total_corner_pressure", "pre_corner_per_shot",
    "pre_recent_corner_delta", "pre_recent_shot_delta", "shot_pressure_bucket", "corner_pressure_bucket",
    "corner_per_shot_bucket", "recent_corner_delta_bucket", "recent_shot_delta_bucket", "pre_feature_ready",
    "post_match_total_shots", "post_match_total_sot", "post_match_corners_per_shot", "post_match_shot_bucket",
]


def pf(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def pi(value: Any, default: int = 0) -> int:
    parsed = pf(value)
    return int(parsed) if parsed is not None else default


def parse_date(value: str) -> date | None:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def norm_team(text: str) -> str:
    raw = (text or "").strip().lower().replace("(corners)", "")
    raw = unicodedata.normalize("NFD", raw)
    raw = "".join(ch for ch in raw if unicodedata.category(ch) != "Mn")
    raw = re.sub(r"[^a-z0-9]+", " ", raw).strip()
    return TEAM_ALIASES.get(raw, raw)


def bucket(value: float | None, cuts: list[tuple[float, str]], missing: str = "missing") -> str:
    if value is None or not math.isfinite(value):
        return missing
    for threshold, label in cuts:
        if value < threshold:
            return label
    return cuts[-1][1].replace("<", ">=") if cuts else str(value)


@dataclass
class TeamState:
    corners_for: list[float] = field(default_factory=list)
    corners_against: list[float] = field(default_factory=list)
    shots_for: list[float] = field(default_factory=list)
    shots_against: list[float] = field(default_factory=list)
    sot_for: list[float] = field(default_factory=list)
    sot_against: list[float] = field(default_factory=list)
    goals_for: list[float] = field(default_factory=list)
    goals_against: list[float] = field(default_factory=list)

    def add(self, *, corners_for: float, corners_against: float, shots_for: float, shots_against: float, sot_for: float, sot_against: float, goals_for: float, goals_against: float) -> None:
        self.corners_for.append(corners_for)
        self.corners_against.append(corners_against)
        self.shots_for.append(shots_for)
        self.shots_against.append(shots_against)
        self.sot_for.append(sot_for)
        self.sot_against.append(sot_against)
        self.goals_for.append(goals_for)
        self.goals_against.append(goals_against)

    def avg(self, name: str, window: int) -> float | None:
        vals = getattr(self, name)[-window:]
        if len(vals) < min(6, window):
            return None
        return sum(vals) / len(vals)

    @property
    def n(self) -> int:
        return len(self.corners_for)


@dataclass
class HistMatch:
    match_date: date
    league: str
    home_team: str
    away_team: str
    home_corners: int
    away_corners: int
    home_shots: int
    away_shots: int
    home_sot: int
    away_sot: int
    home_goals: int
    away_goals: int
    b365h: float | None
    b365d: float | None
    b365a: float | None


def load_historical(path: Path) -> list[HistMatch]:
    rows: list[HistMatch] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            d = parse_date(row.get("Date") or row.get("date") or "")
            if d is None:
                continue
            hc = pi(row.get("HC") or row.get("home_corners"))
            ac = pi(row.get("AC") or row.get("away_corners"))
            if hc == 0 and ac == 0:
                continue
            rows.append(
                HistMatch(
                    match_date=d,
                    league=str(row.get("league") or "").strip().lower(),
                    home_team=str(row.get("HomeTeam") or row.get("home_team") or "").strip(),
                    away_team=str(row.get("AwayTeam") or row.get("away_team") or "").strip(),
                    home_corners=hc,
                    away_corners=ac,
                    home_shots=pi(row.get("HS") or row.get("home_shots")),
                    away_shots=pi(row.get("AS") or row.get("away_shots")),
                    home_sot=pi(row.get("HST") or row.get("home_sot")),
                    away_sot=pi(row.get("AST") or row.get("away_sot")),
                    home_goals=pi(row.get("FTHG") or row.get("home_goals")),
                    away_goals=pi(row.get("FTAG") or row.get("away_goals")),
                    b365h=pf(row.get("B365H")),
                    b365d=pf(row.get("B365D")),
                    b365a=pf(row.get("B365A")),
                )
            )
    rows.sort(key=lambda item: item.match_date)
    return rows


def safe_avg(values: Iterable[float | None]) -> float | None:
    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return sum(vals) / len(vals) if vals else None


def implied_probs(h: float | None, d: float | None, a: float | None) -> tuple[str, float | None, float | None]:
    if not h or not d or not a or min(h, d, a) <= 1.0:
        return "missing", None, None
    ph, pd, pa = 1.0 / h, 1.0 / d, 1.0 / a
    total = ph + pd + pa
    if total <= 0:
        return "missing", None, None
    ph, pa = ph / total, pa / total
    if ph >= pa:
        return "home", ph, abs(ph - pa)
    return "away", pa, abs(ph - pa)


def build_feature_index(matches: list[HistMatch]) -> dict[tuple[str, str, str], dict[str, Any]]:
    states: dict[tuple[str, str], TeamState] = defaultdict(TeamState)
    features: dict[tuple[str, str, str], dict[str, Any]] = {}
    for match in matches:
        home_key = (match.league, norm_team(match.home_team))
        away_key = (match.league, norm_team(match.away_team))
        home = states[home_key]
        away = states[away_key]

        def pressure(team: TeamState, opp: TeamState, for_name: str, against_name: str, window: int) -> float | None:
            own = team.avg(for_name, window)
            conceded = opp.avg(against_name, window)
            return safe_avg([own, conceded])

        home_shot20 = pressure(home, away, "shots_for", "shots_against", 20)
        away_shot20 = pressure(away, home, "shots_for", "shots_against", 20)
        home_shot6 = pressure(home, away, "shots_for", "shots_against", 6)
        away_shot6 = pressure(away, home, "shots_for", "shots_against", 6)
        home_sot20 = pressure(home, away, "sot_for", "sot_against", 20)
        away_sot20 = pressure(away, home, "sot_for", "sot_against", 20)
        home_corner20 = pressure(home, away, "corners_for", "corners_against", 20)
        away_corner20 = pressure(away, home, "corners_for", "corners_against", 20)
        home_corner6 = pressure(home, away, "corners_for", "corners_against", 6)
        away_corner6 = pressure(away, home, "corners_for", "corners_against", 6)
        total_shot20 = safe_avg([home_shot20, away_shot20])
        if total_shot20 is not None:
            total_shot20 *= 2.0
        total_shot6 = safe_avg([home_shot6, away_shot6])
        if total_shot6 is not None:
            total_shot6 *= 2.0
        total_sot20 = safe_avg([home_sot20, away_sot20])
        if total_sot20 is not None:
            total_sot20 *= 2.0
        total_corner20 = safe_avg([home_corner20, away_corner20])
        if total_corner20 is not None:
            total_corner20 *= 2.0
        total_corner6 = safe_avg([home_corner6, away_corner6])
        if total_corner6 is not None:
            total_corner6 *= 2.0
        home_cps = (home.avg("corners_for", 20) / home.avg("shots_for", 20)) if home.avg("shots_for", 20) else None
        away_cps = (away.avg("corners_for", 20) / away.avg("shots_for", 20)) if away.avg("shots_for", 20) else None
        fav_side, fav_prob, fav_gap = implied_probs(match.b365h, match.b365d, match.b365a)
        pre_ready = home.n >= 6 and away.n >= 6
        post_total_shots = match.home_shots + match.away_shots
        post_total_sot = match.home_sot + match.away_sot
        post_cps = (match.home_corners + match.away_corners) / post_total_shots if post_total_shots > 0 else None
        row = {
            "fav_side": fav_side,
            "fav_prob": fav_prob,
            "fav_gap": fav_gap,
            "pre_home_shot_pressure": home_shot20,
            "pre_away_shot_pressure": away_shot20,
            "pre_total_shot_pressure": total_shot20,
            "pre_total_sot_pressure": total_sot20,
            "pre_total_corner_pressure": total_corner20,
            "pre_corner_per_shot": safe_avg([home_cps, away_cps]),
            "pre_recent_corner_delta": (total_corner6 - total_corner20) if total_corner6 is not None and total_corner20 is not None else None,
            "pre_recent_shot_delta": (total_shot6 - total_shot20) if total_shot6 is not None and total_shot20 is not None else None,
            "pre_feature_ready": "true" if pre_ready else "false",
            "post_match_total_shots": post_total_shots,
            "post_match_total_sot": post_total_sot,
            "post_match_corners_per_shot": post_cps,
        }
        key = (match.match_date.isoformat(), norm_team(match.home_team), norm_team(match.away_team))
        features[key] = row
        features[(key[0], key[2], key[1])] = row

        home.add(
            corners_for=match.home_corners,
            corners_against=match.away_corners,
            shots_for=match.home_shots,
            shots_against=match.away_shots,
            sot_for=match.home_sot,
            sot_against=match.away_sot,
            goals_for=match.home_goals,
            goals_against=match.away_goals,
        )
        away.add(
            corners_for=match.away_corners,
            corners_against=match.home_corners,
            shots_for=match.away_shots,
            shots_against=match.home_shots,
            sot_for=match.away_sot,
            sot_against=match.home_sot,
            goals_for=match.away_goals,
            goals_against=match.home_goals,
        )
    return features


def line_bucket(line: float | None) -> str:
    if line is None:
        return "missing"
    if line <= 8.5:
        return "<=8.5"
    if line <= 9.5:
        return "9.0-9.5"
    if line <= 10.5:
        return "10.0-10.5"
    return ">=11.0"


def line_type(line: float | None) -> str:
    if line is None:
        return "missing"
    return "integer" if abs(line - round(line)) < 1e-9 else "half"


def edge_bucket(edge: float | None) -> str:
    if edge is None:
        return "missing"
    if edge < 0.06:
        return "3-6%"
    if edge < 0.10:
        return "6-10%"
    return ">=10%"


def enrich_rows(backtest_rows: list[dict[str, str]], feature_index: dict[tuple[str, str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in backtest_rows:
        if not str(row.get("selected_side") or "").strip():
            continue
        key = (str(row.get("match_date") or "")[:10], norm_team(row.get("home_team") or ""), norm_team(row.get("away_team") or ""))
        feat = feature_index.get(key, {})
        line = pf(row.get("line"))
        selected_ev = pf(row.get("selected_ev"))
        lambda_poisson = pf(row.get("lambda_poisson"))
        market_lambda = pf(row.get("market_lambda"))
        lambda_gap = (lambda_poisson - market_lambda) if lambda_poisson is not None and market_lambda is not None else None
        total_shot_pressure = feat.get("pre_total_shot_pressure")
        total_corner_pressure = feat.get("pre_total_corner_pressure")
        corner_per_shot = feat.get("pre_corner_per_shot")
        recent_corner_delta = feat.get("pre_recent_corner_delta")
        recent_shot_delta = feat.get("pre_recent_shot_delta")
        post_shots = feat.get("post_match_total_shots")
        out = {field: "" for field in OUTPUT_FIELDS}
        for field in OUTPUT_FIELDS:
            if field in row:
                out[field] = row.get(field, "")
        out.update({k: v for k, v in feat.items() if k in OUTPUT_FIELDS})
        out["lambda_gap_model_market"] = lambda_gap
        out["line_bucket"] = line_bucket(line)
        out["line_type"] = line_type(line)
        out["side_line"] = f"{row.get('selected_side')}|{out['line_bucket']}"
        out["side_league"] = f"{row.get('selected_side')}|{row.get('league')}"
        out["edge_bucket"] = edge_bucket(selected_ev)
        out["lambda_gap_bucket"] = bucket(lambda_gap, [(-1.5, "model<<market"), (-0.5, "model<market"), (0.5, "aligned"), (1.5, "model>market"), (999, "model>>market")])
        out["fav_bucket"] = bucket(feat.get("fav_prob"), [(0.45, "balanced<45"), (0.55, "fav45-55"), (0.65, "fav55-65"), (999, "fav>=65")])
        out["shot_pressure_bucket"] = bucket(total_shot_pressure, [(22, "<22"), (25, "22-25"), (28, "25-28"), (999, ">=28")])
        out["corner_pressure_bucket"] = bucket(total_corner_pressure, [(8.5, "<8.5"), (9.5, "8.5-9.5"), (10.5, "9.5-10.5"), (999, ">=10.5")])
        out["corner_per_shot_bucket"] = bucket(corner_per_shot, [(0.30, "<0.30"), (0.36, "0.30-0.36"), (0.42, "0.36-0.42"), (999, ">=0.42")])
        out["recent_corner_delta_bucket"] = bucket(recent_corner_delta, [(-1.0, "<-1"), (-0.25, "-1 to -0.25"), (0.25, "flat"), (1.0, "+0.25 to +1"), (999, ">=+1")])
        out["recent_shot_delta_bucket"] = bucket(recent_shot_delta, [(-3.0, "<-3"), (-1.0, "-3 to -1"), (1.0, "flat"), (3.0, "+1 to +3"), (999, ">=+3")])
        out["post_match_shot_bucket"] = bucket(post_shots, [(20, "<20"), (25, "20-25"), (30, "25-30"), (999, ">=30")])
        output.append(out)
    return output


def metric(row: dict[str, Any], key: str) -> float | None:
    return pf(row.get(key))


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    settled = [row for row in rows if str(row.get("bet_result") or "").strip().lower() in {"won", "lost", "push"}]
    risked = [row for row in settled if str(row.get("bet_result") or "").strip().lower() in {"won", "lost"}]
    pnl = sum(metric(row, "pnl_units") or 0.0 for row in settled)
    clv_vals = [metric(row, "published_to_close_clv") for row in settled if metric(row, "published_to_close_clv") is not None]
    avg_clv = sum(clv_vals) / len(clv_vals) if clv_vals else None
    pos_clv = sum(1 for v in clv_vals if v > 0) / len(clv_vals) if clv_vals else None
    roi = pnl / len(risked) if risked else None
    return {"n": len(settled), "risked": len(risked), "pnl": pnl, "roi": roi, "avg_clv": avg_clv, "pos_clv": pos_clv, "clv_n": len(clv_vals)}


def fmt_pct(value: float | None) -> str:
    return "-" if value is None else f"{value:+.2%}"


def grouped_summaries(rows: list[dict[str, Any]], field: str) -> list[tuple[str, dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(field) or "missing")].append(row)
    return [(label, summarize(group)) for label, group in groups.items()]


def append_table(lines: list[str], title: str, rows: list[dict[str, Any]], field: str, *, min_n: int = 0) -> None:
    lines.extend(["", title, "segment,n,risked,pnl,roi,avg_clv,pos_clv,clv_n,flag"])
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(field) or "missing")].append(row)
    for label, group in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        s = summarize(group)
        flag = "LOW_N" if s["n"] < min_n else ""
        lines.append(
            f"{label},{s['n']},{s['risked']},{s['pnl']:+.2f},{fmt_pct(s['roi'])},{fmt_pct(s['avg_clv'])},{fmt_pct(s['pos_clv'])},{s['clv_n']},{flag}"
        )


def append_candidate_cells(lines: list[str], rows: list[dict[str, Any]]) -> None:
    candidate_fields = [
        "selected_side", "league", "side_league", "line_bucket", "side_line", "edge_bucket",
        "lambda_gap_bucket", "fav_bucket", "shot_pressure_bucket", "corner_pressure_bucket",
        "corner_per_shot_bucket", "recent_corner_delta_bucket", "recent_shot_delta_bucket",
    ]
    candidates: list[tuple[str, str, dict[str, Any]]] = []
    traps: list[tuple[str, str, dict[str, Any]]] = []
    for field in candidate_fields:
        for label, s in grouped_summaries(rows, field):
            if s["n"] < 30:
                continue
            roi = s.get("roi")
            clv = s.get("avg_clv")
            pos = s.get("pos_clv")
            if roi is not None and clv is not None and roi > 0.0 and clv > 0.0 and (pos or 0.0) >= 0.50:
                candidates.append((field, label, s))
            if roi is not None and clv is not None and roi < 0.0 and clv > 0.01 and (pos or 0.0) >= 0.55:
                traps.append((field, label, s))
    candidates.sort(key=lambda item: (-(item[2]["avg_clv"] or 0.0), -item[2]["n"]))
    traps.sort(key=lambda item: (-(item[2]["avg_clv"] or 0.0), -item[2]["n"]))
    lines.extend(["", "Candidate cells with positive ROI and CLV (not promotion proof)", "field,segment,n,roi,avg_clv,pos_clv,pnl"])
    if not candidates:
        lines.append("none,,,,,,")
    for field, label, s in candidates[:12]:
        lines.append(f"{field},{label},{s['n']},{fmt_pct(s['roi'])},{fmt_pct(s['avg_clv'])},{fmt_pct(s['pos_clv'])},{s['pnl']:+.2f}")
    lines.extend(["", "Trap cells: positive CLV but negative ROI", "field,segment,n,roi,avg_clv,pos_clv,pnl"])
    if not traps:
        lines.append("none,,,,,,")
    for field, label, s in traps[:12]:
        lines.append(f"{field},{label},{s['n']},{fmt_pct(s['roi'])},{fmt_pct(s['avg_clv'])},{fmt_pct(s['pos_clv'])},{s['pnl']:+.2f}")


def render_report(rows: list[dict[str, Any]], *, joined_count: int, missing_features: int) -> str:
    total = summarize(rows)
    over_rows = [r for r in rows if str(r.get("selected_side") or "") == "over"]
    under_rows = [r for r in rows if str(r.get("selected_side") or "") == "under"]
    lines = [
        "Corners V2 Feature Diagnostics",
        "",
        "Status: RESEARCH_ONLY. Real Pinnacle prices only. One selected bet per match from corners-real-odds-backtest.py.",
        "Pre-match pressure features are strictly past-only. Post-match shot buckets are labelled diagnostics only.",
        "",
        f"selected_rows: {len(rows)}",
        f"feature_rows_joined: {joined_count}",
        f"feature_rows_missing: {missing_features}",
        f"overall: n={total['n']} pnl={total['pnl']:+.2f} roi={fmt_pct(total['roi'])} avg_clv={fmt_pct(total['avg_clv'])} pos_clv={fmt_pct(total['pos_clv'])}",
        f"over: n={summarize(over_rows)['n']} roi={fmt_pct(summarize(over_rows)['roi'])} avg_clv={fmt_pct(summarize(over_rows)['avg_clv'])}",
        f"under: n={summarize(under_rows)['n']} roi={fmt_pct(summarize(under_rows)['roi'])} avg_clv={fmt_pct(summarize(under_rows)['avg_clv'])}",
        "",
        "Main read: a bucket is interesting only if CLV improves, not just ROI. Treat n<30 as noise.",
    ]
    append_candidate_cells(lines, rows)
    for title, field in [
        ("By selected side", "selected_side"),
        ("By league", "league"),
        ("By side x league", "side_league"),
        ("By line bucket", "line_bucket"),
        ("By line type", "line_type"),
        ("By side x line", "side_line"),
        ("By selected EV bucket", "edge_bucket"),
        ("By model-market lambda gap", "lambda_gap_bucket"),
        ("By favourite probability", "fav_bucket"),
        ("By pre-match shot pressure", "shot_pressure_bucket"),
        ("By pre-match corner pressure", "corner_pressure_bucket"),
        ("By pre-match corners per shot", "corner_per_shot_bucket"),
        ("By recent corner pressure delta", "recent_corner_delta_bucket"),
        ("By recent shot pressure delta", "recent_shot_delta_bucket"),
        ("Post-match total shot bucket (diagnostic only)", "post_match_shot_bucket"),
    ]:
        append_table(lines, title, rows, field, min_n=30)
    return "\n".join(lines) + "\n"


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Corners v2 feature diagnostics on real-odds selected bets")
    parser.add_argument("--backtest", type=Path, default=DEFAULT_BACKTEST)
    parser.add_argument("--historical", type=Path, default=DEFAULT_HISTORICAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    backtest_rows = list(csv.DictReader(args.backtest.open("r", encoding="utf-8-sig", newline="")))
    features = build_feature_index(load_historical(args.historical))
    rows = enrich_rows(backtest_rows, features)
    joined = sum(1 for row in rows if row.get("pre_feature_ready") in {"true", "false"})
    missing = len(rows) - joined
    write_csv(args.output, rows)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(rows, joined_count=joined, missing_features=missing), encoding="utf-8")
    print(f"Wrote {args.output.relative_to(ROOT)}")
    print(f"Wrote {args.report.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
