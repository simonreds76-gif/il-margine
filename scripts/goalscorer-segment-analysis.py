#!/usr/bin/env python3
"""
Diagnostic segment analysis for the historical goalscorer backtest.

This joins historical ATGS backtest rows to the settled model output so we can
inspect exactly where the model is failing:
  - forwards vs non-forwards
  - shorter odds vs longshots
  - high expected minutes vs lower minutes
  - players with deeper prior match samples
  - model vs fallback rows
  - combinations of the above
"""

from __future__ import annotations

import argparse
import csv
import html
import os
import re
import unicodedata
from collections import defaultdict
from typing import Callable, Dict, List


DEFAULT_BACKTEST = "data/goalscorer/test-run/historical-all/goalscorer-historical-backtest.csv"
DEFAULT_MODEL = "data/goalscorer/goalscorer-backtest-results.csv"
DEFAULT_OUT_DIR = "data/goalscorer/test-run/historical-all"


def _norm_text(value: str) -> str:
    normalized = html.unescape((value or "").strip().lower())
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    cleaned = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", cleaned).strip()


TEAM_ALIASES = {
    "ac milan": "milan",
    "milan": "milan",
    "inter": "inter",
    "inter milan": "inter",
    "internazionale": "inter",
    "as roma": "roma",
    "roma": "roma",
    "ss lazio": "lazio",
    "lazio": "lazio",
    "lazio rome": "lazio",
    "hellas verona": "verona",
    "verona": "verona",
    "juventus": "juventus",
    "juventus fc": "juventus",
    "como 1907": "como",
    "como": "como",
    "us cremonese": "cremonese",
    "cremonese": "cremonese",
    "acf fiorentina": "fiorentina",
    "fiorentina": "fiorentina",
    "cagliari calcio": "cagliari",
    "cagliari": "cagliari",
    "pisa sc": "pisa",
    "pisa": "pisa",
    "sassuolo calcio": "sassuolo",
    "sassuolo": "sassuolo",
    "bologna fc": "bologna",
    "bologna fc 1909": "bologna",
    "bologna": "bologna",
    "atalanta bc": "atalanta",
    "atalanta": "atalanta",
    "empoli fc": "empoli",
    "empoli": "empoli",
    "genoa cfc": "genoa",
    "genoa": "genoa",
    "us lecce": "lecce",
    "lecce": "lecce",
    "ac monza": "monza",
    "monza": "monza",
    "ssc napoli": "napoli",
    "napoli": "napoli",
    "parma calcio 1913": "parma",
    "parma": "parma",
    "torino fc": "torino",
    "torino": "torino",
    "udinese calcio": "udinese",
    "udinese": "udinese",
    "venezia fc": "venezia",
    "venezia": "venezia",
}


def _team_key(name: str) -> str:
    return TEAM_ALIASES.get(_norm_text(name), _norm_text(name))


def _parse_float(value: str, default: float = 0.0) -> float:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _load_csv(path: str) -> List[dict]:
    if not os.path.exists(path):
        raise SystemExit(f"File not found: {path}")
    with open(path, "r", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _join_key(match_date: str, player_name: str, team: str, opponent: str) -> tuple[str, str, str, str]:
    return (
        (match_date or "").strip(),
        _norm_text(player_name),
        _team_key(team),
        _team_key(opponent),
    )


def load_model_meta(path: str) -> Dict[tuple[str, str, str, str], dict]:
    rows = _load_csv(path)
    rows.sort(key=lambda row: ((row.get("match_date") or "").strip(), row.get("player_id") or "", row.get("team") or ""))

    prior_matches_by_player: Dict[str, int] = defaultdict(int)
    prior_minutes_by_player: Dict[str, float] = defaultdict(float)
    meta: Dict[tuple[str, str, str, str], dict] = {}

    for row in rows:
        player_id = (row.get("player_id") or "").strip()
        if not player_id:
            continue
        key = _join_key(row.get("match_date") or "", row.get("player_name") or "", row.get("team") or "", row.get("opponent") or "")
        meta[key] = {
            "player_id": player_id,
            "prior_matches": prior_matches_by_player[player_id],
            "prior_minutes": prior_minutes_by_player[player_id],
            "position_group": (row.get("position_group") or "").strip(),
            "model_method": (row.get("method") or "").strip(),
        }
        prior_matches_by_player[player_id] += 1
        prior_minutes_by_player[player_id] += _parse_float(row.get("expected_minutes"))

    return meta


def load_backtest_rows(path: str, model_meta: Dict[tuple[str, str, str, str], dict], min_ev: float) -> tuple[List[dict], dict]:
    rows = _load_csv(path)
    loaded: List[dict] = []
    stats = {"rows": len(rows), "joined_meta": 0, "missing_meta": 0, "qualified_rows": 0}

    for row in rows:
        ev = _parse_float(row.get("ev"))
        scored = int(_parse_float(row.get("scored")))
        pnl = _parse_float(row.get("pnl"))
        odds_decimal = _parse_float(row.get("odds_decimal"))
        expected_minutes = _parse_float(row.get("expected_minutes"))
        meta = model_meta.get(
            _join_key(
                row.get("match_date") or "",
                row.get("player_name") or "",
                row.get("player_team") or "",
                row.get("opponent") or "",
            )
        )
        if meta is not None:
            stats["joined_meta"] += 1
        else:
            stats["missing_meta"] += 1
            meta = {"prior_matches": 0, "prior_minutes": 0.0, "position_group": row.get("position_group") or "", "model_method": row.get("method") or ""}

        loaded.append(
            {
                "season": (row.get("season") or "").strip(),
                "bookmaker": (row.get("bookmaker") or "").strip(),
                "player_name": (row.get("player_name") or "").strip(),
                "player_team": (row.get("player_team") or "").strip(),
                "position_group": (row.get("position_group") or meta["position_group"] or "").strip(),
                "minutes_band": (row.get("minutes_band") or "").strip(),
                "odds_decimal": odds_decimal,
                "expected_minutes": expected_minutes,
                "ev": ev,
                "pnl": pnl,
                "scored": scored,
                "method": (row.get("method") or meta["model_method"] or "").strip(),
                "penalty_role": (row.get("penalty_role") or "").strip(),
                "prior_matches": int(meta["prior_matches"]),
                "prior_minutes": float(meta["prior_minutes"]),
                "qualified": ev >= min_ev,
            }
        )
        if ev >= min_ev:
            stats["qualified_rows"] += 1

    return loaded, stats


def _summarize(rows: List[dict], min_ev: float) -> dict:
    qualified = [row for row in rows if row["qualified"]]
    resolved = [row for row in qualified if row["scored"] in (0, 1)]
    return {
        "rows": len(rows),
        "qualified_rows": len(qualified),
        "qualified_pct": (len(qualified) / len(rows)) if rows else 0.0,
        "avg_ev": (sum(row["ev"] for row in qualified) / len(qualified)) if qualified else 0.0,
        "avg_odds": (sum(row["odds_decimal"] for row in qualified) / len(qualified)) if qualified else 0.0,
        "avg_expected_minutes": (sum(row["expected_minutes"] for row in qualified) / len(qualified)) if qualified else 0.0,
        "avg_prior_matches": (sum(row["prior_matches"] for row in qualified) / len(qualified)) if qualified else 0.0,
        "resolved_rows": len(resolved),
        "roi": (sum(row["pnl"] for row in resolved) / len(resolved)) if resolved else 0.0,
        "win_rate": (sum(row["scored"] for row in resolved) / len(resolved)) if resolved else 0.0,
        "min_ev_threshold": min_ev,
    }


def run_segments(rows: List[dict], min_ev: float) -> List[dict]:
    segments: List[tuple[str, Callable[[dict], bool]]] = [
        ("all_rows", lambda row: True),
        ("fw_only", lambda row: row["position_group"].startswith("FW")),
        ("non_fw", lambda row: not row["position_group"].startswith("FW")),
        ("model_only", lambda row: row["method"] == "model"),
        ("fallback_only", lambda row: row["method"] == "fallback"),
        ("odds_lt_4", lambda row: row["odds_decimal"] < 4.0),
        ("odds_4_to_8", lambda row: 4.0 <= row["odds_decimal"] < 8.0),
        ("odds_8_plus", lambda row: row["odds_decimal"] >= 8.0),
        ("exp_minutes_80_plus", lambda row: row["expected_minutes"] >= 80.0),
        ("exp_minutes_60_plus", lambda row: row["expected_minutes"] >= 60.0),
        ("prior_matches_20_plus", lambda row: row["prior_matches"] >= 20),
        ("prior_matches_10_plus", lambda row: row["prior_matches"] >= 10),
        ("fw_odds_lt_4", lambda row: row["position_group"].startswith("FW") and row["odds_decimal"] < 4.0),
        ("fw_exp_minutes_80_plus", lambda row: row["position_group"].startswith("FW") and row["expected_minutes"] >= 80.0),
        ("fw_prior_matches_20_plus", lambda row: row["position_group"].startswith("FW") and row["prior_matches"] >= 20),
        (
            "fw_under4_minutes80_prior20",
            lambda row: row["position_group"].startswith("FW")
            and row["odds_decimal"] < 4.0
            and row["expected_minutes"] >= 80.0
            and row["prior_matches"] >= 20,
        ),
        (
            "fw_under8_minutes80_prior20",
            lambda row: row["position_group"].startswith("FW")
            and row["odds_decimal"] < 8.0
            and row["expected_minutes"] >= 80.0
            and row["prior_matches"] >= 20,
        ),
    ]

    results: List[dict] = []
    for segment_name, predicate in segments:
        subset = [row for row in rows if predicate(row)]
        summary = _summarize(subset, min_ev)
        results.append({"segment": segment_name, **summary})
    return results


def write_outputs(stats: dict, segments: List[dict], out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "goalscorer-segment-analysis.csv")
    txt_path = os.path.join(out_dir, "goalscorer-segment-analysis.txt")

    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(segments[0].keys()))
        writer.writeheader()
        writer.writerows(segments)

    with open(txt_path, "w", encoding="utf-8") as handle:
        handle.write("Goalscorer Segment Analysis\n")
        handle.write("==========================\n\n")
        handle.write(f"Rows loaded:        {stats['rows']:,}\n")
        handle.write(f"Joined model meta:  {stats['joined_meta']:,}\n")
        handle.write(f"Missing model meta: {stats['missing_meta']:,}\n")
        handle.write(f"Qualified rows:     {stats['qualified_rows']:,}\n\n")
        handle.write(f"{'Segment':<28} {'Qual':>6} {'ROI':>10} {'Avg EV':>10} {'Avg Odds':>10} {'Win%':>8} {'PriorM':>8}\n")
        for row in segments:
            handle.write(
                f"{row['segment']:<28} {row['qualified_rows']:>6} {row['roi']:>10.4f} "
                f"{row['avg_ev']:>10.4f} {row['avg_odds']:>10.2f} {row['win_rate']:>8.3f} {row['avg_prior_matches']:>8.1f}\n"
            )

    print(f"  Saved: {csv_path}")
    print(f"  Saved: {txt_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose historical goalscorer backtest segments")
    parser.add_argument("--backtest", default=DEFAULT_BACKTEST, help="Historical backtest CSV")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Settled model results CSV")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--min-ev", type=float, default=0.05, help="Minimum EV threshold")
    args = parser.parse_args()

    print("\n" + "=" * 64)
    print("  IL MARGINE - Goalscorer Segment Analysis")
    print("=" * 64)

    model_meta = load_model_meta(args.model)
    rows, stats = load_backtest_rows(args.backtest, model_meta, args.min_ev)
    segments = run_segments(rows, args.min_ev)

    print(f"  Rows loaded:        {stats['rows']:,}")
    print(f"  Joined model meta:  {stats['joined_meta']:,}")
    print(f"  Missing model meta: {stats['missing_meta']:,}")
    print(f"  Qualified rows:     {stats['qualified_rows']:,}")
    for row in segments:
        print(
            f"  {row['segment']:<26} "
            f"qual={row['qualified_rows']:<5} "
            f"roi={row['roi']:+.4f} "
            f"avg_ev={row['avg_ev']:+.4f}"
        )

    write_outputs(stats, segments, args.out_dir)
    print("\n  Done.\n")


if __name__ == "__main__":
    main()
