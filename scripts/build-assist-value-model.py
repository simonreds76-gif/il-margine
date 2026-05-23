#!/usr/bin/env python3
"""Build private assist-value model signals.

V0 model shape:
  player assist/xA history + expected minutes proxy + team/opponent context
  + set-piece role boost, compared against Bet365 anytime-assist prices.

This writes research-only shadow signals. It does not publish to Fair Odds Lab.
"""

from __future__ import annotations

import argparse
import csv
import glob
import math
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOARD = "data/assist-value/assist-value-shadow-board.csv"
DEFAULT_PLAYER_LOGS = "data/goalscorer/*-player-match-logs-*.csv"
DEFAULT_OUT = "data/assist-value/assist-value-shadow-signals.csv"
DEFAULT_REPORT = "data/assist-value/assist-value-model-report.txt"

RECENT_MATCHES = 8
LONG_MATCHES = 40
PLAYER_SHRINK_MINUTES = 900.0
TEAM_RECENT_MATCHES = 8
DEFAULT_EXPECTED_MINUTES = 68.0

LEAGUE_AVG_XG = {
    "serie-a": 1.30,
    "epl": 1.42,
    "la-liga": 1.28,
    "bundesliga": 1.55,
    "ligue-1": 1.36,
}

POSITION_ASSIST_PRIOR_PER90 = {
    "FW": 0.13,
    "FWR": 0.14,
    "FWL": 0.14,
    "AMC": 0.18,
    "AMR": 0.18,
    "AML": 0.18,
    "MC": 0.11,
    "ML": 0.13,
    "MR": 0.13,
    "DMC": 0.07,
    "WB": 0.10,
    "DL": 0.075,
    "DR": 0.075,
    "DC": 0.035,
    "GK": 0.005,
    "Unknown": 0.09,
}

SETTLEMENT_FIELDS = [
    "settled",
    "assists_recorded",
    "bet_outcome",
    "settled_at",
    "pnl_units",
    "settlement_note",
]

OUTPUT_FIELDS = [
    "generated_at",
    "captured_at",
    "match_date",
    "kickoff_at",
    "competition",
    "league_key",
    "home_team",
    "away_team",
    "bookmaker",
    "player_name",
    "model_prob",
    "fair_odds",
    "market_odds",
    "market_prob",
    "edge_pp",
    "ev_pct",
    "signal_status",
    "confidence",
    "player_team",
    "opponent_team",
    "position",
    "expected_minutes",
    "assist_rate_per90",
    "xa_rate_per90",
    "history_minutes",
    "team_attack_scale",
    "setpiece_lambda",
    "corner_share_last5_pct",
    "fk_share_last5_pct",
    "setpiece_share_last5_pct",
    "join_status",
    "notes",
    *SETTLEMENT_FIELDS,
]


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def norm_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("'", "").replace("’", "").replace("‘", "")
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


TEAM_ALIASES = {
    "afc bournemouth": "bournemouth",
    "bournemouth": "bournemouth",
    "arsenal fc": "arsenal",
    "arsenal": "arsenal",
    "aston villa": "aston villa",
    "brentford fc": "brentford",
    "brentford": "brentford",
    "brighton hove albion": "brighton",
    "brighton and hove albion": "brighton",
    "burnley fc": "burnley",
    "burnley": "burnley",
    "chelsea fc": "chelsea",
    "chelsea": "chelsea",
    "crystal palace": "crystal palace",
    "everton fc": "everton",
    "everton": "everton",
    "fulham fc": "fulham",
    "fulham": "fulham",
    "leeds united": "leeds",
    "liverpool fc": "liverpool",
    "liverpool": "liverpool",
    "manchester city": "manchester city",
    "man city": "manchester city",
    "manchester united": "manchester united",
    "man utd": "manchester united",
    "newcastle united": "newcastle united",
    "nottingham forest": "nottingham forest",
    "sunderland afc": "sunderland",
    "sunderland": "sunderland",
    "tottenham hotspur": "tottenham",
    "tottenham": "tottenham",
    "west ham united": "west ham",
    "west ham": "west ham",
    "wolverhampton wanderers": "wolves",
    "wolves": "wolves",
    "inter milano": "inter",
    "inter milan": "inter",
    "internazionale": "inter",
    "hellas verona": "verona",
    "atalanta bc": "atalanta",
    "bologna fc": "bologna",
    "cagliari calcio": "cagliari",
    "fiorentina": "fiorentina",
    "genoa cfc": "genoa",
    "juventus": "juventus",
    "lazio": "lazio",
    "ac milan": "milan",
    "milan": "milan",
    "napoli": "napoli",
    "parma calcio": "parma",
    "roma": "roma",
    "sassuolo calcio": "sassuolo",
    "sassuolo": "sassuolo",
    "torino fc": "torino",
    "torino": "torino",
    "udinese calcio": "udinese",
    "udinese": "udinese",
    "us cremonese": "cremonese",
    "cremonese": "cremonese",
    "us lecce": "lecce",
    "lecce": "lecce",
    "elche cf": "elche",
    "elche": "elche",
    "getafe cf": "getafe",
    "getafe": "getafe",
    "sevilla fc": "sevilla",
    "sevilla": "sevilla",
    "real madrid": "real madrid",
    "fc barcelona": "barcelona",
    "barcelona": "barcelona",
    "real betis seville": "real betis",
    "betis": "real betis",
    "atletico madrid": "atletico madrid",
    "girona fc": "girona",
    "girona": "girona",
    "levante ud": "levante",
    "levante": "levante",
    "rcd mallorca": "mallorca",
    "mallorca": "mallorca",
    "athletic club": "athletic club",
    "athletic bilbao": "athletic club",
    "real sociedad": "real sociedad",
    "valencia cf": "valencia",
    "valencia": "valencia",
    "villarreal cf": "villarreal",
    "villarreal": "villarreal",
    "rayo vallecano": "rayo vallecano",
    "osasuna": "osasuna",
    "ca osasuna": "osasuna",
    "ogc nice": "nice",
    "nice": "nice",
    "fc metz": "metz",
    "metz": "metz",
    "fc lorient": "lorient",
    "lorient": "lorient",
    "le havre ac": "le havre",
    "le havre": "le havre",
    "lille osc": "lille",
    "lille": "lille",
    "aj auxerre": "auxerre",
    "auxerre": "auxerre",
    "stade brest 29": "brest",
    "brest": "brest",
    "angers sco": "angers",
    "angers": "angers",
    "olympique marseille": "marseille",
    "marseille": "marseille",
    "stade rennais fc": "rennes",
    "rennes": "rennes",
    "olympique lyon": "lyon",
    "lyon": "lyon",
    "racing club de lens": "lens",
    "rc lens": "lens",
    "lens": "lens",
    "paris saint germain": "psg",
    "paris sg": "psg",
    "psg": "psg",
    "paris fc": "paris fc",
    "strasbourg alsace": "strasbourg",
    "strasbourg": "strasbourg",
    "as monaco": "monaco",
    "monaco": "monaco",
    "fc nantes": "nantes",
    "nantes": "nantes",
    "toulouse fc": "toulouse",
    "toulouse": "toulouse",
}


def team_key(value: str) -> str:
    normalized = norm_text(value)
    return TEAM_ALIASES.get(normalized, normalized)


def league_from_competition(value: str) -> str:
    text = norm_text(value)
    if "premier league" in text or "england" in text:
        return "epl"
    if "serie a" in text or "italy" in text:
        return "serie-a"
    if "liga" in text or "spain" in text:
        return "la-liga"
    if "bundesliga" in text or "germany" in text:
        return "bundesliga"
    if "ligue 1" in text or "france" in text:
        return "ligue-1"
    return ""


def league_from_path(path: str) -> str:
    name = Path(path).name
    for league in ("serie-a", "la-liga", "bundesliga", "ligue-1", "epl"):
        if name.startswith(f"{league}-"):
            return league
    return ""


def parse_date(value: str) -> datetime | None:
    text = (value or "")[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return None


def parse_float(value: str, default: float = 0.0) -> float:
    try:
        return float(str(value or "").replace(",", "").strip())
    except ValueError:
        return default


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def read_csvs(patterns: Iterable[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for pattern in patterns:
        glob_pattern = str(ROOT / pattern) if not Path(pattern).is_absolute() else pattern
        for path in sorted(glob.glob(glob_pattern)):
            league = league_from_path(path)
            with open(path, newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    cleaned = {key: "" if value is None else str(value) for key, value in row.items()}
                    if league and "league_key" not in cleaned:
                        cleaned["league_key"] = league
                    rows.append(cleaned)
    return rows


def signal_key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        row.get("captured_at", ""),
        row.get("match_date", ""),
        team_key(row.get("home_team", "")),
        team_key(row.get("away_team", "")),
        norm_text(row.get("player_name", "")),
        norm_text(row.get("bookmaker", "")),
        row.get("market_odds", "") or row.get("odds_decimal", ""),
    )


def load_existing_settlement(path: str) -> dict[tuple[str, ...], dict[str, str]]:
    target = ROOT / path if not Path(path).is_absolute() else Path(path)
    if not target.exists():
        return {}
    rows = read_csvs([str(target)])
    carried: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        key = signal_key(row)
        settlement = {field: row.get(field, "") for field in SETTLEMENT_FIELDS}
        if any(value for value in settlement.values()):
            carried[key] = settlement
    return carried


def carry_existing_settlement(rows: list[dict[str, str]], existing: dict[tuple[str, ...], dict[str, str]]) -> None:
    for row in rows:
        settlement = existing.get(signal_key(row), {})
        for field in SETTLEMENT_FIELDS:
            row[field] = settlement.get(field, row.get(field, ""))


def player_prior(position: str) -> float:
    pos = (position or "Unknown").split(",")[0].strip() or "Unknown"
    return POSITION_ASSIST_PRIOR_PER90.get(pos, POSITION_ASSIST_PRIOR_PER90["Unknown"])


def build_indexes(player_logs: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], list[dict]], dict[tuple[str, str], list[dict]]]:
    players: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    team_matches: dict[tuple[str, str], dict[tuple[str, str], dict]] = defaultdict(dict)

    for row in player_logs:
        match_date = parse_date(row.get("match_date", ""))
        if not match_date:
            continue
        league = row.get("league_key", "")
        team = team_key(row.get("team", ""))
        opponent = team_key(row.get("opponent", ""))
        player = norm_text(row.get("player_name", ""))
        if not league or not team or not player:
            continue
        parsed = {
            "match_date": match_date,
            "team": team,
            "opponent": opponent,
            "player": player,
            "player_name": row.get("player_name", ""),
            "position": row.get("position", "") or "Unknown",
            "minutes": parse_float(row.get("minutes", "")),
            "assists": parse_float(row.get("assists", "")),
            "xa": parse_float(row.get("xa", "")),
            "team_xg": parse_float(row.get("team_xg", "")),
            "team_xga": parse_float(row.get("team_xga", "")),
        }
        players[(league, team, player)].append(parsed)
        team_matches[(league, team)][(match_date.strftime("%Y-%m-%d"), opponent)] = parsed

    for values in players.values():
        values.sort(key=lambda item: item["match_date"])

    team_index: dict[tuple[str, str], list[dict]] = {}
    for key, match_map in team_matches.items():
        matches = sorted(match_map.values(), key=lambda item: item["match_date"])
        team_index[key] = matches
    return players, team_index


def latest_before(rows: list[dict], match_date: datetime, limit: int | None = None) -> list[dict]:
    filtered = [row for row in rows if row["match_date"] < match_date]
    if limit:
        return filtered[-limit:]
    return filtered


def player_features(history: list[dict], match_date: datetime) -> dict[str, float | str]:
    prior_position = history[-1]["position"] if history else "Unknown"
    prior = player_prior(str(prior_position))
    before = latest_before(history, match_date, LONG_MATCHES)
    recent = before[-RECENT_MATCHES:]
    if not before:
        return {
            "expected_minutes": DEFAULT_EXPECTED_MINUTES,
            "assist_rate_per90": prior,
            "xa_rate_per90": prior,
            "history_minutes": 0.0,
            "position": prior_position,
        }

    total_minutes = sum(row["minutes"] for row in before)
    recent_minutes = [row["minutes"] for row in recent if row["minutes"] > 0]
    expected_minutes = sum(recent_minutes) / len(recent_minutes) if recent_minutes else DEFAULT_EXPECTED_MINUTES
    expected_minutes = clamp(expected_minutes, 15.0, 90.0)

    assists = sum(row["assists"] for row in before)
    xa = sum(row["xa"] for row in before)
    raw_assist_per90 = assists * 90.0 / total_minutes if total_minutes > 0 else prior
    raw_xa_per90 = xa * 90.0 / total_minutes if total_minutes > 0 else prior
    shrink = total_minutes / (total_minutes + PLAYER_SHRINK_MINUTES)
    assist_per90 = shrink * raw_assist_per90 + (1.0 - shrink) * prior
    xa_per90 = shrink * raw_xa_per90 + (1.0 - shrink) * prior
    return {
        "expected_minutes": expected_minutes,
        "assist_rate_per90": clamp(assist_per90, 0.001, 0.75),
        "xa_rate_per90": clamp(xa_per90, 0.001, 0.75),
        "history_minutes": total_minutes,
        "position": prior_position,
    }


def team_context_scale(
    team_index: dict[tuple[str, str], list[dict]],
    league: str,
    player_team: str,
    opponent_team: str,
    match_date: datetime,
) -> float:
    league_avg = LEAGUE_AVG_XG.get(league, 1.35)
    team_recent = latest_before(team_index.get((league, player_team), []), match_date, TEAM_RECENT_MATCHES)
    opp_recent = latest_before(team_index.get((league, opponent_team), []), match_date, TEAM_RECENT_MATCHES)
    team_xg = sum(row["team_xg"] for row in team_recent) / len(team_recent) if team_recent else league_avg
    opp_xga = sum(row["team_xga"] for row in opp_recent) / len(opp_recent) if opp_recent else league_avg
    attack = clamp(team_xg / league_avg, 0.65, 1.45)
    opponent = clamp(opp_xga / league_avg, 0.70, 1.40)
    return math.sqrt(attack * opponent)


def setpiece_lambda(row: dict[str, str], expected_minutes: float) -> float:
    corner_share = parse_float(row.get("corner_share_last5_pct", "")) / 100.0
    fk_share = parse_float(row.get("fk_share_last5_pct", "")) / 100.0
    setpiece_share = parse_float(row.get("setpiece_share_last5_pct", "")) / 100.0
    if row.get("shadow_status") != "role_matched":
        return 0.0
    minutes_scale = clamp(expected_minutes / 75.0, 0.35, 1.15)
    lam = (0.018 * corner_share) + (0.014 * fk_share) + (0.012 * setpiece_share)
    return clamp(lam * minutes_scale, 0.0, 0.07)


def resolve_player_team(row: dict[str, str], league: str, player_key: str, indexes: dict[tuple[str, str, str], list[dict]]) -> tuple[str, str]:
    home = team_key(row.get("home_team", ""))
    away = team_key(row.get("away_team", ""))
    role_team = team_key(row.get("role_team", ""))
    if role_team in {home, away}:
        return role_team, away if role_team == home else home
    for candidate in (home, away):
        if (league, candidate, player_key) in indexes:
            return candidate, away if candidate == home else home
    return role_team, away if role_team == home else home


def model_row(row: dict[str, str], indexes, team_index, generated_at: str) -> dict[str, str] | None:
    match_date = parse_date(row.get("match_date", ""))
    if not match_date:
        return None
    odds = parse_float(row.get("odds_decimal", ""))
    if odds <= 1.0:
        return None
    league = league_from_competition(row.get("competition", ""))
    player_key = norm_text(row.get("player_name", ""))
    if not league or not player_key:
        return None

    player_team, opponent_team = resolve_player_team(row, league, player_key, indexes)
    history = indexes.get((league, player_team, player_key), [])
    features = player_features(history, match_date)
    team_scale = team_context_scale(team_index, league, player_team, opponent_team, match_date)

    base_per90 = (0.65 * float(features["xa_rate_per90"])) + (0.35 * float(features["assist_rate_per90"]))
    open_play_lambda = base_per90 * (float(features["expected_minutes"]) / 90.0) * team_scale
    sp_lambda = setpiece_lambda(row, float(features["expected_minutes"]))
    total_lambda = clamp(open_play_lambda + sp_lambda, 0.001, 0.45)
    model_prob = clamp(1.0 - math.exp(-total_lambda), 0.001, 0.45)
    market_prob = 1.0 / odds
    edge_pp = 100.0 * (model_prob - market_prob)
    ev_pct = 100.0 * ((model_prob * odds) - 1.0)
    fair_odds = 1.0 / model_prob

    history_minutes = float(features["history_minutes"])
    role_matched = row.get("shadow_status") == "role_matched"
    confidence = "low"
    if history_minutes >= 900 and role_matched:
        confidence = "medium"
    if history_minutes >= 1800 and role_matched and float(features["expected_minutes"]) >= 55:
        confidence = "high"

    if edge_pp >= 4.0 and ev_pct >= 10.0 and confidence in {"medium", "high"} and fair_odds <= 18.0:
        status = "shadow_signal"
    elif edge_pp >= 2.0 and role_matched:
        status = "watch"
    else:
        status = "no_edge"

    return {
        "generated_at": generated_at,
        "captured_at": row.get("captured_at", ""),
        "match_date": row.get("match_date", ""),
        "kickoff_at": row.get("kickoff_at", ""),
        "competition": row.get("competition", ""),
        "league_key": league,
        "home_team": row.get("home_team", ""),
        "away_team": row.get("away_team", ""),
        "bookmaker": row.get("bookmaker", ""),
        "player_name": row.get("player_name", ""),
        "model_prob": f"{model_prob:.6f}",
        "fair_odds": f"{fair_odds:.3f}",
        "market_odds": f"{odds:.3f}",
        "market_prob": f"{market_prob:.6f}",
        "edge_pp": f"{edge_pp:.2f}",
        "ev_pct": f"{ev_pct:.2f}",
        "signal_status": status,
        "confidence": confidence,
        "player_team": player_team,
        "opponent_team": opponent_team,
        "position": str(features["position"]),
        "expected_minutes": f"{float(features['expected_minutes']):.1f}",
        "assist_rate_per90": f"{float(features['assist_rate_per90']):.4f}",
        "xa_rate_per90": f"{float(features['xa_rate_per90']):.4f}",
        "history_minutes": f"{history_minutes:.0f}",
        "team_attack_scale": f"{team_scale:.3f}",
        "setpiece_lambda": f"{sp_lambda:.4f}",
        "corner_share_last5_pct": row.get("corner_share_last5_pct", ""),
        "fk_share_last5_pct": row.get("fk_share_last5_pct", ""),
        "setpiece_share_last5_pct": row.get("setpiece_share_last5_pct", ""),
        "join_status": row.get("join_status", ""),
        "notes": "private_shadow_v0_not_public",
    }


def write_csv(path: str, rows: list[dict[str, str]]) -> Path:
    target = ROOT / path if not Path(path).is_absolute() else Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return target


def write_report(path: str, rows: list[dict[str, str]]) -> Path:
    target = ROOT / path if not Path(path).is_absolute() else Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    signals = [row for row in rows if row["signal_status"] == "shadow_signal"]
    watches = [row for row in rows if row["signal_status"] == "watch"]
    by_league: dict[str, int] = defaultdict(int)
    for row in signals:
        by_league[row["league_key"]] += 1
    lines = [
        "Assist Value Model Report",
        f"generated_at_utc: {now_utc_iso()}",
        "",
        "Status",
        "model_status: ENABLED_SHADOW_V0",
        "public_signal_status: DISABLED",
        "settlement_status: ENABLED_SHADOW_FOTMOB",
        "backtest_status: NOT_BACKTESTED",
        "",
        "Counts",
        f"priced_rows: {len(rows)}",
        f"shadow_signals: {len(signals)}",
        f"watch_rows: {len(watches)}",
        "shadow_signals_by_league: "
        + (", ".join(f"{league}={count}" for league, count in sorted(by_league.items())) or "none"),
        "",
        "Model",
        "p_assist = 1 - exp(-lambda)",
        "lambda = blended player xA/assist rate per90 * expected_minutes * team_attack_scale + setpiece_role_boost",
        "Market probability is 1 / Bet365 decimal odds; no vig adjustment because only one side is available.",
        "",
        "Top shadow signals",
    ]
    for row in signals[:25]:
        lines.append(
            " - "
            f"{row['player_name']} | {row['home_team']} vs {row['away_team']} | "
            f"fair {row['fair_odds']} vs market {row['market_odds']} | "
            f"edge {row['edge_pp']}pp | conf {row['confidence']} | "
            f"setpiece {row['setpiece_share_last5_pct']}"
        )
    if not signals:
        lines.append(" - none")
    lines.extend(
        [
            "",
            "Guardrail",
            "These are private model candidates only. Do not publish until settlement/backtest gates exist.",
        ]
    )
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Build assist-value private model signals")
    parser.add_argument("--board", default=DEFAULT_BOARD)
    parser.add_argument("--player-logs", nargs="+", default=[DEFAULT_PLAYER_LOGS])
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--report-out", default=DEFAULT_REPORT)
    args = parser.parse_args()

    existing_settlement = load_existing_settlement(args.out)
    board_rows = read_csvs([args.board])
    player_logs = read_csvs(args.player_logs)
    indexes, team_index = build_indexes(player_logs)
    generated_at = now_utc_iso()
    rows = [
        modelled
        for row in board_rows
        if (modelled := model_row(row, indexes, team_index, generated_at)) is not None
    ]
    carry_existing_settlement(rows, existing_settlement)
    rows.sort(key=lambda row: (row["signal_status"] == "shadow_signal", parse_float(row["edge_pp"])), reverse=True)
    out_path = write_csv(args.out, rows)
    report_path = write_report(args.report_out, rows)
    print(f"Assist model rows: {len(rows):,}")
    print(f"Shadow signals: {sum(1 for row in rows if row['signal_status'] == 'shadow_signal'):,}")
    print(f"Saved: {out_path}")
    print(f"Saved: {report_path}")


if __name__ == "__main__":
    main()
