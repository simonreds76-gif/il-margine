from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "backtest" / "strict-signals-spreadv1-archive.csv"
REPORT_TXT = ROOT / "data" / "backtest" / "spread-v1-segment-report.txt"
REPORT_CSV = ROOT / "data" / "backtest" / "spread-v1-segment-report.csv"


def to_float(value: object, default: float | None = None) -> float | None:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def to_boolish(value: object) -> bool | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"1", "true", "t", "yes", "y", "win", "won"}:
        return True
    if text in {"0", "false", "f", "no", "n", "loss", "lost"}:
        return False
    return None


def bucket_edge(edge: float | None) -> str:
    if edge is None:
        return "unknown"
    if edge < 10:
        return "00-10"
    if edge < 15:
        return "10-15"
    if edge < 20:
        return "15-20"
    return "20+"


def bucket_line_abs(line: float | None) -> str:
    if line is None:
        return "unknown"
    value = abs(line)
    if value < 2:
        return "00-1.5"
    if value < 4:
        return "02-3.5"
    return "04+"


def bucket_odds(odds: float | None) -> str:
    if odds is None:
        return "unknown"
    if odds < 1.85:
        return "<1.85"
    if odds < 1.95:
        return "1.85-1.95"
    return "1.95+"


def display_line(row: dict[str, str]) -> float | None:
    line = to_float(row.get("spread_line"))
    side = (row.get("side") or "").strip()
    if line is None:
        return None
    if side == "P2-":
        return -line
    return line


def orientation(row: dict[str, str]) -> str:
    line = display_line(row)
    if line is None:
        return "unknown"
    if line > 0:
        return "dog_handicap"
    if line < 0:
        return "favorite_handicap"
    return "scratch"


def row_result(row: dict[str, str]) -> tuple[str, float, float]:
    odds = to_float(row.get("spread_odds")) or to_float(row.get("pin_odds1")) or 0.0
    stake = to_float(row.get("stake_units"), 2.0) or 2.0
    outcome = (row.get("bet_outcome") or row.get("result") or "").strip().lower()
    won = to_boolish(row.get("won_bet"))
    if "push" in outcome or "void" in outcome:
        return "push", 0.0, stake
    if won is True or outcome in {"win", "won"}:
        return "win", stake * max(odds - 1.0, 0.0), stake
    if won is False or outcome in {"loss", "lost"}:
        return "loss", -stake, stake
    return "unknown", 0.0, 0.0


def normal_value(value: str | None) -> str:
    text = (value or "").strip()
    return text if text else "unknown"


def enrich(row: dict[str, str]) -> dict[str, object]:
    result, pnl, staked = row_result(row)
    line = display_line(row)
    edge = to_float(row.get("value_pct"))
    odds = to_float(row.get("spread_odds"))
    model_guard = normal_value(row.get("ml_short_fav_model_guard")).lower()
    market_guard = normal_value(row.get("ml_short_fav_market_guard")).lower()
    dog_guard = normal_value(row.get("short_fav_dog_spread_guard")).lower()
    return {
        **row,
        "_result": result,
        "_pnl": pnl,
        "_staked": staked,
        "_display_line": line,
        "_orientation": orientation(row),
        "_line_abs_bucket": bucket_line_abs(line),
        "_edge_bucket": bucket_edge(edge),
        "_odds_bucket": bucket_odds(odds),
        "_guard_combo": f"model={model_guard}|market={market_guard}|dog={dog_guard}",
        "_edge": edge,
        "_odds": odds,
    }


def load_rows() -> list[dict[str, object]]:
    if not INPUT.exists():
        raise FileNotFoundError(f"Missing input: {INPUT}")
    with INPUT.open(newline="", encoding="utf-8-sig") as f:
        raw_rows = list(csv.DictReader(f))
    rows: list[dict[str, object]] = []
    for row in raw_rows:
        if (row.get("bet_type") or "").strip().lower() != "spread":
            continue
        if (row.get("settlement_status") or "").strip().lower() != "settled":
            continue
        enriched = enrich(row)
        if enriched["_result"] == "unknown":
            continue
        rows.append(enriched)
    return rows


def summarize(rows: Iterable[dict[str, object]]) -> dict[str, object]:
    selected = list(rows)
    wins = sum(1 for r in selected if r["_result"] == "win")
    losses = sum(1 for r in selected if r["_result"] == "loss")
    pushes = sum(1 for r in selected if r["_result"] == "push")
    pnl = sum(float(r["_pnl"]) for r in selected)
    staked = sum(float(r["_staked"]) for r in selected)
    roi = (pnl / staked * 100.0) if staked else 0.0
    edges = [float(r["_edge"]) for r in selected if r["_edge"] is not None]
    odds = [float(r["_odds"]) for r in selected if r["_odds"] is not None]
    return {
        "n": len(selected),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "pnl": pnl,
        "staked": staked,
        "roi_pct": roi,
        "avg_edge": mean(edges) if edges else 0.0,
        "avg_odds": mean(odds) if odds else 0.0,
    }


def current_bounded_gate(row: dict[str, object], *, include_clay: bool) -> bool:
    """Replay the current spread-v1 safety gate against historical archived rows."""
    surface = normal_value(str(row.get("surface", "")))
    series = normal_value(str(row.get("series", "")))
    confidence = normal_value(str(row.get("confidence", ""))).lower()
    line = row.get("_display_line")
    edge = row.get("_edge")
    if not isinstance(line, (int, float)) or not isinstance(edge, (int, float)):
        return False
    if edge < 10.0 or edge > 18.0:
        return False
    if line >= 0 or abs(float(line)) < 2.0 or abs(float(line)) > 3.5:
        return False
    if surface == "Hard":
        return series != "Grand Slam"
    if surface == "Clay" and include_clay:
        return series in {"ATP250", "ATP500"} and confidence == "high"
    return False


def segment_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    dimensions = [
        ("orientation", "_orientation"),
        ("line_abs_bucket", "_line_abs_bucket"),
        ("edge_bucket", "_edge_bucket"),
        ("odds_bucket", "_odds_bucket"),
        ("surface", "surface"),
        ("series", "series"),
        ("confidence", "confidence"),
        ("calibration_reason", "spread_calibration_reason"),
        ("guard_combo", "_guard_combo"),
        ("orientation_x_line", ("_orientation", "_line_abs_bucket")),
        ("orientation_x_edge", ("_orientation", "_edge_bucket")),
        ("surface_x_orientation", ("surface", "_orientation")),
        ("series_x_orientation", ("series", "_orientation")),
    ]
    out: list[dict[str, object]] = []
    for dimension, field in dimensions:
        buckets: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            if isinstance(field, tuple):
                value = " | ".join(normal_value(str(row.get(part, ""))) for part in field)
            else:
                value = normal_value(str(row.get(field, "")))
            buckets[value].append(row)
        for value, bucket_rows in buckets.items():
            stats = summarize(bucket_rows)
            out.append({"dimension": dimension, "value": value, **stats})
    out.sort(key=lambda r: (str(r["dimension"]), -int(r["n"]), str(r["value"])))
    return out


def fmt_stats(stats: dict[str, object]) -> str:
    return (
        f"{int(stats['n'])} bets, {int(stats['wins'])}W/{int(stats['losses'])}L/"
        f"{int(stats['pushes'])}P, PnL {float(stats['pnl']):+.2f}u, "
        f"staked {float(stats['staked']):.1f}u, ROI {float(stats['roi_pct']):+.1f}%"
    )


def write_csv(rows: list[dict[str, object]]) -> None:
    REPORT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "dimension",
        "value",
        "n",
        "wins",
        "losses",
        "pushes",
        "pnl",
        "staked",
        "roi_pct",
        "avg_edge",
        "avg_odds",
    ]
    with REPORT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "pnl": round(float(row["pnl"]), 4),
                    "staked": round(float(row["staked"]), 4),
                    "roi_pct": round(float(row["roi_pct"]), 4),
                    "avg_edge": round(float(row["avg_edge"]), 4),
                    "avg_odds": round(float(row["avg_odds"]), 4),
                }
            )


def write_report(rows: list[dict[str, object]], segments: list[dict[str, object]]) -> None:
    overall = summarize(rows)
    live_gate = summarize([r for r in rows if current_bounded_gate(r, include_clay=False)])
    clay_research_gate = summarize([r for r in rows if current_bounded_gate(r, include_clay=True)])
    min_block_n = 8
    block_flags = [
        s
        for s in segments
        if int(s["n"]) >= min_block_n
        and str(s["dimension"]) in {"orientation", "line_abs_bucket", "edge_bucket", "odds_bucket", "surface", "series", "orientation_x_line", "surface_x_orientation"}
        and float(s["roi_pct"]) <= -10.0
    ]
    promote_watch = [
        s
        for s in segments
        if int(s["n"]) >= min_block_n
        and str(s["dimension"]) in {"orientation", "line_abs_bucket", "edge_bucket", "odds_bucket", "surface", "series", "orientation_x_line", "surface_x_orientation"}
        and float(s["roi_pct"]) >= 5.0
    ]
    block_flags.sort(key=lambda s: float(s["roi_pct"]))
    promote_watch.sort(key=lambda s: float(s["roi_pct"]), reverse=True)

    lines = [
        "Tennis spread V1 segment report",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"Input: {INPUT.relative_to(ROOT)}",
        "",
        f"Overall settled spread V1: {fmt_stats(overall)}",
        f"Current bounded gate replay (default hard-only): {fmt_stats(live_gate)}",
        f"Current bounded gate replay (clay research enabled): {fmt_stats(clay_research_gate)}",
        "",
        "Largest segments",
    ]
    for segment in sorted(segments, key=lambda s: int(s["n"]), reverse=True)[:14]:
        lines.append(
            f"- {segment['dimension']}={segment['value']}: {fmt_stats(segment)} "
            f"(avg edge {float(segment['avg_edge']):.1f}%, avg odds {float(segment['avg_odds']):.3f})"
        )
    lines.extend(["", f"Risk flags (n >= {min_block_n}, ROI <= -10%)"])
    if block_flags:
        for segment in block_flags[:12]:
            lines.append(f"- Block/watch {segment['dimension']}={segment['value']}: {fmt_stats(segment)}")
    else:
        lines.append("- No hard block from current sample size.")
    lines.extend(["", f"Positive watchlist (n >= {min_block_n}, ROI >= +5%)"])
    if promote_watch:
        for segment in promote_watch[:12]:
            lines.append(f"- Keep/promote {segment['dimension']}={segment['value']}: {fmt_stats(segment)}")
    else:
        lines.append("- No segment clears a promotion watch threshold yet.")
    lines.extend(
        [
            "",
            "Interpretation",
            "- Treat this as a live-sample policy report, not a permanent truth; sample is still small.",
            "- A segment should not be promoted just because one tiny bucket is green.",
            "- A segment with 8+ bets and clearly negative ROI is enough to tighten gates now, then re-test weekly.",
        ]
    )
    REPORT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    rows = load_rows()
    segments = segment_rows(rows)
    write_csv(segments)
    write_report(rows, segments)
    print(f"Wrote {REPORT_TXT}")
    print(f"Wrote {REPORT_CSV}")


if __name__ == "__main__":
    main()
