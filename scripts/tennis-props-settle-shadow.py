#!/usr/bin/env python3
"""Settle internal Bet365 tennis aces/DF shadow signals from Sackmann service stats."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parent.parent
PROPS_DIR = ROOT / "data" / "tennis-props"
DEFAULT_SIGNALS = PROPS_DIR / "shadow" / "aces-dfs-shadow-signals.csv"
DEFAULT_PERFORMANCE = PROPS_DIR / "shadow" / "aces-dfs-shadow-performance.txt"
DEFAULT_SACKMANN = ROOT / "data" / "sackmann"

FIELDNAMES = [
    "signal_id",
    "logged_at_utc",
    "date",
    "tour",
    "tournament",
    "player",
    "opponent",
    "market",
    "line",
    "side",
    "projection_mean",
    "confidence",
    "bookmaker",
    "over_odds",
    "under_odds",
    "selected_odds",
    "fair_over_odds",
    "fair_under_odds",
    "fair_odds",
    "value_over_pct",
    "value_under_pct",
    "value_pct",
    "matched_board",
    "notes",
    "source_file",
    "settlement_status",
    "actual",
    "result",
    "pnl",
    "settled_at_utc",
    "settlement_note",
]


def norm_text(value: object) -> str:
    raw = str(value or "").strip()
    if "," in raw:
        last, first = raw.split(",", 1)
        if last.strip() and first.strip():
            raw = f"{first.strip()} {last.strip()}"
    text = unicodedata.normalize("NFKD", raw)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def pair_key(a: object, b: object) -> tuple[str, str]:
    return tuple(sorted((norm_text(a), norm_text(b))))  # type: ignore[return-value]


def parse_float(value: object) -> float | None:
    try:
        text = str(value or "").strip()
        if not text:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def parse_year(value: object) -> int | None:
    text = str(value or "").strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def sackmann_year(value: object) -> int | None:
    text = str(value or "").strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDNAMES})


def is_void_score(score: object) -> bool:
    text = str(score or "").upper()
    return any(token in text for token in ("RET", "W/O", "WO", "DEF", "ABD"))


def market_count(row: dict[str, str], player_norm: str, market: str) -> tuple[int | None, str]:
    winner = norm_text(row.get("winner_name"))
    loser = norm_text(row.get("loser_name"))
    is_winner = player_norm == winner
    is_loser = player_norm == loser
    if not is_winner and not is_loser:
        return None, "player_not_in_match"
    lower = market.lower().replace(" ", "_")
    if lower in {"aces", "ace", "player_aces"}:
        raw = row.get("w_ace") if is_winner else row.get("l_ace")
    elif lower in {"double_faults", "double_fault", "dfs", "df"}:
        raw = row.get("w_df") if is_winner else row.get("l_df")
    else:
        return None, "unsupported_market"
    parsed = parse_float(raw)
    if parsed is None:
        return None, "missing_service_stat"
    return int(round(parsed)), "ok"


def result_for(actual: int, line: float, side: str) -> str:
    if actual == line:
        return "push"
    if side == "OVER":
        return "win" if actual > line else "loss"
    if side == "UNDER":
        return "win" if actual < line else "loss"
    return "void"


def pnl_for(result: str, odds: float | None) -> float:
    if result == "win" and odds and odds > 1:
        return odds - 1.0
    if result == "loss":
        return -1.0
    return 0.0


def load_sackmann_index(sackmann_dir: Path) -> dict[tuple[str, int, tuple[str, str]], list[dict[str, str]]]:
    index: dict[tuple[str, int, tuple[str, str]], list[dict[str, str]]] = defaultdict(list)
    for path in sorted(sackmann_dir.glob("*_matches_20*.csv")):
        if "qual_chall" in path.name:
            continue
        tour = "ATP" if path.name.startswith("atp_") else "WTA" if path.name.startswith("wta_") else ""
        if not tour:
            continue
        for row in read_csv(path):
            year = sackmann_year(row.get("tourney_date"))
            if year is None:
                continue
            key = (tour, year, pair_key(row.get("winner_name"), row.get("loser_name")))
            index[key].append(row)
    return index


def tournament_overlap(signal_tournament: str, sackmann_tournament: str) -> bool:
    sig = norm_text(signal_tournament)
    sm = norm_text(sackmann_tournament)
    if not sig or not sm:
        return False
    if sig in sm or sm in sig:
        return True
    slam_aliases = {
        "french open": "roland garros",
        "roland garros": "roland garros",
        "australian open": "australian open",
        "wimbledon": "wimbledon",
        "us open": "us open",
        "u s open": "us open",
    }
    return slam_aliases.get(sig, sig) == slam_aliases.get(sm, sm)


def choose_candidate(signal: dict[str, str], candidates: list[dict[str, str]]) -> dict[str, str] | None:
    if not candidates:
        return None
    tournament = signal.get("tournament", "")
    overlapped = [r for r in candidates if tournament_overlap(tournament, r.get("tourney_name", ""))]
    pool = overlapped or candidates
    pool = sorted(pool, key=lambda r: str(r.get("tourney_date") or ""), reverse=True)
    return pool[0] if len(pool) == 1 or overlapped else pool[0]


def write_performance(path: Path, rows: list[dict[str, str]]) -> None:
    settled = [r for r in rows if (r.get("settlement_status") or "").lower() == "settled"]
    pending = [r for r in rows if (r.get("settlement_status") or "").lower() == "pending"]
    voids = [r for r in rows if (r.get("settlement_status") or "").lower() == "void"]
    pnl = sum(parse_float(r.get("pnl")) or 0.0 for r in settled)
    roi = pnl / len(settled) * 100.0 if settled else 0.0

    def bucket(label: str, key: str) -> list[str]:
        out = [f"\n{label}:"]
        for value in sorted({r.get(key, "") or "-" for r in rows}):
            subset = [r for r in rows if (r.get(key, "") or "-") == value]
            settled_subset = [r for r in subset if (r.get("settlement_status") or "").lower() == "settled"]
            subset_pnl = sum(parse_float(r.get("pnl")) or 0.0 for r in settled_subset)
            subset_roi = subset_pnl / len(settled_subset) * 100.0 if settled_subset else 0.0
            out.append(f"  {value}: rows={len(subset)} settled={len(settled_subset)} pnl={subset_pnl:+.2f}u roi={subset_roi:+.1f}%")
        return out

    lines = [
        "Tennis aces/DF shadow evidence",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "Status: internal shadow only; no public betting record or live staking.",
        f"Rows: {len(rows)} | settled: {len(settled)} | pending: {len(pending)} | void: {len(voids)}",
        f"PnL: {pnl:+.2f}u | ROI: {roi:+.1f}%",
        "Promotion guard: do not read ROI seriously before 300 settled lines across at least two Slams.",
    ]
    for label, key in [("By market", "market"), ("By side", "side"), ("By tour", "tour"), ("By confidence", "confidence")]:
        lines.extend(bucket(label, key))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Settle tennis aces/DF shadow signals from Sackmann service stats")
    parser.add_argument("--signals", default=str(DEFAULT_SIGNALS))
    parser.add_argument("--performance", default=str(DEFAULT_PERFORMANCE))
    parser.add_argument("--sackmann-dir", default=str(DEFAULT_SACKMANN))
    args = parser.parse_args()

    signals_path = Path(args.signals)
    rows = read_csv(signals_path)
    if not rows:
        write_performance(Path(args.performance), rows)
        print(f"No shadow rows to settle: {signals_path}")
        return 0

    index = load_sackmann_index(Path(args.sackmann_dir))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    settled_now = 0
    still_pending = 0

    for row in rows:
        status = (row.get("settlement_status") or "pending").lower()
        if status not in {"", "pending"}:
            continue
        year = parse_year(row.get("date"))
        tour = (row.get("tour") or "").upper()
        if year is None or tour not in {"ATP", "WTA"}:
            row["settlement_status"] = "pending"
            row["settlement_note"] = "missing_tour_or_year"
            still_pending += 1
            continue
        key = (tour, year, pair_key(row.get("player"), row.get("opponent")))
        candidate = choose_candidate(row, index.get(key, []))
        if candidate is None:
            row["settlement_status"] = "pending"
            row["settlement_note"] = "sackmann_match_not_found"
            still_pending += 1
            continue
        if is_void_score(candidate.get("score")):
            row["settlement_status"] = "void"
            row["actual"] = ""
            row["result"] = "void"
            row["pnl"] = "0.000"
            row["settled_at_utc"] = now
            row["settlement_note"] = f"void_score:{candidate.get('score','')}"
            settled_now += 1
            continue
        actual, note = market_count(candidate, norm_text(row.get("player")), row.get("market", ""))
        line = parse_float(row.get("line"))
        odds = parse_float(row.get("selected_odds"))
        if actual is None or line is None:
            row["settlement_status"] = "pending"
            row["settlement_note"] = note if actual is None else "missing_line"
            still_pending += 1
            continue
        result = result_for(actual, line, (row.get("side") or "").upper())
        row["settlement_status"] = "settled" if result != "void" else "void"
        row["actual"] = str(actual)
        row["result"] = result
        row["pnl"] = f"{pnl_for(result, odds):.3f}"
        row["settled_at_utc"] = now
        row["settlement_note"] = f"sackmann:{candidate.get('tourney_name','')}:{candidate.get('score','')}"
        settled_now += 1

    write_csv(signals_path, rows)
    write_performance(Path(args.performance), rows)
    print(f"Settled/voided now: {settled_now}; still pending checked: {still_pending}; total rows: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
