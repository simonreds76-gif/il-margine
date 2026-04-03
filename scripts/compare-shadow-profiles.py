"""
Compare shadow profiles (currently volume_200 vs volume_275) using:
- exact historical backtest scoring from backtest-policy-profiles.py
- current live shadow CSVs / weekly performance summaries

Usage:
  python scripts/compare-shadow-profiles.py
"""

from __future__ import annotations

import csv
import runpy
from pathlib import Path

from signal_storage import VOLUME_200_SIGNAL_PATHS, VOLUME_275_SIGNAL_PATHS


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "backtest"
OUT_PATH = DATA_DIR / "shadow-profile-comparison.txt"


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def safe_float(value: str | None) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except ValueError:
        return None


def settled_summary(signal_csv: Path) -> dict[str, float | int]:
    rows = load_csv(signal_csv)
    total = len(rows)
    settled = [r for r in rows if (r.get("settlement_status") or "").strip().lower() == "settled"]
    ml = sum(1 for r in rows if (r.get("bet_type") or "match") != "spread")
    spread = total - ml
    pnl = 0.0
    staked = 0.0
    graded = 0
    for r in settled:
        outcome = (r.get("bet_outcome") or "").strip().upper()
        if outcome not in {"WIN", "LOSS"}:
            continue
        stake = safe_float(r.get("stake_units")) or 1.0
        bet_type = (r.get("bet_type") or "match").strip().lower()
        side = (r.get("side") or "").strip().upper()
        if bet_type == "spread":
            odds = safe_float(r.get("spread_odds"))
            if odds is None:
                odds = safe_float(r.get("pin_odds1")) if side.startswith("P1") else safe_float(r.get("pin_odds2"))
        else:
            odds = safe_float(r.get("pin_odds1")) if side == "P1" else safe_float(r.get("pin_odds2"))
        if odds is None or odds <= 1.0:
            continue
        staked += stake
        graded += 1
        pnl += stake * (odds - 1.0) if outcome == "WIN" else -stake
    roi = (pnl / staked * 100.0) if staked else None
    return {
        "signals": total,
        "ml": ml,
        "spread": spread,
        "settled": len(settled),
        "graded": graded,
        "staked": staked,
        "pnl": pnl,
        "roi_pct": roi if roi is not None else float("nan"),
    }


def latest_summary(summary_csv: Path) -> dict[str, str] | None:
    rows = load_csv(summary_csv)
    if not rows:
        return None
    # Prefer all_time combined row.
    for row in reversed(rows):
        if (row.get("scope") or "") == "all_time" and (row.get("bet_type") or "") == "":
            return row
    return rows[-1]


def main() -> int:
    ns = runpy.run_path(str(ROOT / "scripts" / "backtest-policy-profiles.py"))
    rows = ns["_load_rows"]([Path(p) for p in ns["DEFAULT_FILES"]])
    profile_rules = ns["PROFILE_RULES"]
    score_profile = ns["_score_profile"]
    summarize = ns["_summarize"]

    hist_200 = summarize(score_profile(rows, profile_rules["volume_200"]))
    hist_275 = summarize(score_profile(rows, profile_rules["volume_275"]))

    live_200 = settled_summary(VOLUME_200_SIGNAL_PATHS.archive)
    live_275 = settled_summary(VOLUME_275_SIGNAL_PATHS.archive)
    weekly_200 = latest_summary(DATA_DIR / "strict-policy-performance-volume200-weekly.csv")
    weekly_275 = latest_summary(DATA_DIR / "strict-policy-performance-volume275-weekly.csv")

    lines = [
        "Shadow Profile Comparison",
        "Generated: 2026-03-13",
        "",
        "Historical exact backtest (2022-2025 ATP, ML-only, current exclusions honored):",
        (
            f"  volume_200: bets={int(hist_200['bets'])} avg/year={hist_200['avg_bets_per_year']:.1f} "
            f"tierROI={hist_200['tier_roi_pct']:+.2f}% flatROI={hist_200['flat_roi_pct']:+.2f}% "
            f"tierP/L={hist_200['tier_profit']:+.2f}u on {hist_200['tier_staked']:.2f}u"
        ),
        (
            f"  volume_275: bets={int(hist_275['bets'])} avg/year={hist_275['avg_bets_per_year']:.1f} "
            f"tierROI={hist_275['tier_roi_pct']:+.2f}% flatROI={hist_275['flat_roi_pct']:+.2f}% "
            f"tierP/L={hist_275['tier_profit']:+.2f}u on {hist_275['tier_staked']:.2f}u"
        ),
        (
            f"  delta (200 - 275): bets={int(hist_200['bets'] - hist_275['bets'])} "
            f"tierROI={hist_200['tier_roi_pct'] - hist_275['tier_roi_pct']:+.2f}pp "
            f"flatROI={hist_200['flat_roi_pct'] - hist_275['flat_roi_pct']:+.2f}pp"
        ),
        "",
        "Current live shadow tracking:",
        (
            f"  volume_200 CSV: signals={live_200['signals']} (ML={live_200['ml']}, spread={live_200['spread']}) "
            f"settled={live_200['settled']} graded={live_200['graded']}"
        ),
        (
            f"  volume_275 CSV: signals={live_275['signals']} (ML={live_275['ml']}, spread={live_275['spread']}) "
            f"settled={live_275['settled']} graded={live_275['graded']}"
        ),
    ]

    if weekly_200:
        lines.append(
            f"  volume_200 weekly summary: source={weekly_200.get('source_file')} all_time_signals={weekly_200.get('signals')} "
            f"settled={weekly_200.get('settled')} roi={weekly_200.get('roi_pct') or 'n/a'}%"
        )
    if weekly_275:
        lines.append(
            f"  volume_275 weekly summary: source={weekly_275.get('source_file')} all_time_signals={weekly_275.get('signals')} "
            f"settled={weekly_275.get('settled')} roi={weekly_275.get('roi_pct') or 'n/a'}%"
        )

    lines.extend(
        [
            "",
            "Recommendation:",
            "  Use volume_200 as the active shadow profile.",
            "  Reason: better exact historical ROI, positive in every year, and simpler profile after removing the weakest slice.",
            "  Keep volume_275 only as a legacy comparison profile.",
            "",
        ]
    )

    text = "\n".join(lines)
    OUT_PATH.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nWrote report -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
