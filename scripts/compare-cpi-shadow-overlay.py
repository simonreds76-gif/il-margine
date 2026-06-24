#!/usr/bin/env python3
"""Compare current baseline fair-odds backtest against CPI shadow overlay.

This is deliberately a research/audit script. It does not promote any lane.
It answers one question: did the CPI venue-speed overlay improve selections
against real Pinnacle closing prices, or did it just move probabilities around?
"""

from __future__ import annotations

import csv
import math
import argparse
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKTEST_DIR = ROOT / "data" / "backtest"
YEARS = (2024, 2025)
THRESHOLDS = (5.0, 10.0)


def _float(value: object) -> float | None:
    try:
        if value is None:
            return None
        text = str(value).strip()
        if text == "":
            return None
        return float(text)
    except Exception:
        return None


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("date") or "").strip(),
        str(row.get("tournament") or "").strip().lower(),
        str(row.get("round") or "").strip().lower(),
        str(row.get("player1_id") or "").strip(),
        str(row.get("player2_id") or "").strip(),
    )


def _load_rows(suffix: str) -> dict[tuple[str, str, str, str, str], dict[str, str]]:
    out: dict[tuple[str, str, str, str, str], dict[str, str]] = {}
    for year in YEARS:
        path = BACKTEST_DIR / f"backtest-results-{year}-{suffix}.csv"
        if not path.exists():
            raise FileNotFoundError(path)
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                out[_key(row)] = row
    return out


def _selected(row: dict[str, str], threshold: float) -> dict[str, Any] | None:
    if not _truthy(row.get("has_pinnacle_odds")):
        return None
    if _truthy(row.get("policy_excluded")):
        return None
    value_pct = _float(row.get("value_pct"))
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


def _cpi_bucket(row: dict[str, str]) -> str:
    if _float(row.get("cpi_value")) is None:
        return "missing"
    z = _float(row.get("cpi_z")) or 0.0
    if z <= -0.50:
        return "slow"
    if z >= 0.50:
        return "fast"
    return "neutral"


def _add_metric(bucket: dict[str, Any], prefix: str, selection: dict[str, Any] | None) -> None:
    if not selection:
        return
    bucket[f"{prefix}_bets"] += 1
    bucket[f"{prefix}_pnl"] += float(selection["pnl"])
    if selection["result"] == "win":
        bucket[f"{prefix}_wins"] += 1


def _roi(pnl: float, bets: int) -> float:
    return 100.0 * pnl / bets if bets else 0.0


def _model_prob_actual_winner(row: dict[str, str]) -> float | None:
    fav_prob = _float(row.get("model_favorite_prob"))
    if fav_prob is None:
        return None
    fav = str(row.get("model_favorite") or "").strip().lower()
    p1 = str(row.get("player1") or "").strip().lower()
    p2 = str(row.get("player2") or "").strip().lower()
    actual = str(row.get("actual_winner") or "").strip().lower()
    if actual == p1:
        return fav_prob if fav == p1 else 1.0 - fav_prob
    if actual == p2:
        return fav_prob if fav == p2 else 1.0 - fav_prob
    return None


def _prob_scores(rows: list[dict[str, str]]) -> tuple[int, float, float]:
    n = 0
    brier = 0.0
    logloss = 0.0
    for row in rows:
        p = _model_prob_actual_winner(row)
        if p is None:
            continue
        p = min(max(p, 1e-6), 1.0 - 1e-6)
        n += 1
        brier += (1.0 - p) ** 2
        logloss += -math.log(p)
    if not n:
        return 0, 0.0, 0.0
    return n, brier / n, logloss / n


def _new_bucket() -> dict[str, Any]:
    return {
        "pairs": 0,
        "base_bets": 0,
        "base_wins": 0,
        "base_pnl": 0.0,
        "overlay_bets": 0,
        "overlay_wins": 0,
        "overlay_pnl": 0.0,
        "same_side": 0,
        "added": 0,
        "dropped": 0,
        "flipped": 0,
        "prob_move_abs_sum": 0.0,
        "cpi_delta_abs_sum": 0.0,
        "cpi_rows": 0,
    }


def _segment_rows(
    paired: list[tuple[dict[str, str], dict[str, str]]],
    threshold: float,
) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], dict[str, Any]] = defaultdict(_new_bucket)

    for base, overlay in paired:
        surface = str(overlay.get("surface") or base.get("surface") or "unknown").strip() or "unknown"
        model_surface = str(overlay.get("model_surface") or surface).strip() or surface
        cpi_bucket = _cpi_bucket(overlay)
        segment_values = [
            ("all", "all"),
            ("surface", surface),
            ("model_surface", model_surface),
            ("cpi_bucket", cpi_bucket),
            ("surface_cpi_bucket", f"{surface}:{cpi_bucket}"),
        ]
        base_sel = _selected(base, threshold)
        overlay_sel = _selected(overlay, threshold)
        base_prob = _float(base.get("our_prob"))
        overlay_prob = _float(overlay.get("our_prob"))
        prob_move = abs((overlay_prob or 0.0) - (base_prob or 0.0)) if base_prob is not None and overlay_prob is not None else 0.0
        cpi_delta = abs(_float(overlay.get("cpi_delta")) or 0.0)
        has_cpi = _float(overlay.get("cpi_value")) is not None

        for segment, value in segment_values:
            bucket = buckets[(segment, value)]
            bucket["pairs"] += 1
            bucket["prob_move_abs_sum"] += prob_move
            if has_cpi:
                bucket["cpi_rows"] += 1
                bucket["cpi_delta_abs_sum"] += cpi_delta
            _add_metric(bucket, "base", base_sel)
            _add_metric(bucket, "overlay", overlay_sel)
            if base_sel and overlay_sel:
                if base_sel["side"] == overlay_sel["side"]:
                    bucket["same_side"] += 1
                else:
                    bucket["flipped"] += 1
            elif overlay_sel and not base_sel:
                bucket["added"] += 1
            elif base_sel and not overlay_sel:
                bucket["dropped"] += 1

    rows: list[dict[str, Any]] = []
    for (segment, value), bucket in sorted(buckets.items()):
        base_bets = int(bucket["base_bets"])
        overlay_bets = int(bucket["overlay_bets"])
        base_pnl = float(bucket["base_pnl"])
        overlay_pnl = float(bucket["overlay_pnl"])
        pairs = int(bucket["pairs"])
        cpi_rows = int(bucket["cpi_rows"])
        rows.append(
            {
                "threshold": threshold,
                "segment": segment,
                "value": value,
                "pairs": pairs,
                "cpi_rows": cpi_rows,
                "base_bets": base_bets,
                "base_wins": int(bucket["base_wins"]),
                "base_pnl": round(base_pnl, 4),
                "base_roi_pct": round(_roi(base_pnl, base_bets), 3),
                "overlay_bets": overlay_bets,
                "overlay_wins": int(bucket["overlay_wins"]),
                "overlay_pnl": round(overlay_pnl, 4),
                "overlay_roi_pct": round(_roi(overlay_pnl, overlay_bets), 3),
                "delta_bets": overlay_bets - base_bets,
                "delta_pnl": round(overlay_pnl - base_pnl, 4),
                "delta_roi_pct": round(_roi(overlay_pnl, overlay_bets) - _roi(base_pnl, base_bets), 3),
                "same_side": int(bucket["same_side"]),
                "added": int(bucket["added"]),
                "dropped": int(bucket["dropped"]),
                "flipped": int(bucket["flipped"]),
                "avg_abs_prob_move_pp": round(100.0 * float(bucket["prob_move_abs_sum"]) / pairs, 4) if pairs else 0.0,
                "avg_abs_cpi_delta_pp": round(100.0 * float(bucket["cpi_delta_abs_sum"]) / cpi_rows, 4) if cpi_rows else 0.0,
            }
        )
    return rows


def _write_cells(rows: list[dict[str, Any]], output_prefix: str) -> Path:
    path = BACKTEST_DIR / f"{output_prefix}-cells.csv"
    fields = [
        "threshold",
        "segment",
        "value",
        "pairs",
        "cpi_rows",
        "base_bets",
        "base_wins",
        "base_pnl",
        "base_roi_pct",
        "overlay_bets",
        "overlay_wins",
        "overlay_pnl",
        "overlay_roi_pct",
        "delta_bets",
        "delta_pnl",
        "delta_roi_pct",
        "same_side",
        "added",
        "dropped",
        "flipped",
        "avg_abs_prob_move_pp",
        "avg_abs_cpi_delta_pp",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k) for k in fields})
    return path


def _fmt_row(row: dict[str, Any]) -> str:
    return (
        f"{row['value']:<22} pairs={row['pairs']:>4} "
        f"base={row['base_bets']:>4} bets {row['base_roi_pct']:>+7.2f}% "
        f"overlay={row['overlay_bets']:>4} bets {row['overlay_roi_pct']:>+7.2f}% "
        f"delta_pnl={row['delta_pnl']:>+7.2f}u "
        f"added/drop/flip={row['added']}/{row['dropped']}/{row['flipped']}"
    )


def _write_report(
    paired: list[tuple[dict[str, str], dict[str, str]]],
    rows: list[dict[str, Any]],
    base_rows: list[dict[str, str]],
    overlay_rows: list[dict[str, str]],
    *,
    output_prefix: str,
    overlay_label: str,
) -> Path:
    report = BACKTEST_DIR / f"{output_prefix}-report.txt"
    base_n, base_brier, base_logloss = _prob_scores(base_rows)
    overlay_n, overlay_brier, overlay_logloss = _prob_scores(overlay_rows)
    lookup = {(r["threshold"], r["segment"], r["value"]): r for r in rows}
    main10 = lookup[(10.0, "all", "all")]
    main5 = lookup[(5.0, "all", "all")]

    verdict = "NO LIVE PROMOTION"
    main_delta_pnl = float(main10["delta_pnl"])
    main_selection_changes = int(main10["added"]) + int(main10["dropped"]) + int(main10["flipped"])
    if (
        main_delta_pnl >= 2.0
        and main_selection_changes >= 10
        and float(main10["overlay_roi_pct"]) > float(main10["base_roi_pct"])
        and overlay_brier <= base_brier
    ):
        verdict = "SHADOW IMPROVED, STILL NEEDS SAMPLE REVIEW"
    elif (
        main_delta_pnl >= 20.0
        and main_selection_changes >= 50
        and float(main10["overlay_roi_pct"]) > float(main10["base_roi_pct"])
        and overlay_brier > base_brier
    ):
        verdict = "ROI IMPROVED, PROBABILITY QUALITY WORSE - SHADOW ONLY"
    elif abs(main_delta_pnl) < 2.0 and main_selection_changes < 10:
        verdict = "NO MATERIAL CHANGE"

    with open(report, "w", encoding="utf-8", newline="") as f:
        f.write(f"{overlay_label} comparison\n")
        f.write("================================\n\n")
        f.write(f"Verdict: {verdict}\n")
        f.write(f"Scope: ATP 2024-2025, paired current-code baseline vs {overlay_label}.\n")
        f.write("CPI is lag-only. Same-season CPI is not used. This is not a live lane.\n\n")
        f.write(f"Paired rows: {len(paired)}\n")
        f.write(
            f"Probability quality: baseline brier={base_brier:.5f}, logloss={base_logloss:.5f} "
            f"(n={base_n}); overlay brier={overlay_brier:.5f}, logloss={overlay_logloss:.5f} "
            f"(n={overlay_n}).\n\n"
        )
        f.write("Main selection comparison\n")
        f.write("-------------------------\n")
        f.write(_fmt_row(main5) + "\n")
        f.write(_fmt_row(main10) + "\n\n")
        f.write("Surface split at value>=10\n")
        f.write("--------------------------\n")
        for value in ("Hard", "Clay", "Grass"):
            row = lookup.get((10.0, "surface", value))
            if row:
                f.write(_fmt_row(row) + "\n")
        f.write("\nModel-surface split at value>=10\n")
        f.write("--------------------------------\n")
        for value in ("Hard", "Clay", "Grass", "SpeedSlow", "SpeedNeutral", "SpeedFast"):
            row = lookup.get((10.0, "model_surface", value))
            if row:
                f.write(_fmt_row(row) + "\n")
        f.write("\nCPI speed bucket split at value>=10\n")
        f.write("-----------------------------------\n")
        for value in ("slow", "neutral", "fast", "missing"):
            row = lookup.get((10.0, "cpi_bucket", value))
            if row:
                f.write(_fmt_row(row) + "\n")
        f.write("\nSurface x CPI bucket at value>=10\n")
        f.write("---------------------------------\n")
        sx_rows = [
            r
            for r in rows
            if r["threshold"] == 10.0
            and r["segment"] == "surface_cpi_bucket"
            and int(r["overlay_bets"]) + int(r["base_bets"]) > 0
        ]
        for row in sorted(sx_rows, key=lambda r: (str(r["value"]), -int(r["overlay_bets"]))):
            f.write(_fmt_row(row) + "\n")
        f.write("\nDecision notes\n")
        f.write("--------------\n")
        if verdict in {"NO LIVE PROMOTION", "NO MATERIAL CHANGE"}:
            f.write("- This CPI experiment is not a production improvement on this paired test.\n")
            if verdict == "NO MATERIAL CHANGE":
                f.write("- It changed too few selections to be meaningful; treat the tiny P/L move as noise.\n")
            f.write("- Keep CPI as a monitor/research map, not a signal generator.\n")
            f.write("- Use the report to design gated cells, not to broaden grass blindly.\n")
        elif verdict.startswith("ROI IMPROVED"):
            f.write("- The regime model improved selected-bet ROI, but worsened broad probability quality.\n")
            f.write("- Treat this as a shadow candidate: profile-specific gates only, no broad live routing.\n")
            f.write("- Next test should isolate profitable regime cells and retune calibration for model_surface.\n")
        else:
            f.write("- The CPI experiment improved the paired test, but this still needs held-out gate discipline.\n")
            f.write("- Do not activate broad CPI routing without profile-level and surface-level checks.\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare CPI shadow/regime backtests against cpi-base.")
    parser.add_argument("--base-suffix", default="cpi-base")
    parser.add_argument("--overlay-suffix", default="cpi-shadow")
    parser.add_argument("--output-prefix", default="cpi-shadow-overlay")
    parser.add_argument("--overlay-label", default=None)
    args = parser.parse_args()

    overlay_label = args.overlay_label or args.overlay_suffix
    base = _load_rows(args.base_suffix)
    overlay = _load_rows(args.overlay_suffix)
    common_keys = sorted(set(base) & set(overlay))
    paired = [(base[k], overlay[k]) for k in common_keys]
    rows: list[dict[str, Any]] = []
    for threshold in THRESHOLDS:
        rows.extend(_segment_rows(paired, threshold))
    cells_path = _write_cells(rows, args.output_prefix)
    report_path = _write_report(
        paired,
        rows,
        [base[k] for k in common_keys],
        [overlay[k] for k in common_keys],
        output_prefix=args.output_prefix,
        overlay_label=overlay_label,
    )
    print(f"Paired rows: {len(paired)}")
    print(f"Wrote {cells_path}")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
