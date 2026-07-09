"""CPI / venue-speed diagnostic for tennis aces and double-fault projections.

This script enriches the stage-0 aces/DF rows with TennisAbstract CPI where it
can be resolved and tests simple speed multipliers. It is intentionally an
audit, not a live model switch: same-year CPI can leak current-event conditions,
so the report separates coverage from any action recommendation.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Callable

from tennis_props_model import count_line_probabilities, resolve_count_dispersion


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROWS = ROOT / "data" / "tennis-props" / "backtest" / "aces-dfs-stage0-rows.csv"
DEFAULT_CPI = ROOT / "data" / "backtest" / "tennisabstract-atp-surface-speed.csv"
DEFAULT_OUT_TXT = ROOT / "data" / "tennis-props" / "backtest" / "aces-dfs-cpi-speed-audit.txt"
DEFAULT_OUT_CSV = ROOT / "data" / "tennis-props" / "backtest" / "aces-dfs-cpi-speed-audit.csv"

CPI_MIN = 0.25
CPI_MAX = 1.75
BUCKET_Z = 0.50


Market = str
Predictor = Callable[["EvalRow", Market], float]


@dataclass(frozen=True)
class EvalRow:
    tour: str
    year: int
    tournament: str
    surface: str
    actual_aces: float
    projected_aces: float
    naive_aces: float
    actual_dfs: float
    projected_dfs: float
    naive_dfs: float
    ace_confidence: str
    df_confidence: str

    def actual(self, market: Market) -> float:
        return self.actual_dfs if market == "dfs" else self.actual_aces

    def projected(self, market: Market) -> float:
        return self.projected_dfs if market == "dfs" else self.projected_aces

    def naive(self, market: Market) -> float:
        return self.naive_dfs if market == "dfs" else self.naive_aces

    def confidence(self, market: Market) -> str:
        return self.df_confidence if market == "dfs" else self.ace_confidence


@dataclass(frozen=True)
class EnrichedRow:
    row: EvalRow
    cpi: float
    cpi_z: float
    cpi_bucket: str
    cpi_mode: str
    cpi_key: str


@dataclass(frozen=True)
class VariantResult:
    market: str
    mode: str
    variant: str
    n: int
    mae: float
    bias: float
    rmse: float
    logloss: float
    delta_mae_vs_current: float
    delta_ll_vs_current: float


def parse_float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        return default


def parse_int(value: str | None, default: int = 0) -> int:
    try:
        return int(float(value if value not in (None, "") else default))
    except (TypeError, ValueError):
        return default


def canonical_surface(value: str | None) -> str:
    text = str(value or "").strip().title()
    if text == "I.Hard":
        return "Hard"
    return text


def keyify(value: str | None) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def key_candidates(tournament: str) -> list[str]:
    base = keyify(tournament)
    candidates = {
        base,
        base.replace("u s", "us"),
        base.replace("us open", "us open"),
        base.replace("us open", "u s open"),
        base.replace("s hertogenbosch", "hertogenbosch"),
        base.replace("hertogenbosch", "s hertogenbosch"),
        base.replace("queens club", "queen s club"),
        base.replace("queen s club", "queens club"),
    }
    if base == "us open":
        candidates.add("us open")
        candidates.add("u s open")
    if base == "roland garros":
        candidates.add("french open")
    return [c for c in candidates if c]


def load_rows(path: Path) -> list[EvalRow]:
    rows: list[EvalRow] = []
    with path.open(encoding="utf-8", newline="") as f:
        for raw in csv.DictReader(f):
            rows.append(
                EvalRow(
                    tour=str(raw.get("tour") or "").strip().upper(),
                    year=parse_int(raw.get("year")),
                    tournament=str(raw.get("tournament") or "").strip(),
                    surface=canonical_surface(raw.get("surface")),
                    actual_aces=parse_float(raw.get("actual_aces")),
                    projected_aces=parse_float(raw.get("projected_aces")),
                    naive_aces=parse_float(raw.get("naive_aces")),
                    actual_dfs=parse_float(raw.get("actual_dfs")),
                    projected_dfs=parse_float(raw.get("projected_dfs")),
                    naive_dfs=parse_float(raw.get("naive_dfs")),
                    ace_confidence=str(raw.get("ace_confidence") or "").strip().upper(),
                    df_confidence=str(raw.get("df_confidence") or "").strip().upper(),
                )
            )
    return rows


def load_cpi(path: Path) -> dict[tuple[int, str, str], float]:
    out: dict[tuple[int, str, str], float] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8-sig", newline="") as f:
        for raw in csv.DictReader(f):
            year = parse_int(raw.get("season_year"))
            surface = canonical_surface(raw.get("surface"))
            key = keyify(raw.get("tournament_key") or raw.get("tournament_name"))
            cpi = parse_float(raw.get("cpi") or raw.get("ta_surface_speed"), default=float("nan"))
            if year and surface in {"Hard", "Clay", "Grass"} and key and math.isfinite(cpi) and CPI_MIN <= cpi <= CPI_MAX:
                out[(year, surface, key)] = cpi
    return out


def surface_stats(cpi: dict[tuple[int, str, str], float], surface: str, max_year: int) -> tuple[float, float]:
    values = [value for (year, surf, _), value in cpi.items() if surf == surface and year <= max_year]
    if not values:
        return 0.0, 1.0
    mu = mean(values)
    sd = pstdev(values) if len(values) > 1 else 1.0
    return mu, sd if sd > 1e-9 else 1.0


def resolve_cpi(
    cpi: dict[tuple[int, str, str], float],
    row: EvalRow,
    *,
    mode: str,
    lag_years: int,
) -> EnrichedRow | None:
    keys = key_candidates(row.tournament)
    if mode == "same_year":
        for key in keys:
            value = cpi.get((row.year, row.surface, key))
            if value is not None:
                mu, sd = surface_stats(cpi, row.surface, row.year)
                z = (value - mu) / sd
                return EnrichedRow(row=row, cpi=value, cpi_z=z, cpi_bucket=cpi_bucket(z), cpi_mode="same_year", cpi_key=key)
        return None

    for key in keys:
        years = sorted(
            (year for (year, surface, stored_key), _ in cpi.items() if surface == row.surface and stored_key == key and year <= row.year - 1),
            reverse=True,
        )
        if not years:
            continue
        selected_years = years[:lag_years]
        value = sum(cpi[(year, row.surface, key)] for year in selected_years) / len(selected_years)
        mu, sd = surface_stats(cpi, row.surface, row.year - 1)
        z = (value - mu) / sd
        return EnrichedRow(row=row, cpi=value, cpi_z=z, cpi_bucket=cpi_bucket(z), cpi_mode=f"lagged_{len(selected_years)}y", cpi_key=key)
    return None


def cpi_bucket(z: float) -> str:
    if z <= -BUCKET_Z:
        return "slow"
    if z >= BUCKET_Z:
        return "fast"
    return "neutral"


def safe_mean(values: list[float]) -> float:
    return mean(values) if values else float("nan")


def rmse(errors: list[float]) -> float:
    return math.sqrt(safe_mean([err * err for err in errors])) if errors else float("nan")


def log_loss(probs: list[float], outcomes: list[int]) -> float:
    if not probs:
        return float("nan")
    total = 0.0
    for prob, outcome in zip(probs, outcomes, strict=True):
        p = max(1e-6, min(1.0 - 1e-6, prob))
        total += -outcome * math.log(p) - (1 - outcome) * math.log(1.0 - p)
    return total / len(probs)


def metrics(rows: list[EnrichedRow], market: Market, predictor: Predictor) -> dict[str, float]:
    errors: list[float] = []
    probs: list[float] = []
    outcomes: list[int] = []
    for enriched in rows:
        row = enriched.row
        pred = max(0.0, predictor(row, market))
        actual = row.actual(market)
        errors.append(pred - actual)
        line = math.floor(row.naive(market)) + 0.5
        alpha = resolve_count_dispersion(row.tour, market)
        probs.append(
            count_line_probabilities(
                line,
                pred,
                distribution="negative_binomial",
                alpha=alpha,
                tour=row.tour,
                market=market,
            )[0]
        )
        outcomes.append(1 if actual > line else 0)
    return {
        "n": float(len(rows)),
        "mae": safe_mean([abs(error) for error in errors]),
        "bias": safe_mean(errors),
        "rmse": rmse(errors),
        "logloss": log_loss(probs, outcomes),
    }


def current_predictor(row: EvalRow, market: Market) -> float:
    return row.projected(market)


def cpi_multiplier_predictor(
    enriched_lookup: dict[EvalRow, EnrichedRow],
    *,
    ace_beta: float,
    df_beta: float,
    cap: float,
) -> Predictor:
    def _predict(row: EvalRow, market: Market) -> float:
        enriched = enriched_lookup[row]
        beta = df_beta if market == "dfs" else ace_beta
        multiplier = max(1.0 - cap, min(1.0 + cap, 1.0 + beta * enriched.cpi_z))
        return row.projected(market) * multiplier

    return _predict


def evaluate_variants(enriched_rows: list[EnrichedRow], mode: str) -> list[VariantResult]:
    lookup = {row.row: row for row in enriched_rows}
    candidates: list[tuple[str, Predictor]] = [("current", current_predictor)]
    for ace_beta in (0.015, 0.025, 0.035, 0.050):
        for df_beta in (-0.020, -0.010, 0.000, 0.010, 0.020):
            candidates.append(
                (
                    f"cpi_ace{ace_beta:+.3f}_df{df_beta:+.3f}",
                    cpi_multiplier_predictor(lookup, ace_beta=ace_beta, df_beta=df_beta, cap=0.12),
                )
            )

    results: list[VariantResult] = []
    for market in ("aces", "dfs"):
        current = metrics(enriched_rows, market, current_predictor)
        for variant, predictor in candidates:
            scored = metrics(enriched_rows, market, predictor)
            results.append(
                VariantResult(
                    market=market,
                    mode=mode,
                    variant=variant,
                    n=int(scored["n"]),
                    mae=scored["mae"],
                    bias=scored["bias"],
                    rmse=scored["rmse"],
                    logloss=scored["logloss"],
                    delta_mae_vs_current=scored["mae"] - current["mae"],
                    delta_ll_vs_current=scored["logloss"] - current["logloss"],
                )
            )
    return results


def segment_metrics(enriched_rows: list[EnrichedRow], market: Market, key_fn: Callable[[EnrichedRow], str]) -> list[tuple[str, dict[str, float]]]:
    grouped: dict[str, list[EnrichedRow]] = defaultdict(list)
    for row in enriched_rows:
        grouped[key_fn(row)].append(row)
    return [(key, metrics(grouped[key], market, current_predictor)) for key in sorted(grouped)]


def fmt(value: float, digits: int = 3) -> str:
    return "n/a" if not math.isfinite(value) else f"{value:.{digits}f}"


def write_csv(path: Path, results: list[VariantResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "mode",
        "market",
        "variant",
        "n",
        "mae",
        "bias",
        "rmse",
        "logloss",
        "delta_mae_vs_current",
        "delta_ll_vs_current",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for result in sorted(results, key=lambda r: (r.mode, r.market, r.mae, r.logloss)):
            writer.writerow(
                {
                    "mode": result.mode,
                    "market": result.market,
                    "variant": result.variant,
                    "n": result.n,
                    "mae": f"{result.mae:.6f}",
                    "bias": f"{result.bias:.6f}",
                    "rmse": f"{result.rmse:.6f}",
                    "logloss": f"{result.logloss:.6f}",
                    "delta_mae_vs_current": f"{result.delta_mae_vs_current:.6f}",
                    "delta_ll_vs_current": f"{result.delta_ll_vs_current:.6f}",
                }
            )


def write_report(
    path: Path,
    *,
    source_rows: list[EvalRow],
    enriched_by_mode: dict[str, list[EnrichedRow]],
    results: list[VariantResult],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "Tennis Props CPI Speed Audit",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Input rows: {len(source_rows)}",
        "Outcome-only. No odds, no ROI, no CLV.",
        "Lagged CPI is safe for model decisions; same-year CPI is diagnostic only unless captured before the match.",
        "",
        "Coverage",
    ]
    for mode, rows in enriched_by_mode.items():
        lines.append(f"- {mode}: {len(rows)}/{len(source_rows)} rows ({100.0 * len(rows) / max(1, len(source_rows)):.1f}%)")
        by_tournament = defaultdict(int)
        for row in rows:
            by_tournament[f"{row.row.tour} {row.row.tournament} {row.row.year}"] += 1
        for key, count in sorted(by_tournament.items()):
            lines.append(f"  {key}: {count}")
    lines.append("")

    for mode, enriched_rows in enriched_by_mode.items():
        if not enriched_rows:
            continue
        mode_results = [result for result in results if result.mode == mode]
        lines.append(f"{mode.upper()} headline")
        for market in ("aces", "dfs"):
            current = next(result for result in mode_results if result.market == market and result.variant == "current")
            best = min((r for r in mode_results if r.market == market), key=lambda r: (r.mae, r.logloss))
            if best.variant == "current":
                lines.append(f"- {market.upper()}: current remains best (MAE {current.mae:.3f}, bias {current.bias:+.3f}).")
            else:
                lines.append(
                    f"- {market.upper()}: {best.variant} improves MAE by {-best.delta_mae_vs_current:.3f} "
                    f"({current.mae:.3f} -> {best.mae:.3f}), log-loss delta {best.delta_ll_vs_current:+.3f}."
                )
        lines.append("")

        lines.append(f"{mode.upper()} current model by CPI bucket")
        lines.append("Market Bucket     N  MAE   Bias   RMSE  LogLoss")
        for market in ("aces", "dfs"):
            for bucket, summary in segment_metrics(enriched_rows, market, lambda r: r.cpi_bucket):
                lines.append(
                    f"{market:<6} {bucket:<8} {int(summary['n']):4d} "
                    f"{fmt(summary['mae']):>5s} {summary['bias']:+6.3f} {fmt(summary['rmse']):>6s} {fmt(summary['logloss']):>7s}"
                )
        lines.append("")

        lines.append(f"{mode.upper()} best variants")
        lines.append("Market Variant                         N  MAE   DeltaMAE  Bias   LogLoss  DeltaLL")
        for market in ("aces", "dfs"):
            ranked = sorted([r for r in mode_results if r.market == market], key=lambda r: (r.mae, r.logloss))[:8]
            for result in ranked:
                lines.append(
                    f"{market:<6} {result.variant[:31]:31s} {result.n:4d} "
                    f"{fmt(result.mae):>5s} {result.delta_mae_vs_current:+9.3f} "
                    f"{result.bias:+6.3f} {fmt(result.logloss):>7s} {result.delta_ll_vs_current:+8.3f}"
                )
        lines.append("")

    lines.append("Decision")
    lagged = enriched_by_mode.get("lagged", [])
    if not lagged:
        lines.append("- No lagged CPI coverage in the current props stage-0 rows, so do not wire CPI into aces/DF live pricing from this audit.")
        lines.append("- Next required step: regenerate stage-0 rows with broader non-Slam main-tour coverage and historical CPI rows, then re-run.")
    else:
        lines.append("- Consider wiring only if lagged CPI improves MAE by >=0.03 counts and does not worsen synthetic O/U log-loss.")
    lines.append("- Same-year CPI can explain venue effects but must stay research-only unless we can prove it is available before match time.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit CPI speed multipliers for tennis aces/DF stage-0 rows.")
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--cpi", type=Path, default=DEFAULT_CPI)
    parser.add_argument("--lag-years", type=int, default=3)
    parser.add_argument("--out-txt", type=Path, default=DEFAULT_OUT_TXT)
    parser.add_argument("--out-csv", type=Path, default=DEFAULT_OUT_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = load_rows(args.rows)
    cpi = load_cpi(args.cpi)
    enriched_by_mode = {
        "lagged": [resolved for row in rows if (resolved := resolve_cpi(cpi, row, mode="lagged", lag_years=args.lag_years)) is not None],
        "same_year": [resolved for row in rows if (resolved := resolve_cpi(cpi, row, mode="same_year", lag_years=args.lag_years)) is not None],
    }
    results: list[VariantResult] = []
    for mode, enriched_rows in enriched_by_mode.items():
        if enriched_rows:
            results.extend(evaluate_variants(enriched_rows, mode))
    write_csv(args.out_csv, results)
    write_report(args.out_txt, source_rows=rows, enriched_by_mode=enriched_by_mode, results=results)
    print(f"Wrote {args.out_txt}")
    print(f"Wrote {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
