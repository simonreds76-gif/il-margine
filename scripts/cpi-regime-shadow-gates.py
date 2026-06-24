#!/usr/bin/env python3
"""Gate-search and value-calibration audit for the CPI speed-regime tennis model.

This is intentionally research-only. It turns the broad CPI regime experiment into
concrete shadow cells by requiring a simple train/holdout pass:

  - train: 2024
  - holdout: 2025

The historical tennis-data files list the match winner first, so this script does
not pretend to produce a standard reliability diagram. Instead it calibrates the
useful betting question: when a speed-regime cell claims value, did that value
realise in ROI against the available Pinnacle price?
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKTEST_DIR = ROOT / "data" / "backtest"
TRAIN_YEAR = 2024
HOLDOUT_YEAR = 2025
THRESHOLD = 10.0
CALIBRATION_THRESHOLD = 5.0
SPEED_SURFACES = {"SpeedFast", "SpeedNeutral", "SpeedSlow"}


def _float(value: object) -> float | None:
    try:
        text = str(value or "").strip()
        if text == "":
            return None
        return float(text)
    except Exception:
        return None


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _key(row: dict[str, str], year: int) -> tuple[int, str, str, str, str, str]:
    return (
        year,
        str(row.get("date") or "").strip(),
        str(row.get("tournament") or "").strip().lower(),
        str(row.get("round") or "").strip().lower(),
        str(row.get("player1_id") or "").strip(),
        str(row.get("player2_id") or "").strip(),
    )


def _load_rows(suffix: str) -> dict[tuple[int, str, str, str, str, str], dict[str, str]]:
    out: dict[tuple[int, str, str, str, str, str], dict[str, str]] = {}
    for year in (TRAIN_YEAR, HOLDOUT_YEAR):
        path = BACKTEST_DIR / f"backtest-results-{year}-{suffix}.csv"
        if not path.exists():
            raise FileNotFoundError(path)
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                row = dict(row)
                row["source_year"] = str(year)
                out[_key(row, year)] = row
    return out


def _selected(row: dict[str, str], threshold: float, value_field: str = "value_pct") -> dict[str, Any] | None:
    if not _truthy(row.get("has_pinnacle_odds")):
        return None
    if _truthy(row.get("policy_excluded")):
        return None
    value_pct = _float(row.get(value_field))
    if value_pct is None or value_pct < threshold:
        return None
    side = str(row.get("bet_side") or "").strip().lower()
    if side not in {"winner", "loser"}:
        return None
    odds_field = "pinnacle_odds" if side == "winner" else "pinnacle_odds_loser"
    odds = _float(row.get(odds_field))
    if odds is None or odds <= 1.0:
        return None
    result = str(row.get("bet_result") or "").strip().lower()
    if result not in {"win", "loss"}:
        return None
    pnl = odds - 1.0 if result == "win" else -1.0
    return {
        "side": side,
        "odds": odds,
        "value_pct": value_pct,
        "result": result,
        "pnl": pnl,
    }


def _roi(pnl: float, bets: int) -> float:
    return 100.0 * pnl / bets if bets else 0.0


def _cpi_bucket(row: dict[str, str]) -> str:
    if _float(row.get("cpi_value")) is None:
        return "missing"
    z = _float(row.get("cpi_z")) or 0.0
    if z <= -0.50:
        return "slow"
    if z >= 0.50:
        return "fast"
    return "neutral"


def _value_band(row: dict[str, str]) -> str:
    value = _float(row.get("value_pct")) or 0.0
    if value >= 25:
        return "25+"
    if value >= 15:
        return "15-25"
    if value >= 10:
        return "10-15"
    if value >= 5:
        return "5-10"
    return "<5"


def _market_side(row: dict[str, str]) -> str:
    winner_odds = _float(row.get("pinnacle_odds"))
    loser_odds = _float(row.get("pinnacle_odds_loser"))
    if winner_odds is None or loser_odds is None:
        return "unknown"
    return "winner" if winner_odds <= loser_odds else "loser"


def _model_side(row: dict[str, str]) -> str:
    fav = str(row.get("model_favorite") or "").strip().lower()
    p1 = str(row.get("player1") or "").strip().lower()
    p2 = str(row.get("player2") or "").strip().lower()
    if fav == p1:
        return "winner"
    if fav == p2:
        return "loser"
    return "unknown"


def _alignment(row: dict[str, str]) -> str:
    model = _model_side(row)
    market = _market_side(row)
    if "unknown" in {model, market}:
        return "unknown"
    return "same_fav" if model == market else "side_flip"


def _segments(row: dict[str, str]) -> list[tuple[str, str]]:
    surface = str(row.get("surface") or "unknown").strip() or "unknown"
    model_surface = str(row.get("model_surface") or surface).strip() or surface
    cpi_bucket = _cpi_bucket(row)
    confidence = str(row.get("confidence") or "unknown").strip().lower() or "unknown"
    series = str(row.get("series") or "unknown").strip() or "unknown"
    alignment = _alignment(row)
    value_band = _value_band(row)
    surface_cpi = f"{surface}:{cpi_bucket}"
    return [
        ("all", "all"),
        ("model_surface", model_surface),
        ("surface_cpi_bucket", surface_cpi),
        ("model_surface_confidence", f"{model_surface}:{confidence}"),
        ("surface_cpi_bucket_confidence", f"{surface_cpi}:{confidence}"),
        ("model_surface_alignment", f"{model_surface}:{alignment}"),
        ("surface_cpi_bucket_alignment", f"{surface_cpi}:{alignment}"),
        ("model_surface_value_band", f"{model_surface}:{value_band}"),
        ("surface_cpi_bucket_value_band", f"{surface_cpi}:{value_band}"),
        ("model_surface_series", f"{model_surface}:{series}"),
    ]


def _new_perf() -> dict[str, Any]:
    return {"bets": 0, "wins": 0, "pnl": 0.0, "value_sum": 0.0, "odds_sum": 0.0}


def _add_perf(perf: dict[str, Any], selection: dict[str, Any] | None) -> None:
    if not selection:
        return
    perf["bets"] += 1
    perf["wins"] += 1 if selection["result"] == "win" else 0
    perf["pnl"] += float(selection["pnl"])
    perf["value_sum"] += float(selection["value_pct"])
    perf["odds_sum"] += float(selection["odds"])


def _summarise(perf: dict[str, Any]) -> dict[str, float | int]:
    bets = int(perf["bets"])
    pnl = float(perf["pnl"])
    return {
        "bets": bets,
        "wins": int(perf["wins"]),
        "pnl": round(pnl, 4),
        "roi_pct": round(_roi(pnl, bets), 3),
        "avg_value_pct": round(float(perf["value_sum"]) / bets, 3) if bets else 0.0,
        "avg_odds": round(float(perf["odds_sum"]) / bets, 3) if bets else 0.0,
    }


def _fit_surface_factors(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    by_surface: dict[str, dict[str, Any]] = defaultdict(_new_perf)
    for row in rows:
        if int(row.get("source_year") or 0) != TRAIN_YEAR:
            continue
        model_surface = str(row.get("model_surface") or "").strip()
        if model_surface not in SPEED_SURFACES:
            continue
        _add_perf(by_surface[model_surface], _selected(row, CALIBRATION_THRESHOLD))

    factors: dict[str, dict[str, Any]] = {}
    for model_surface in sorted(SPEED_SURFACES):
        summary = _summarise(by_surface[model_surface])
        avg_value = float(summary["avg_value_pct"])
        roi = float(summary["roi_pct"])
        raw_factor = roi / avg_value if avg_value > 0 else 0.0
        if int(summary["bets"]) < 30 or roi <= 0:
            factor = 0.0
            verdict = "blocked"
        else:
            factor = max(0.0, min(1.25, raw_factor))
            verdict = "usable" if factor >= 0.25 else "too_weak"
            if verdict == "too_weak":
                factor = 0.0
        factors[model_surface] = {
            **summary,
            "realisation_factor": round(factor, 4),
            "raw_realisation_factor": round(raw_factor, 4),
            "verdict": verdict,
        }
    return factors


def _apply_calibrated_value(rows: list[dict[str, str]], factors: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        row = dict(row)
        model_surface = str(row.get("model_surface") or "").strip()
        factor = float(factors.get(model_surface, {}).get("realisation_factor") or 0.0)
        value = _float(row.get("value_pct"))
        if value is None or model_surface not in SPEED_SURFACES:
            row["cpi_regime_calibrated_value_pct"] = ""
            row["cpi_regime_factor"] = ""
        else:
            row["cpi_regime_calibrated_value_pct"] = f"{value * factor:.6f}"
            row["cpi_regime_factor"] = f"{factor:.4f}"
        out.append(row)
    return out


def _gate_status(train_overlay: dict[str, Any], holdout_overlay: dict[str, Any]) -> str:
    train = _summarise(train_overlay)
    holdout = _summarise(holdout_overlay)
    combined_bets = int(train["bets"]) + int(holdout["bets"])
    combined_pnl = float(train["pnl"]) + float(holdout["pnl"])
    combined_roi = _roi(combined_pnl, combined_bets)

    if (
        int(train["bets"]) >= 30
        and float(train["roi_pct"]) >= 3.0
        and int(holdout["bets"]) >= 20
        and float(holdout["roi_pct"]) >= 0.0
        and combined_bets >= 60
        and combined_roi >= 3.0
    ):
        return "PASS_SHADOW"
    if (
        int(train["bets"]) >= 20
        and float(train["roi_pct"]) >= 0.0
        and int(holdout["bets"]) >= 10
        and float(holdout["roi_pct"]) >= -5.0
        and combined_roi >= 0.0
    ):
        return "WATCH"
    return "FAIL"


def _is_cpi_specific(segment: str, value: str) -> bool:
    if "Speed" in value:
        return True
    if segment.startswith("surface_cpi_bucket"):
        return ":fast" in value or ":neutral" in value or ":slow" in value
    return False


def _build_gate_rows(
    base_rows: dict[tuple[int, str, str, str, str, str], dict[str, str]],
    overlay_rows: dict[tuple[int, str, str, str, str, str], dict[str, str]],
) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "train_base": _new_perf(),
            "train_overlay": _new_perf(),
            "holdout_base": _new_perf(),
            "holdout_overlay": _new_perf(),
        }
    )
    for key in sorted(set(base_rows) & set(overlay_rows)):
        year = key[0]
        base = base_rows[key]
        overlay = overlay_rows[key]
        year_prefix = "train" if year == TRAIN_YEAR else "holdout"
        base_sel = _selected(base, THRESHOLD)
        overlay_sel = _selected(overlay, THRESHOLD)
        for segment, value in _segments(overlay):
            bucket = buckets[(segment, value)]
            _add_perf(bucket[f"{year_prefix}_base"], base_sel)
            _add_perf(bucket[f"{year_prefix}_overlay"], overlay_sel)

    rows: list[dict[str, Any]] = []
    for (segment, value), bucket in buckets.items():
        train_base = _summarise(bucket["train_base"])
        train_overlay = _summarise(bucket["train_overlay"])
        holdout_base = _summarise(bucket["holdout_base"])
        holdout_overlay = _summarise(bucket["holdout_overlay"])
        status = _gate_status(bucket["train_overlay"], bucket["holdout_overlay"])
        if status in {"PASS_SHADOW", "WATCH"} and not _is_cpi_specific(segment, value):
            status = "BASELINE_CONTEXT"
        combined_bets = int(train_overlay["bets"]) + int(holdout_overlay["bets"])
        combined_pnl = float(train_overlay["pnl"]) + float(holdout_overlay["pnl"])
        rows.append(
            {
                "status": status,
                "segment": segment,
                "value": value,
                "train_base_bets": train_base["bets"],
                "train_base_roi_pct": train_base["roi_pct"],
                "train_overlay_bets": train_overlay["bets"],
                "train_overlay_roi_pct": train_overlay["roi_pct"],
                "train_overlay_pnl": train_overlay["pnl"],
                "train_overlay_avg_value_pct": train_overlay["avg_value_pct"],
                "holdout_base_bets": holdout_base["bets"],
                "holdout_base_roi_pct": holdout_base["roi_pct"],
                "holdout_overlay_bets": holdout_overlay["bets"],
                "holdout_overlay_roi_pct": holdout_overlay["roi_pct"],
                "holdout_overlay_pnl": holdout_overlay["pnl"],
                "holdout_overlay_avg_value_pct": holdout_overlay["avg_value_pct"],
                "combined_overlay_bets": combined_bets,
                "combined_overlay_pnl": round(combined_pnl, 4),
                "combined_overlay_roi_pct": round(_roi(combined_pnl, combined_bets), 3),
            }
        )
    status_rank = {"PASS_SHADOW": 0, "WATCH": 1, "BASELINE_CONTEXT": 2, "FAIL": 3}
    return sorted(
        rows,
        key=lambda r: (
            status_rank.get(str(r["status"]), 9),
            -float(r["holdout_overlay_pnl"]),
            -int(r["combined_overlay_bets"]),
        ),
    )


def _calibrated_holdout_report(rows: list[dict[str, str]]) -> dict[str, Any]:
    perf = _new_perf()
    by_surface: dict[str, dict[str, Any]] = defaultdict(_new_perf)
    for row in rows:
        if int(row.get("source_year") or 0) != HOLDOUT_YEAR:
            continue
        selection = _selected(row, THRESHOLD, value_field="cpi_regime_calibrated_value_pct")
        _add_perf(perf, selection)
        if selection:
            _add_perf(by_surface[str(row.get("model_surface") or "unknown")], selection)
    return {
        "all": _summarise(perf),
        "by_surface": {surface: _summarise(bucket) for surface, bucket in sorted(by_surface.items())},
    }


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _write_factor_csv(path: Path, factors: dict[str, dict[str, Any]]) -> None:
    fields = [
        "model_surface",
        "bets",
        "wins",
        "pnl",
        "roi_pct",
        "avg_value_pct",
        "avg_odds",
        "raw_realisation_factor",
        "realisation_factor",
        "verdict",
    ]
    rows = [{"model_surface": surface, **values} for surface, values in sorted(factors.items())]
    _write_csv(path, rows, fields)


def _write_report(
    path: Path,
    gates: list[dict[str, Any]],
    factors: dict[str, dict[str, Any]],
    calibrated: dict[str, Any],
) -> None:
    passed = [row for row in gates if row["status"] == "PASS_SHADOW"]
    watched = [row for row in gates if row["status"] == "WATCH"]
    with open(path, "w", encoding="utf-8") as f:
        f.write("CPI speed-regime shadow gate report\n")
        f.write("===================================\n\n")
        f.write("Verdict: SHADOW ONLY - gated cells, no live routing\n")
        f.write(f"Train year: {TRAIN_YEAR}; holdout year: {HOLDOUT_YEAR}; value threshold: {THRESHOLD:.0f}%.\n")
        f.write("The historical files list winners first, so value realisation is used instead of a fake reliability curve.\n\n")
        f.write("Speed-regime value realisation factors (trained on 2024 value>=5)\n")
        f.write("----------------------------------------------------------------\n")
        for surface, values in sorted(factors.items()):
            f.write(
                f"{surface:<13} bets={int(values['bets']):>4} roi={float(values['roi_pct']):>+7.2f}% "
                f"avg_claim={float(values['avg_value_pct']):>5.2f}% "
                f"factor={float(values['realisation_factor']):>4.2f} {values['verdict']}\n"
            )
        f.write("\nCalibrated holdout selection, speed surfaces only\n")
        f.write("-------------------------------------------------\n")
        all_perf = calibrated["all"]
        f.write(
            f"All speed surfaces: bets={int(all_perf['bets'])} "
            f"roi={float(all_perf['roi_pct']):+.2f}% pnl={float(all_perf['pnl']):+.2f}u\n"
        )
        for surface, perf in calibrated["by_surface"].items():
            f.write(
                f"{surface:<13} bets={int(perf['bets']):>3} "
                f"roi={float(perf['roi_pct']):>+7.2f}% pnl={float(perf['pnl']):>+7.2f}u\n"
            )
        f.write("\nAccepted shadow gates\n")
        f.write("---------------------\n")
        if not passed:
            f.write("No cell passed the strict train+holdout gate.\n")
        for row in passed[:20]:
            f.write(
                f"{row['segment']}={row['value']} | "
                f"train {row['train_overlay_bets']} bets {float(row['train_overlay_roi_pct']):+.2f}% | "
                f"holdout {row['holdout_overlay_bets']} bets {float(row['holdout_overlay_roi_pct']):+.2f}% | "
                f"combined {row['combined_overlay_bets']} bets {float(row['combined_overlay_roi_pct']):+.2f}%\n"
            )
        f.write("\nWatchlist gates\n")
        f.write("---------------\n")
        if not watched:
            f.write("No watchlist cells.\n")
        for row in watched[:20]:
            f.write(
                f"{row['segment']}={row['value']} | "
                f"train {row['train_overlay_bets']} bets {float(row['train_overlay_roi_pct']):+.2f}% | "
                f"holdout {row['holdout_overlay_bets']} bets {float(row['holdout_overlay_roi_pct']):+.2f}% | "
                f"combined {row['combined_overlay_bets']} bets {float(row['combined_overlay_roi_pct']):+.2f}%\n"
            )
        f.write("\nRules\n")
        f.write("-----\n")
        f.write("- PASS_SHADOW requires train>=30 bets, train ROI>=+3%, holdout>=20 bets, holdout ROI>=0%, combined>=60 bets, combined ROI>=+3%.\n")
        f.write("- WATCH is weaker and exists only to keep an eye on cells, not to publish picks.\n")
        f.write("- No production route should consume these files without a separate live CLV gate.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build CPI speed-regime gated shadow report.")
    parser.add_argument("--base-suffix", default="cpi-base")
    parser.add_argument("--overlay-suffix", default="cpi-regime")
    parser.add_argument("--output-prefix", default="cpi-regime-shadow")
    args = parser.parse_args()

    base = _load_rows(args.base_suffix)
    overlay = _load_rows(args.overlay_suffix)
    overlay_list = [overlay[key] for key in sorted(overlay)]
    factors = _fit_surface_factors(overlay_list)
    calibrated_rows = _apply_calibrated_value(overlay_list, factors)
    calibrated = _calibrated_holdout_report(calibrated_rows)
    gates = _build_gate_rows(base, overlay)

    gate_fields = [
        "status",
        "segment",
        "value",
        "train_base_bets",
        "train_base_roi_pct",
        "train_overlay_bets",
        "train_overlay_roi_pct",
        "train_overlay_pnl",
        "train_overlay_avg_value_pct",
        "holdout_base_bets",
        "holdout_base_roi_pct",
        "holdout_overlay_bets",
        "holdout_overlay_roi_pct",
        "holdout_overlay_pnl",
        "holdout_overlay_avg_value_pct",
        "combined_overlay_bets",
        "combined_overlay_pnl",
        "combined_overlay_roi_pct",
    ]
    gates_path = BACKTEST_DIR / f"{args.output_prefix}-gates.csv"
    factors_path = BACKTEST_DIR / f"{args.output_prefix}-value-factors.csv"
    report_path = BACKTEST_DIR / f"{args.output_prefix}-report.txt"
    _write_csv(gates_path, gates, gate_fields)
    _write_factor_csv(factors_path, factors)
    _write_report(report_path, gates, factors, calibrated)
    print(f"Wrote {gates_path}")
    print(f"Wrote {factors_path}")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
