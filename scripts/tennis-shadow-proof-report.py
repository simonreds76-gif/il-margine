#!/usr/bin/env python3
"""Build a compact proof report for tennis strict/shadow lanes.

This is a local decision aid. It does not create signals or change routing.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "backtest"


@dataclass(frozen=True)
class LaneConfig:
    key: str
    label: str
    archive_paths: tuple[str, ...]
    live_paths: tuple[str, ...] = ()
    clv_paths: tuple[str, ...] = ()
    note: str = ""


LANES = [
    LaneConfig(
        key="strict_ml",
        label="Strict ML",
        archive_paths=("strict-signals-archive.csv",),
        live_paths=("strict-signals-live.csv",),
        clv_paths=("strict-clv-audit-2026.csv",),
        note="Production strict lane. Only hard/Masters/high-confidence should be treated as live-grade.",
    ),
    LaneConfig(
        key="volume_200",
        label="Volume 200",
        archive_paths=("strict-signals-volume200-archive.csv",),
        clv_paths=("strict-clv-audit-volume200-2026.csv",),
        note="Measured expansion. Keep bundled under strict until live CLV sample grows.",
    ),
    LaneConfig(
        key="spread_v1",
        label="Spread v1",
        archive_paths=("strict-signals-spreadv1-archive.csv",),
        clv_paths=("strict-clv-audit-spreadv1-2026.csv", "strict-clv-audit-spreadv1-spread-2026.csv"),
        note="Spread shadow/research. Needs positive CLV and orientation proof before promotion.",
    ),
    LaneConfig(
        key="grass_bo3",
        label="Grass bo3",
        archive_paths=("strict-signals-grass_bo3-archive.csv", "strict-signals-grass_bo3.csv"),
        live_paths=("strict-signals-grass_bo3-live.csv",),
        clv_paths=("strict-clv-audit-grass_bo3-2026.csv",),
        note="Grass shadow lane. Treat as no-bet until settled ROI and CLV exist.",
    ),
    LaneConfig(
        key="cpi_speed_shadow",
        label="CPI speed shadow",
        archive_paths=("strict-signals-cpi_speed-archive.csv", "strict-signals-cpi_speed.csv"),
        live_paths=("strict-signals-cpi_speed-live.csv",),
        clv_paths=("strict-clv-audit-cpi_speed-2026.csv",),
        note="Court-speed shadow lane. Live proof matters more than backtest delta.",
    ),
    LaneConfig(
        key="clay_bo3",
        label="Clay bo3",
        archive_paths=("strict-signals-clay_bo3-archive.csv",),
        live_paths=("strict-signals-clay_bo3-live.csv",),
        clv_paths=("strict-clv-audit-clay_bo3-2026.csv", "strict-clv-audit-clay_bo3-spread-2026.csv"),
        note="Clay shadow only. Do not revive broad clay just because a small cell looks good.",
    ),
    LaneConfig(
        key="challenger_ml",
        label="Challenger ML v2 prospective",
        archive_paths=("strict-signals-challenger-ml-v2-archive.csv",),
        live_paths=("strict-signals-challenger-ml-v2-live.csv",),
        clv_paths=("strict-clv-audit-challenger-ml-v2-2026.csv",),
        note="Zero-stake evidence only. Legacy 23-row batch is frozen and excluded.",
    ),
]


def read_first_csv(paths: Iterable[str]) -> tuple[list[dict[str, str]], str]:
    for rel in paths:
        path = DATA / rel
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle)), rel
    return [], ""


def read_all_csv(paths: Iterable[str]) -> tuple[list[dict[str, str]], list[str]]:
    rows: list[dict[str, str]] = []
    used: list[str] = []
    for rel in paths:
        path = DATA / rel
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            chunk = list(csv.DictReader(handle))
        rows.extend(chunk)
        used.append(rel)
    return rows, used


def num(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if parsed == parsed else None


def row_status(row: dict[str, str]) -> str:
    status = (row.get("settlement_status") or row.get("status") or "").strip().lower()
    result = (row.get("won_bet") or row.get("bet_outcome") or row.get("result") or "").strip().lower()
    if status in {"void", "cancelled", "push"} or result in {"void", "push", "p"}:
        return "void"
    if result in {"true", "1", "won", "win", "w"} or "won" in result:
        return "won"
    if result in {"false", "0", "lost", "loss", "l"} or "lost" in result:
        return "lost"
    if status == "settled":
        return "settled_unknown"
    return "pending"


def pnl_units(row: dict[str, str]) -> float | None:
    status = row_status(row)
    stake = num(row.get("stake_units")) or 1.0
    if status == "lost":
        return -stake
    if status != "won":
        return None
    odds = None
    if (row.get("bet_type") or "").lower() == "spread":
        odds = num(row.get("spread_odds"))
    if odds is None:
        side = (row.get("side") or "").upper()
        odds = num(row.get("pin_odds2" if side == "P2" else "pin_odds1"))
    if odds is None:
        odds = num(row.get("odds")) or num(row.get("bookmaker_odds"))
    if odds is None:
        return None
    return (odds - 1.0) * stake


def clv_value(row: dict[str, str]) -> float | None:
    return num(row.get("clv_implied_delta_pct")) or num(row.get("clv_pct")) or num(row.get("avg_clv_pct"))


def verdict(settled: int, pending: int, roi_pct: float | None, clv_n: int, avg_clv_pct: float | None, positive_clv_pct: float | None) -> str:
    if settled == 0:
        return "COLLECTING" if pending > 0 else "NO SAMPLE"
    if settled < 30:
        return "TOO EARLY"
    if clv_n == 0:
        return "ROI ONLY - CLV MISSING"
    if settled >= 100 and clv_n >= 50 and (roi_pct or 0.0) >= 0 and (avg_clv_pct or 0.0) >= 0.5 and (positive_clv_pct or 0.0) >= 52.0:
        return "PROMOTION WATCH"
    if (roi_pct or 0.0) < -5.0 or (avg_clv_pct or 0.0) < -0.5:
        return "CAUTION"
    return "SHADOW HOLD"


def summarize_lane(lane: LaneConfig) -> dict[str, str]:
    archive_rows, archive_source = read_first_csv(lane.archive_paths)
    live_rows, live_source = read_first_csv(lane.live_paths)
    clv_rows, clv_sources = read_all_csv(lane.clv_paths)

    statuses = [row_status(row) for row in archive_rows]
    wins = statuses.count("won")
    losses = statuses.count("lost")
    voids = statuses.count("void")
    pending = statuses.count("pending") + len(live_rows)
    settled = wins + losses
    pnl_values = [value for row in archive_rows if (value := pnl_units(row)) is not None]
    stake_values = [num(row.get("stake_units")) or 1.0 for row, status in zip(archive_rows, statuses) if status in {"won", "lost"}]
    total_pnl = sum(pnl_values)
    total_stake = sum(stake_values)
    roi_pct = (total_pnl / total_stake * 100.0) if total_stake > 0 else None

    clv_values = [value for row in clv_rows if (value := clv_value(row)) is not None]
    avg_clv = sum(clv_values) / len(clv_values) if clv_values else None
    positive_clv = (sum(1 for value in clv_values if value > 0) / len(clv_values) * 100.0) if clv_values else None

    return {
        "lane": lane.key,
        "label": lane.label,
        "archive_source": archive_source,
        "live_source": live_source,
        "signals": str(len(archive_rows)),
        "live_rows": str(len(live_rows)),
        "pending": str(pending),
        "settled": str(settled),
        "wins": str(wins),
        "losses": str(losses),
        "voids": str(voids),
        "pnl_units": f"{total_pnl:.2f}",
        "roi_pct": "" if roi_pct is None else f"{roi_pct:.2f}",
        "clv_rows": str(len(clv_values)),
        "avg_clv_pct": "" if avg_clv is None else f"{avg_clv:.2f}",
        "positive_clv_pct": "" if positive_clv is None else f"{positive_clv:.1f}",
        "verdict": verdict(settled, pending, roi_pct, len(clv_values), avg_clv, positive_clv),
        "clv_sources": ";".join(clv_sources),
        "note": lane.note,
    }


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "lane",
        "label",
        "archive_source",
        "live_source",
        "signals",
        "live_rows",
        "pending",
        "settled",
        "wins",
        "losses",
        "voids",
        "pnl_units",
        "roi_pct",
        "clv_rows",
        "avg_clv_pct",
        "positive_clv_pct",
        "verdict",
        "clv_sources",
        "note",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_txt(rows: list[dict[str, str]], path: Path) -> None:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "TENNIS SHADOW PROOF REPORT",
        f"Generated: {generated}",
        "",
        "Use this as the local decision sheet. Public/live promotion still needs explicit human approval.",
        "",
    ]
    for row in rows:
        roi = f"{row['roi_pct']}%" if row["roi_pct"] else "n/a"
        clv = f"{row['avg_clv_pct']}%" if row["avg_clv_pct"] else "n/a"
        pos = f"{row['positive_clv_pct']}%" if row["positive_clv_pct"] else "n/a"
        lines.extend(
            [
                f"{row['label']} [{row['verdict']}]",
                f"  signals={row['signals']} live={row['live_rows']} pending={row['pending']} settled={row['settled']} record={row['wins']}W-{row['losses']}L void={row['voids']}",
                f"  pnl={row['pnl_units']}u roi={roi} clv_n={row['clv_rows']} avg_clv={clv} positive_clv={pos}",
                f"  source={row['archive_source'] or 'missing'} clv={row['clv_sources'] or 'missing'}",
                f"  note={row['note']}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=str(DATA / "tennis-shadow-proof-report.csv"))
    parser.add_argument("--txt", default=str(DATA / "tennis-shadow-proof-report.txt"))
    args = parser.parse_args()

    rows = [summarize_lane(lane) for lane in LANES]
    write_csv(rows, Path(args.csv))
    write_txt(rows, Path(args.txt))
    print(f"Wrote {args.csv}")
    print(f"Wrote {args.txt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
