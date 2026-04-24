#!/usr/bin/env python3
"""
Audit tennis ML blend calibration from existing backtest result CSVs.

Important: backtest-results rows are oriented as player1 = actual winner and
player2 = actual loser. This script therefore evaluates "probability assigned
to the eventual winner" and symmetric loser-side EV, instead of fitting a naive
y=0/1 regression on the row as-is.

Outputs:
  data/backtest/ml-blend-calibration-audit.txt
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "data" / "backtest" / "ml-blend-calibration-audit.txt"
BACKTEST_FILES = [ROOT / "data" / "backtest" / f"backtest-results-{year}.csv" for year in (2022, 2023, 2024, 2025)]


def _float(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _logit(p: float) -> float:
    p = max(1e-6, min(1.0 - 1e-6, p))
    return math.log(p / (1.0 - p))


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, z))))


def _temperature(p: float, slope: float) -> float:
    return _sigmoid(slope * _logit(p))


def _winner_log_loss(p_winner: float) -> float:
    return -math.log(max(1e-6, min(1.0 - 1e-6, p_winner)))


def load_rows() -> list[dict]:
    rows: list[dict] = []
    for path in BACKTEST_FILES:
        year = int(path.stem.split("-")[-1])
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            for raw in csv.DictReader(f):
                p_sr = _float(raw.get("p_serve_return"))
                p_elo = _float(raw.get("p_elo"))
                p_rank = _float(raw.get("p_rank"))
                odds_winner = _float(raw.get("pinnacle_odds"))
                odds_loser = _float(raw.get("pinnacle_odds_loser"))
                if p_sr is None or p_elo is None or odds_winner is None or odds_loser is None:
                    continue
                if odds_winner <= 1.0 or odds_loser <= 1.0:
                    continue
                implied_w = 1.0 / odds_winner
                implied_l = 1.0 / odds_loser
                rows.append({
                    "year": year,
                    "surface": raw.get("surface") or "",
                    "series": raw.get("series") or "",
                    "confidence": raw.get("confidence") or "",
                    "p_sr": p_sr,
                    "p_elo": p_elo,
                    "p_rank": p_rank,
                    "odds_winner": odds_winner,
                    "odds_loser": odds_loser,
                    "market_p_winner": implied_w / (implied_w + implied_l),
                    "our_prob": _float(raw.get("our_prob")),
                    "our_prob_raw": _float(raw.get("our_prob_raw")),
                })
    return rows


def blend_prob_winner(row: dict, ws: float, we: float, wr: float, sr_cap: float | None, temp_slope: float) -> float:
    p_sr = float(row["p_sr"])
    if sr_cap is not None:
        p_sr = max(0.5 - sr_cap, min(0.5 + sr_cap, p_sr))

    pairs = [(ws, _logit(p_sr)), (we, _logit(float(row["p_elo"])))]
    if row.get("p_rank") is not None:
        pairs.append((wr, _logit(float(row["p_rank"]))))

    total_w = sum(w for w, _ in pairs)
    p = _sigmoid(sum(w * z for w, z in pairs) / total_w) if total_w > 0 else 0.5
    return _temperature(p, temp_slope)


def metrics(rows: list[dict], probs: list[float]) -> tuple[float, float]:
    n = max(1, len(rows))
    log_loss = sum(_winner_log_loss(p) for p in probs) / n
    brier = sum((1.0 - p) ** 2 for p in probs) / n
    return log_loss, brier


def roi(
    rows: list[dict],
    probs: list[float],
    *,
    edge: float = 0.10,
    max_fav_gap: float | None = 0.10,
    surface: str | None = None,
    confidence: set[str] | None = {"high", "medium"},
) -> dict:
    n = 0
    winner_bets = 0
    loser_bets = 0
    pnl = 0.0
    for row, p_winner in zip(rows, probs):
        if confidence and row.get("confidence") not in confidence:
            continue
        if surface and row.get("surface") != surface:
            continue
        p_loser = 1.0 - p_winner
        model_fav = max(p_winner, p_loser)
        market_fav = max(float(row["market_p_winner"]), 1.0 - float(row["market_p_winner"]))
        if max_fav_gap is not None and abs(model_fav - market_fav) > max_fav_gap:
            continue
        ev_winner = p_winner * float(row["odds_winner"]) - 1.0
        ev_loser = p_loser * float(row["odds_loser"]) - 1.0
        if max(ev_winner, ev_loser) < edge:
            continue
        n += 1
        if ev_winner >= ev_loser:
            winner_bets += 1
            pnl += float(row["odds_winner"]) - 1.0
        else:
            loser_bets += 1
            pnl -= 1.0
    return {
        "n": n,
        "winner_bets": winner_bets,
        "loser_bets": loser_bets,
        "pnl": round(pnl, 2),
        "roi": round(pnl / n, 4) if n else None,
    }


def stored_probs(rows: list[dict], column: str, temp_slope: float = 1.0) -> list[float]:
    out = []
    for row in rows:
        value = row.get(column)
        out.append(_temperature(float(value), temp_slope) if value is not None else 0.5)
    return out


def write_line(lines: list[str], text: str = "") -> None:
    lines.append(text)


def main() -> int:
    rows = load_rows()
    train = [r for r in rows if int(r["year"]) <= 2024]
    test = [r for r in rows if int(r["year"]) == 2025]
    lines: list[str] = []

    write_line(lines, "ML Blend Calibration Audit")
    write_line(lines, "==========================")
    write_line(lines, "Rows are oriented as player1=actual winner; metrics are probability assigned to the winner.")
    write_line(lines, f"Rows: {len(rows):,} | train 2022-2024: {len(train):,} | validation 2025: {len(test):,}")
    write_line(lines)

    for column in ("our_prob_raw", "our_prob"):
        p_train = stored_probs(train, column)
        p_test = stored_probs(test, column)
        write_line(lines, f"Stored {column}")
        write_line(lines, f"  train logloss/brier: {metrics(train, p_train)}")
        write_line(lines, f"  2025  logloss/brier: {metrics(test, p_test)}")
        write_line(lines, f"  2025 edge>=10 gap<=10 all:  {roi(test, p_test)}")
        write_line(lines, f"  2025 edge>=10 gap<=10 clay: {roi(test, p_test, surface='Clay')}")

        candidates = []
        for slope_i in range(50, 151, 5):
            slope = slope_i / 100.0
            pt = stored_probs(train, column, slope)
            pv = stored_probs(test, column, slope)
            candidates.append((metrics(train, pt)[0], metrics(test, pv)[0], slope, roi(test, pv), roi(test, pv, surface="Clay")))
        write_line(lines, "  best symmetric temperatures by train logloss:")
        for item in sorted(candidates)[:5]:
            write_line(lines, f"    train_ll={item[0]:.4f} test_ll={item[1]:.4f} slope={item[2]:.2f} all10={item[3]} clay10={item[4]}")
        write_line(lines)

    grid = []
    for sr_cap in (0.30, 0.25, 0.20, 0.15):
        for ws in (0.05, 0.10, 0.15, 0.20, 0.25):
            for we in (0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75):
                wr = 1.0 - ws - we
                if wr < 0.0 or wr > 0.45:
                    continue
                for slope in (0.75, 0.85, 0.95, 1.05, 1.15):
                    p_train = [blend_prob_winner(r, ws, we, wr, sr_cap, slope) for r in train]
                    p_test = [blend_prob_winner(r, ws, we, wr, sr_cap, slope) for r in test]
                    tr_ll, tr_brier = metrics(train, p_train)
                    te_ll, te_brier = metrics(test, p_test)
                    grid.append({
                        "train_ll": tr_ll,
                        "test_ll": te_ll,
                        "train_brier": tr_brier,
                        "test_brier": te_brier,
                        "params": (ws, we, wr, sr_cap, slope),
                        "all10": roi(test, p_test),
                        "clay10": roi(test, p_test, surface="Clay"),
                    })

    write_line(lines, "Grid Candidates")
    write_line(lines, "---------------")
    write_line(lines, "Best by train logloss:")
    for item in sorted(grid, key=lambda x: x["train_ll"])[:10]:
        write_line(
            lines,
            f"  train_ll={item['train_ll']:.4f} test_ll={item['test_ll']:.4f} "
            f"test_brier={item['test_brier']:.4f} params={item['params']} "
            f"all10={item['all10']} clay10={item['clay10']}"
        )
    write_line(lines)
    write_line(lines, "Best 2025 clay ROI candidates with n>=40 (diagnostic, not production selection):")
    clay_items = [x for x in grid if x["clay10"]["n"] >= 40 and x["clay10"]["roi"] is not None]
    for item in sorted(clay_items, key=lambda x: -float(x["clay10"]["roi"]))[:10]:
        write_line(
            lines,
            f"  train_ll={item['train_ll']:.4f} test_ll={item['test_ll']:.4f} "
            f"params={item['params']} all10={item['all10']} clay10={item['clay10']}"
        )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
