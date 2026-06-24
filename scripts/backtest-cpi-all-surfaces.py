#!/usr/bin/env python3
"""All-surface lagged CPI diagnostics for ATP fair-odds backtests.

This script does not create picks. It answers one question:
where does prior-edition venue speed separate profitable and losing cells?

Rules:
  - lagged mode uses only CPI rows from years <= match_year - 1.
  - same_year mode is emitted only as a leakage diagnostic.
  - buckets are within-surface z-score buckets, not raw CPI thresholds.
"""

from __future__ import annotations

import csv
import math
import random
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BT = ROOT / "data" / "backtest"
SPEED_CSV = BT / "tennisabstract-atp-surface-speed.csv"
OUT_TXT = BT / "cpi-all-surfaces-report.txt"
OUT_CSV = BT / "cpi-all-surfaces-cells.csv"

YEARS = [2022, 2023, 2024, 2025]
LAG_YEARS = 3
VALUE_MIN = 5.0
VALUE_REPORT_MIN = 10.0
BUCKET_Z = 0.50
CPI_MIN = 0.25
CPI_MAX = 1.75
BOOTSTRAP_SIMS = 500

random.seed(41)

TOURNAMENT_ALIASES = {
    # Slams.
    "french open": "roland garros",
    "us open": "us open",
    "u s open": "us open",
    "australian open": "australian open",
    "wimbledon": "wimbledon",
    # Grass
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
    # Common sponsor/venue variants.
    "mutua madrid open": "madrid masters",
    "madrid": "madrid masters",
    "internazionali bnl d italia": "rome masters",
    "italian open": "rome masters",
    "rome": "rome masters",
    "western southern open": "cincinnati masters",
    "western and southern open": "cincinnati masters",
    "western southern financial group masters": "cincinnati masters",
    "western and southern financial group masters": "cincinnati masters",
    "cincinnati": "cincinnati masters",
    "cincinnati open": "cincinnati masters",
    "bnp paribas open": "indian wells masters",
    "indian wells": "indian wells masters",
    "miami open": "miami masters",
    "miami": "miami masters",
    "national bank open": "canada masters",
    "canadian open": "canada masters",
    "rogers cup": "canada masters",
    "monte carlo": "monte carlo masters",
    "rolex monte carlo masters": "monte carlo masters",
    "hamburg european open": "hamburg",
    "hamburg open": "hamburg",
    "barcelona open": "barcelona",
    "bmw open": "munich",
    "nordea open": "bastad",
    "grand prix hassan ii": "marrakech",
    "generali open": "kitzbuhel",
    "u s men s clay court championships": "houston",
    "suisse open gstaad": "gstaad",
    "chile open": "santiago",
    "croatia open": "umag",
    "lyon open": "lyon",
    "cordoba open": "cordoba",
    "estoril open": "estoril",
    "millennium estoril open": "estoril",
    "tiriac open": "bucharest",
    "rio open": "rio de janeiro",
    "argentina open": "buenos aires",
    "china open": "beijing",
    "japan open": "tokyo",
    "japan open tennis championships": "tokyo",
    "rakuten japan open tennis championships": "tokyo",
    "qatar exxonmobil open": "doha",
    "qatar exxon mobil open": "doha",
    "dubai duty free tennis championships": "dubai",
    "dubai tennis championships": "dubai",
    "abn amro open": "rotterdam",
    "abn amro world tennis tournament": "rotterdam",
    "erste bank open": "vienna",
    "vienna open": "vienna",
    "swiss indoors": "basel",
    "abierto mexicano": "acapulco",
    "citi open": "washington",
    "winston salem open at wake forest university": "salem",
    "winston salem open": "salem",
    "winston salem": "salem",
    "open 13": "marseille",
    "open sud de france": "montpellier",
    "open de moselle": "metz",
    "nordic open": "stockholm",
    "atlanta open": "atlanta",
    "chengdu open": "chengdu",
    "asb classic": "auckland",
    "astana open": "astana",
    "brisbane international": "brisbane",
    "adelaide international 1": "adelaide 1",
    "adelaide international 2": "adelaide 2",
    "adelaide international": "adelaide",
    "maharashtra open": "pune",
    "almaty open": "almaty",
    "hong kong tennis open": "hong kong",
    "hangzhou open": "hangzhou",
    "belgrade open": "belgrade",
    "sydney tennis classic": "sydney",
    "zhuhai championships": "zhuhai",
    "hellenic championship": "athens",
    "melbourne summer set": "melbourne",
    "korea open": "seoul",
    "masters cup": "tour finals",
    "bnp paribas masters": "paris masters",
}


def fnum(value: Any) -> float | None:
    try:
        v = float(value if value is not None else "")
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def tour_key(name: str | None) -> str:
    core = (name or "").strip().lower()
    core = re.sub(r"\b\d{4}\b", " ", core)
    core = re.sub(r"\b(challenger|qualifiers?|qualifying|qualification|atp|wta)\b", " ", core)
    core = re.sub(r"[^a-z0-9]+", " ", core)
    return " ".join(core.split())


def key_candidates(name: str | None) -> list[str]:
    raw = (name or "").strip().lower()
    parts = [p.strip() for p in re.split(r"\s*-\s*", raw) if p.strip()]
    keys = [tour_key(raw)]
    keys.extend(tour_key(p) for p in parts)
    if len(parts) >= 2:
        keys.append(tour_key(f"{parts[0]} {parts[-1]}"))
    base = keys[0] if keys else ""
    for token in (
        "adelaide",
        "auckland",
        "basel",
        "beijing",
        "brisbane",
        "cincinnati",
        "doha",
        "dubai",
        "geneva",
        "hamburg",
        "halle",
        "houston",
        "indian wells",
        "kitzbuhel",
        "los cabos",
        "madrid",
        "mallorca",
        "marseille",
        "miami",
        "monte carlo",
        "munich",
        "paris",
        "rio de janeiro",
        "rome",
        "rotterdam",
        "stuttgart",
        "tokyo",
        "vienna",
        "washington",
        "winston salem",
    ):
        if token in base:
            keys.append(token)
    if "queen" in base and "club" in base:
        keys.append("queen s club")
    if "hertogenbosch" in base or "rosmalen" in base:
        keys.append("s hertogenbosch")
    expanded: list[str] = []
    for key in keys:
        if not key:
            continue
        expanded.append(key)
        alias = TOURNAMENT_ALIASES.get(key)
        if alias:
            expanded.append(alias)
    seen = set()
    out = []
    for key in expanded:
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def canonical_surface(surface: str | None) -> str:
    s = (surface or "").strip()
    if s == "I.hard":
        return "Hard"
    if s in {"Hard", "Clay", "Grass"}:
        return s
    return s.title() if s else ""


def load_cpi() -> dict[tuple[int, str, str], float]:
    out: dict[tuple[int, str, str], float] = {}
    if not SPEED_CSV.exists():
        return out
    with SPEED_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            try:
                year = int(row.get("season_year") or 0)
            except ValueError:
                continue
            surface = canonical_surface(row.get("surface"))
            key = tour_key(row.get("tournament_key") or row.get("tournament_name"))
            cpi = fnum(row.get("cpi") or row.get("ta_surface_speed"))
            if (
                year > 0
                and surface in {"Hard", "Clay", "Grass"}
                and key
                and cpi is not None
                and CPI_MIN <= cpi <= CPI_MAX
            ):
                out[(year, surface, key)] = cpi
    return out


def surface_stats(cpi: dict[tuple[int, str, str], float], surface: str, max_year: int) -> tuple[float, float]:
    vals = [v for (year, surf, _), v in cpi.items() if surf == surface and year <= max_year]
    if not vals:
        return 0.0, 1.0
    mu = mean(vals)
    sd = pstdev(vals) if len(vals) > 1 else 1.0
    return mu, sd if sd > 1e-9 else 1.0


def resolve_cpi(
    cpi: dict[tuple[int, str, str], float],
    *,
    year: int,
    surface: str,
    tournament: str,
    mode: str,
) -> tuple[float | None, float | None, str, str]:
    keys = key_candidates(tournament)
    if mode == "same_year":
        for key in keys:
            value = cpi.get((year, surface, key))
            if value is not None:
                mu, sd = surface_stats(cpi, surface, year)
                return value, (value - mu) / sd, key, "same_year"
        return None, None, "", "missing"

    for key in keys:
        years = sorted((y for (y, surf, k), _ in cpi.items() if surf == surface and k == key and y <= year - 1), reverse=True)
        if not years:
            continue
        use_years = years[:LAG_YEARS]
        value = sum(cpi[(y, surface, key)] for y in use_years) / len(use_years)
        mu, sd = surface_stats(cpi, surface, year - 1)
        return value, (value - mu) / sd, key, f"prior_lag_{len(use_years)}y"
    return None, None, "", "missing"


def cpi_bucket(z: float) -> str:
    if z <= -BUCKET_Z:
        return "slow"
    if z >= BUCKET_Z:
        return "fast"
    return "neutral"


def value_band(v: float) -> str:
    if v < 10:
        return "5-10"
    if v < 15:
        return "10-15"
    if v < 20:
        return "15-20"
    if v < 30:
        return "20-30"
    return "30-plus"


def style_bucket(row: dict, bet_is_p1: bool) -> str:
    psr = fnum(row.get("p_serve_return"))
    pelo = fnum(row.get("p_elo"))
    if psr is None or pelo is None:
        return "unknown"
    bet_psr = psr if bet_is_p1 else 1.0 - psr
    bet_pelo = pelo if bet_is_p1 else 1.0 - pelo
    diff = bet_psr - bet_pelo
    if diff >= 0.05:
        return "serve_led"
    if diff <= -0.05:
        return "nonserve_led"
    return "balanced"


def load_candidates() -> list[dict]:
    rows: list[dict] = []
    for year in YEARS:
        path = BT / f"backtest-results-{year}.csv"
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                surface = canonical_surface(row.get("surface"))
                if surface not in {"Hard", "Clay", "Grass"}:
                    continue
                if row.get("bet_result") not in {"win", "loss"}:
                    continue
                value = fnum(row.get("value_pct"))
                if value is None or value < VALUE_MIN:
                    continue
                win_odds = fnum(row.get("pinnacle_odds"))
                lose_odds = fnum(row.get("pinnacle_odds_loser"))
                our_prob = fnum(row.get("our_prob"))
                if not win_odds or not lose_odds or win_odds <= 1.0 or lose_odds <= 1.0 or our_prob is None:
                    continue
                p1_won = (row.get("actual_winner") or "").strip() == (row.get("player1") or "").strip()
                bet_won_side = row.get("bet_side") == "winner"
                bet_is_p1 = p1_won == bet_won_side
                bet_odds = win_odds if bet_won_side else lose_odds
                other_odds = lose_odds if bet_won_side else win_odds
                bet_player = (row.get("player1") if bet_is_p1 else row.get("player2")) or ""
                other_player = (row.get("player2") if bet_is_p1 else row.get("player1")) or ""
                model_fav = (row.get("model_favorite") or "").strip()
                market_fav = bet_player.strip() if bet_odds < other_odds else other_player.strip()
                policy_excluded = str(row.get("policy_excluded")).strip().lower() in {"true", "1", "yes"}
                rows.append(
                    {
                        "year": year,
                        "surface": surface,
                        "tournament": row.get("tournament") or "",
                        "series": row.get("series") or "",
                        "confidence": (row.get("confidence") or "").strip().lower(),
                        "value_pct": value,
                        "value_band": value_band(value),
                        "won": row.get("bet_result") == "win",
                        "pnl": (bet_odds - 1.0) if row.get("bet_result") == "win" else -1.0,
                        "scope_policy_allowed": not policy_excluded,
                        "market_side": "fav" if bet_odds < other_odds else "dog",
                        "fav_agree": bool(model_fav) and model_fav == market_fav,
                        "style": style_bucket(row, bet_is_p1),
                    }
                )
    return rows


def metrics(rows: list[dict]) -> dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {
            "n": 0,
            "pnl": 0.0,
            "roi_pct": 0.0,
            "wr_pct": 0.0,
            "p_roi_le_0": 1.0,
            "ci_low_pct": 0.0,
            "ci_high_pct": 0.0,
            "pos_years": 0,
            "years": "",
            "top_tournament": "",
            "top_tournament_pnl": 0.0,
            "top_tournament_n": 0,
        }
    pnl = sum(float(r["pnl"]) for r in rows)
    pnls = [float(r["pnl"]) for r in rows]
    sims = sorted(sum(random.choice(pnls) for _ in range(n)) / n for _ in range(BOOTSTRAP_SIMS))
    by_year: dict[int, list[float]] = defaultdict(lambda: [0, 0.0])
    by_tournament: dict[str, list[float]] = defaultdict(lambda: [0, 0.0])
    for r in rows:
        by_year[int(r["year"])][0] += 1
        by_year[int(r["year"])][1] += float(r["pnl"])
        by_tournament[str(r["tournament"])][0] += 1
        by_tournament[str(r["tournament"])][1] += float(r["pnl"])
    top_t = max(by_tournament.items(), key=lambda kv: kv[1][1]) if by_tournament else ("", [0, 0.0])
    return {
        "n": n,
        "pnl": pnl,
        "roi_pct": 100.0 * pnl / n,
        "wr_pct": 100.0 * sum(1 for r in rows if r["won"]) / n,
        "p_roi_le_0": sum(1 for s in sims if s <= 0.0) / len(sims),
        "ci_low_pct": 100.0 * sims[int(0.025 * len(sims))],
        "ci_high_pct": 100.0 * sims[int(0.975 * len(sims))],
        "pos_years": sum(1 for _, v in by_year.items() if v[0] > 0 and v[1] > 0),
        "years": "; ".join(f"{y}:{v[1]:+.1f}u/{int(v[0])}" for y, v in sorted(by_year.items())),
        "top_tournament": top_t[0],
        "top_tournament_pnl": top_t[1][1],
        "top_tournament_n": int(top_t[1][0]),
    }


def row_cell(rows: list[dict], **labels: str) -> dict[str, Any]:
    return {**labels, **metrics(rows)}


def append_bucket_cells(cells: list[dict[str, Any]], rows: list[dict], **labels: str) -> None:
    cells.append(row_cell(rows, bucket="all", **labels))
    for bucket in ("slow", "neutral", "fast"):
        bucket_rows = [r for r in rows if r["cpi_bucket"] == bucket]
        cells.append(row_cell(bucket_rows, bucket=bucket, **labels))


def main() -> None:
    cpi = load_cpi()
    candidates = load_candidates()
    enriched: list[dict] = []
    missing = defaultdict(int)
    for candidate in candidates:
        for mode in ("same_year", "lagged"):
            cpi_value, cpi_z, cpi_key, cpi_mode = resolve_cpi(
                cpi,
                year=int(candidate["year"]),
                surface=str(candidate["surface"]),
                tournament=str(candidate["tournament"]),
                mode=mode,
            )
            if cpi_value is None or cpi_z is None:
                missing[(mode, candidate["surface"])] += 1
                continue
            enriched.append(
                {
                    **candidate,
                    "mode": mode,
                    "cpi_value": cpi_value,
                    "cpi_z": cpi_z,
                    "cpi_key": cpi_key,
                    "cpi_mode": cpi_mode,
                    "cpi_bucket": cpi_bucket(cpi_z),
                }
            )

    cells: list[dict[str, Any]] = []
    modes = ("lagged", "same_year")
    scopes = {
        "research_all": lambda r: True,
        "policy_allowed": lambda r: bool(r["scope_policy_allowed"]),
    }
    for mode in modes:
        for scope, scope_fn in scopes.items():
            scoped = [r for r in enriched if r["mode"] == mode and scope_fn(r)]
            for surface in ("Hard", "Clay", "Grass"):
                surface_rows = [r for r in scoped if r["surface"] == surface and r["value_pct"] >= VALUE_REPORT_MIN]
                append_bucket_cells(cells, surface_rows, mode=mode, scope=scope, surface=surface, cell="value_10_plus")
                for side in ("fav", "dog"):
                    rows = [r for r in surface_rows if r["market_side"] == side]
                    append_bucket_cells(cells, rows, mode=mode, scope=scope, surface=surface, cell=f"market_{side}")
                for agree in ("agree", "disagree"):
                    want = agree == "agree"
                    rows = [r for r in surface_rows if bool(r["fav_agree"]) == want]
                    append_bucket_cells(cells, rows, mode=mode, scope=scope, surface=surface, cell=f"fav_{agree}")
                for style in ("serve_led", "balanced", "nonserve_led", "unknown"):
                    rows = [r for r in surface_rows if r["style"] == style]
                    append_bucket_cells(cells, rows, mode=mode, scope=scope, surface=surface, cell=f"style_{style}")
                for band in ("5-10", "10-15", "15-20", "20-30", "30-plus"):
                    rows = [r for r in scoped if r["surface"] == surface and r["value_band"] == band]
                    append_bucket_cells(cells, rows, mode=mode, scope=scope, surface=surface, cell=f"value_band_{band}")
                for series in sorted({str(r["series"]) for r in surface_rows if r.get("series")}):
                    rows = [r for r in surface_rows if r["series"] == series]
                    append_bucket_cells(cells, rows, mode=mode, scope=scope, surface=surface, cell=f"series_{series}")

    fields = [
        "mode",
        "scope",
        "surface",
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
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in cells:
            w.writerow({k: row.get(k, "") for k in fields})

    def fmt(row: dict[str, Any]) -> str:
        return (
            f"{row['scope']:<14} {row['surface']:<5} {row['cell']:<22} {row['bucket']:<7} "
            f"n={int(row['n']):<4} ROI={float(row['roi_pct']):+6.1f}% WR={float(row['wr_pct']):5.1f}% "
            f"P(<=0)={float(row['p_roi_le_0']):.2f} years={row.get('years', '')}"
        )

    lines = [
        "All-Surface CPI Research Report",
        "===============================",
        "",
        "Scope: ATP fair-odds historical backtest rows, value >= 5%; headline tables use value >= 10%.",
        "lagged uses prior completed CPI editions only. same_year is a leakage diagnostic only.",
        f"CPI buckets are within-surface z-score buckets: slow <= -{BUCKET_Z:.2f}, fast >= +{BUCKET_Z:.2f}.",
        f"CPI rows: {len(cpi)}; candidates: {len(candidates)}; enriched rows: {len(enriched)}.",
        "",
        "Missing CPI rows by mode/surface:",
    ]
    for mode in ("lagged", "same_year"):
        bits = [f"{surface}={missing[(mode, surface)]}" for surface in ("Hard", "Clay", "Grass")]
        lines.append(f"- {mode}: " + ", ".join(bits))
    lines.extend(["", "Headline lagged cells, value >= 10%:", ""])
    for scope in ("research_all", "policy_allowed"):
        for surface in ("Hard", "Clay", "Grass"):
            for bucket in ("all", "slow", "neutral", "fast"):
                row = next(
                    r
                    for r in cells
                    if r["mode"] == "lagged"
                    and r["scope"] == scope
                    and r["surface"] == surface
                    and r["cell"] == "value_10_plus"
                    and r["bucket"] == bucket
                )
                lines.append(fmt(row))
        lines.append("")

    positives = [
        r
        for r in cells
        if r["mode"] == "lagged"
        and r["scope"] == "research_all"
        and int(r["n"]) >= 60
        and float(r["roi_pct"]) > 0
        and r["bucket"] in {"all", "slow", "neutral", "fast"}
    ]
    positives.sort(key=lambda r: (float(r["roi_pct"]), int(r["n"])), reverse=True)
    lines.extend(["Promising research_all lagged cells (n>=60, ROI>0):"])
    for row in positives[:12]:
        lines.append("- " + fmt(row))
    lines.extend(
        [
            "",
            "Decision rules:",
            "- Do not use same_year for model decisions.",
            "- Treat n<60 as informational only; n>=150 is the minimum for a cell worth acting on.",
            "- A surface-speed cell needs live CLV before promotion.",
            "- CPI should next be tested as a shadow probability overlay, not directly switched on for live signals.",
        ]
    )
    OUT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_TXT}")
    print(f"Wrote {OUT_CSV}")


if __name__ == "__main__":
    main()
