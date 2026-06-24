#!/usr/bin/env python3
"""Lagged grass CPI research report.

This is a diagnostic, not a betting engine. It compares same-season CPI
(leaky, for measuring contamination only) with prior-edition lagged CPI.
"""

from __future__ import annotations

import csv
import math
import random
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BT = ROOT / "data" / "backtest"
SPEED_CSV = BT / "tennisabstract-atp-surface-speed.csv"
OUT_TXT = BT / "grass-cpi-research-report.txt"
OUT_CSV = BT / "grass-cpi-cells.csv"

YEARS = [2022, 2023, 2024, 2025]
VALUE_BANDS = [(5, 10), (10, 15), (15, 20), (20, 30), (30, 10_000)]
SLOW_MAX = 1.05
FAST_MIN = 1.15
LAG_YEARS = 3

random.seed(29)

ALIASES = {
    "cinch championships": "queen s club",
    "london queens club": "queen s club",
    "queen s club championships": "queen s club",
    "queens club championships": "queen s club",
    "terra wortmann open": "halle",
    "noventi open": "halle",
    "halle open": "halle",
    "b oss open": "stuttgart",
    "boss open": "stuttgart",
    "mercedes cup": "stuttgart",
    "stuttgart open": "stuttgart",
    "libema open": "s hertogenbosch",
    "rosmalen grass court championships": "s hertogenbosch",
    "s hertogenbosch": "s hertogenbosch",
    "hertogenbosch": "s hertogenbosch",
    "eastbourne international": "eastbourne",
    "mallorca championships": "mallorca",
    "hall of fame championships": "newport",
    "wimbledon": "wimbledon",
}


def tour_key(name: str | None) -> str:
    core = (name or "").strip().lower()
    core = re.sub(r"\b\d{4}\b", " ", core)
    core = re.sub(r"\b(challenger|qualifiers?|qualifying|qualification|atp|wta)\b", " ", core)
    core = re.sub(r"[^a-z0-9]+", " ", core)
    return " ".join(core.split())


def key_candidates(name: str | None) -> list[str]:
    base = tour_key(name)
    raw_parts = [p.strip() for p in re.split(r"\s*-\s*", (name or "").lower()) if p.strip()]
    keys = [base]
    keys.extend(tour_key(p) for p in raw_parts)
    if "queen" in base and "club" in base:
        keys.append("queen s club")
    if "hertogenbosch" in base or "rosmalen" in base:
        keys.append("s hertogenbosch")
    for token in ("halle", "stuttgart", "eastbourne", "mallorca", "newport", "wimbledon"):
        if token in base:
            keys.append(token)
    expanded: list[str] = []
    for key in keys:
        if key:
            expanded.append(key)
            expanded.append(ALIASES.get(key, ""))
    seen = set()
    out = []
    for key in expanded:
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def fnum(value: str | None) -> float | None:
    try:
        v = float(value or "")
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def load_cpi() -> dict[tuple[int, str], float]:
    lookup: dict[tuple[int, str], float] = {}
    if not SPEED_CSV.exists():
        return lookup
    with SPEED_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if (row.get("surface") or "") != "Grass":
                continue
            try:
                year = int(row.get("season_year") or 0)
            except ValueError:
                continue
            key = tour_key(row.get("tournament_key") or row.get("tournament_name"))
            cpi = fnum(row.get("cpi") or row.get("ta_surface_speed"))
            if year > 0 and key and cpi is not None:
                lookup[(year, key)] = cpi
    return lookup


def resolve_cpi(cpi: dict[tuple[int, str], float], year: int, tournament: str, mode: str) -> tuple[float | None, str]:
    keys = key_candidates(tournament)
    if mode == "same_year":
        for key in keys:
            value = cpi.get((year, key))
            if value is not None:
                return value, key
        return None, ""

    values: list[float] = []
    found_key = ""
    for key in keys:
        years = sorted((y for (y, k), _ in cpi.items() if k == key and y <= year - 1), reverse=True)
        if years:
            for y in years[:LAG_YEARS]:
                values.append(cpi[(y, key)])
            found_key = key
            break
    if not values:
        return None, ""
    return sum(values) / len(values), found_key


def bucket(cpi_value: float) -> str:
    if cpi_value < SLOW_MAX:
        return "slow"
    if cpi_value >= FAST_MIN:
        return "fast"
    return "neutral"


def value_band(value_pct: float) -> str:
    for lo, hi in VALUE_BANDS:
        if lo <= value_pct < hi:
            return f"{lo}-{hi if hi < 999 else 'plus'}"
    return "other"


def load_bets() -> list[dict]:
    bets: list[dict] = []
    for year in YEARS:
        path = BT / f"backtest-results-{year}.csv"
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("surface") != "Grass":
                    continue
                if (row.get("series") or "") == "Grand Slam":
                    continue
                if (row.get("confidence") or "").strip().lower() not in {"high", "medium"}:
                    continue
                if str(row.get("policy_excluded")).strip().lower() in {"true", "1", "yes"}:
                    continue
                if row.get("bet_result") not in {"win", "loss"}:
                    continue
                value_pct = fnum(row.get("value_pct"))
                if value_pct is None or value_pct < 5:
                    continue
                win_odds = fnum(row.get("pinnacle_odds"))
                lose_odds = fnum(row.get("pinnacle_odds_loser"))
                if not win_odds or not lose_odds or win_odds <= 1.0 or lose_odds <= 1.0:
                    continue
                bet_odds = win_odds if row.get("bet_side") == "winner" else lose_odds
                won = row.get("bet_result") == "win"
                bets.append(
                    {
                        "year": year,
                        "tournament": row.get("tournament") or "",
                        "series": row.get("series") or "",
                        "confidence": (row.get("confidence") or "").strip().lower(),
                        "value_pct": value_pct,
                        "value_band": value_band(value_pct),
                        "won": won,
                        "pnl": (bet_odds - 1.0) if won else -1.0,
                    }
                )
    return bets


def metrics(rows: list[dict]) -> dict:
    n = len(rows)
    if n == 0:
        return {"n": 0, "pnl": 0.0, "roi_pct": 0.0, "wr_pct": 0.0, "p_roi_le_0": 1.0}
    pnl = sum(float(r["pnl"]) for r in rows)
    pnls = [float(r["pnl"]) for r in rows]
    sims = []
    for _ in range(2000):
        sims.append(sum(random.choice(pnls) for _ in range(n)) / n)
    sims.sort()
    by_year = defaultdict(lambda: [0, 0.0])
    by_tourn = defaultdict(lambda: [0, 0.0])
    for r in rows:
        by_year[r["year"]][0] += 1
        by_year[r["year"]][1] += float(r["pnl"])
        by_tourn[r["tournament"]][0] += 1
        by_tourn[r["tournament"]][1] += float(r["pnl"])
    top_t = max(by_tourn.items(), key=lambda kv: kv[1][1]) if by_tourn else ("", [0, 0.0])
    return {
        "n": n,
        "pnl": pnl,
        "roi_pct": 100.0 * pnl / n,
        "wr_pct": 100.0 * sum(1 for r in rows if r["won"]) / n,
        "p_roi_le_0": sum(1 for s in sims if s <= 0.0) / len(sims),
        "ci_low_pct": 100.0 * sims[int(0.025 * len(sims))],
        "ci_high_pct": 100.0 * sims[int(0.975 * len(sims))],
        "years": "; ".join(f"{y}:{v[1]:+.1f}u/{v[0]}" for y, v in sorted(by_year.items())),
        "pos_years": sum(1 for _, v in by_year.items() if v[0] > 0 and v[1] > 0),
        "top_tournament": top_t[0],
        "top_tournament_pnl": top_t[1][1],
        "top_tournament_n": top_t[1][0],
    }


def main() -> None:
    cpi = load_cpi()
    bets = load_bets()
    enriched: list[dict] = []
    missing = defaultdict(int)
    for bet in bets:
        for mode in ("same_year", "lagged"):
            cpi_value, cpi_key = resolve_cpi(cpi, int(bet["year"]), str(bet["tournament"]), mode)
            if cpi_value is None:
                missing[mode] += 1
                continue
            enriched.append({**bet, "mode": mode, "cpi": cpi_value, "cpi_key": cpi_key, "cpi_bucket": bucket(cpi_value)})

    cells: list[dict] = []
    for mode in ("same_year", "lagged"):
        mode_rows = [r for r in enriched if r["mode"] == mode]
        for label, rows in [
            ("all_value_5_plus", mode_rows),
            ("value_10_plus", [r for r in mode_rows if r["value_pct"] >= 10]),
        ]:
            m = metrics(rows)
            cells.append({"mode": mode, "cell": label, "bucket": "all", **m, "missing_cpi": missing[mode]})
        for b in ("slow", "neutral", "fast"):
            rows = [r for r in mode_rows if r["value_pct"] >= 10 and r["cpi_bucket"] == b]
            m = metrics(rows)
            cells.append({"mode": mode, "cell": "value_10_plus", "bucket": b, **m, "missing_cpi": missing[mode]})
        for band in ("5-10", "10-15", "15-20", "20-30", "30-plus"):
            rows = [r for r in mode_rows if r["value_band"] == band]
            m = metrics(rows)
            cells.append({"mode": mode, "cell": f"value_band_{band}", "bucket": "all", **m, "missing_cpi": missing[mode]})

    fields = [
        "mode",
        "cell",
        "bucket",
        "n",
        "pnl",
        "roi_pct",
        "wr_pct",
        "p_roi_le_0",
        "ci_low_pct",
        "ci_high_pct",
        "pos_years",
        "years",
        "top_tournament",
        "top_tournament_pnl",
        "top_tournament_n",
        "missing_cpi",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in cells:
            w.writerow({k: row.get(k, "") for k in fields})

    lines = [
        "Grass CPI Research Report",
        "=========================",
        "",
        "Scope: ATP grass warm-up matches only, Grand Slam excluded, high/medium confidence, settled backtest rows.",
        "same_year is a leakage diagnostic only. lagged uses prior completed editions only.",
        f"Bucket rules: slow < {SLOW_MAX:.2f}; neutral {SLOW_MAX:.2f}-{FAST_MIN:.2f}; fast >= {FAST_MIN:.2f}.",
        f"Loaded bets: {len(bets)}; CPI rows: {len(cpi)}; lag years: {LAG_YEARS}.",
        "",
    ]
    for row in cells:
        if row["cell"] != "value_10_plus":
            continue
        lines.append(
            f"{row['mode']:<9} {row['bucket']:<7} n={row['n']:<4} ROI={row['roi_pct']:+6.1f}% "
            f"WR={row['wr_pct']:5.1f}% P(<=0)={row['p_roi_le_0']:.2f} "
            f"CI=[{row.get('ci_low_pct', 0):+.1f}%,{row.get('ci_high_pct', 0):+.1f}%] "
            f"years={row.get('years', '')}"
        )
    lines.extend(
        [
            "",
            "Decision rule:",
            "- Ignore same_year for promotion; it can read the current event.",
            "- Treat lagged cells with n<60 as informational only.",
            "- 2026 grass remains shadow-only until lagged backtest plus live CLV clear the promotion bars.",
        ]
    )
    OUT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_TXT}")
    print(f"Wrote {OUT_CSV}")


if __name__ == "__main__":
    main()
