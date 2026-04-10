#!/usr/bin/env python3
"""
Build team total shots estimates for upcoming fixtures (Big 5).

Uses the same rolling EMA + Poisson logic as team-shots-model.py, with team
names aligned to historical data via the same normalisation as matchday-shortlist.

Outputs:
  data/team-shots/team-shots-upcoming.csv

Usage:
  python scripts/team_shots_upcoming.py
  python scripts/team_shots_upcoming.py --days-ahead 7
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

DEFAULT_OUT = ROOT / "data" / "team-shots" / "team-shots-upcoming.csv"

DISPLAY_LINES = [9.5, 10.5, 11.5, 12.5, 13.5]
SUPPORTED_LIVE_LEAGUES = {"epl", "serie-a", "la-liga", "bundesliga"}


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
    args = parser.parse_args()

    tsm = _load_module("team_shots_model", ROOT / "scripts" / "team-shots-model.py")
    msl = _load_module("matchday_shortlist", ROOT / "scripts" / "matchday-shortlist.py")
    normalize_team = msl.normalize_team

    from the_odds_api_client import OddsApiClient, SPORT_KEYS

    fbref_path = tsm.DEFAULT_FBREF
    if fbref_path.exists():
        matches = tsm.load_fbref_matches(fbref_path)
    else:
        matches = tsm.load_matches(tsm.DEFAULT_INPUT)

    team_states: Dict[str, tsm.TeamState] = defaultdict(tsm.TeamState)
    league_avgs = tsm.compute_league_avg(matches)

    for m in matches:
        league_avg = league_avgs.get(m.league, tsm.DEFAULT_BASELINE)
        hk = f"{m.league}:{normalize_team(m.home_team)}"
        ak = f"{m.league}:{normalize_team(m.away_team)}"
        hs = team_states[hk]
        as_ = team_states[ak]
        hs.add_match(
            m.home_shots, m.home_sot, m.away_shots, m.away_sot,
            m.home_corners, m.home_goals, m.away_goals,
            xg=m.home_xg, conc_xg=m.away_xg,
        )
        as_.add_match(
            m.away_shots, m.away_sot, m.home_shots, m.home_sot,
            m.away_corners, m.away_goals, m.home_goals,
            xg=m.away_xg, conc_xg=m.home_xg,
        )

    try:
        client = OddsApiClient()
    except RuntimeError as e:
        print(f"ERROR: {e}")
        return

    cutoff = datetime.now(timezone.utc) + timedelta(days=args.days_ahead)
    rows_out: List[Dict[str, Any]] = []

    for league, sport_key in SPORT_KEYS.items():
        if league not in SUPPORTED_LIVE_LEAGUES:
            continue
        events = client.get_upcoming_events(sport_key)
        for ev in events:
            ko = ev.get("commence_time", "")
            try:
                ko_dt = datetime.fromisoformat(ko.replace("Z", "+00:00"))
                if ko_dt > cutoff:
                    continue
            except (ValueError, TypeError):
                pass

            home_raw = ev.get("home_team", "")
            away_raw = ev.get("away_team", "")
            hk = f"{league}:{normalize_team(home_raw)}"
            ak = f"{league}:{normalize_team(away_raw)}"
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
                    "note": "insufficient_ema",
                })
                continue

            h_lam, _ = home_res
            a_lam, _ = away_res
            row: Dict[str, Any] = {
                "league": league,
                "kickoff_iso": ko,
                "home_team": home_raw,
                "away_team": away_raw,
                "home_lambda": round(h_lam, 2),
                "away_lambda": round(a_lam, 2),
                "note": "",
            }
            for line in DISPLAY_LINES:
                p_h = tsm.prob_over(line, h_lam)
                p_a = tsm.prob_over(line, a_lam)
                row[f"home_p_over_{line}"] = round(p_h, 4)
                row[f"home_fair_over_{line}"] = tsm.fair_odds(p_h)
                row[f"home_fair_under_{line}"] = tsm.fair_odds(1.0 - p_h)
                row[f"away_p_over_{line}"] = round(p_a, 4)
                row[f"away_fair_over_{line}"] = tsm.fair_odds(p_a)
                row[f"away_fair_under_{line}"] = tsm.fair_odds(1.0 - p_a)
            rows_out.append(row)

    rows_out.sort(key=lambda r: (r.get("kickoff_iso") or "", r.get("league") or ""))

    fields = [
        "league", "kickoff_iso", "home_team", "away_team",
        "home_lambda", "away_lambda", "note",
    ]
    for line in DISPLAY_LINES:
        fields.extend([
            f"home_p_over_{line}", f"home_fair_over_{line}", f"home_fair_under_{line}",
            f"away_p_over_{line}", f"away_fair_over_{line}", f"away_fair_under_{line}",
        ])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows_out)

    print(f"Wrote {len(rows_out)} upcoming rows -> {args.output}")
    credits = client.get_credits_remaining()
    if credits is not None:
        print(f"Odds API credits remaining: {credits}")


if __name__ == "__main__":
    main()
