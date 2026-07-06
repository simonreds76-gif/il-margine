#!/usr/bin/env python3
"""Compare the tennis props projection board with manual Bet365 aces/DF lines."""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path
import re
import unicodedata

from tennis_props_model import (
    count_line_probabilities,
    poisson_line_probabilities,
    push_adjusted_fair_odds,
    push_adjusted_value_pct,
)


ROOT = Path(__file__).resolve().parent.parent
PROPS_DIR = ROOT / "data" / "tennis-props"
INBOX_DIR = PROPS_DIR / "inbox"
DEFAULT_BOARD = PROPS_DIR / "player-props-board.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def norm_name(value: object) -> str:
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


def is_placeholder_player(value: object) -> bool:
    text = norm_name(value)
    return (not text) or text in {"total", "totals", "player total", "player totals"} or text.startswith("totals")


def parse_float(value: object, default: float | None = None) -> float | None:
    try:
        text = str(value or "").strip()
        if not text:
            return default
        return float(text)
    except (TypeError, ValueError):
        return default


def fmt(value: float | None, digits: int = 4) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def market_mean(board_row: dict[str, str], market: str) -> float | None:
    lower = market.lower().replace(" ", "_")
    if lower in {"aces", "ace", "player_aces"}:
        return parse_float(board_row.get("projected_aces"))
    if lower in {"double_faults", "double_fault", "dfs", "df"}:
        return parse_float(board_row.get("projected_dfs"))
    return None


def market_confidence(board_row: dict[str, str], market: str) -> str:
    lower = market.lower().replace(" ", "_")
    if lower in {"aces", "ace", "player_aces"}:
        return str(board_row.get("ace_confidence") or "")
    if lower in {"double_faults", "double_fault", "dfs", "df"}:
        return str(board_row.get("df_confidence") or "")
    return ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--board", default=str(DEFAULT_BOARD))
    parser.add_argument("--lines", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--min-value", type=float, default=0.08)
    parser.add_argument(
        "--distribution",
        choices=["negative_binomial", "nb", "poisson"],
        default="negative_binomial",
        help="Count distribution used for aces/DF O/U prices. Negative binomial is the default research surface.",
    )
    args = parser.parse_args()

    lines_path = Path(args.lines) if args.lines else INBOX_DIR / f"bet365-lines-{args.date}.csv"
    out_path = Path(args.out) if args.out else PROPS_DIR / f"comparison-{args.date}.csv"
    line_rows = read_csv(lines_path)
    if not lines_path.exists():
        print(f"Lines file not found: {lines_path}")
        return
    if not line_rows:
        print(f"Lines file has no market rows: {lines_path}")
        return
    board_rows = read_csv(Path(args.board))
    board = {
        (
            str(row.get("date") or ""),
            str(row.get("tour") or "").upper(),
            norm_name(row.get("player")),
            norm_name(row.get("opponent")),
        ): row
        for row in board_rows
    }
    board_by_player: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in board_rows:
        player_key = (str(row.get("date") or ""), str(row.get("tour") or "").upper(), norm_name(row.get("player")))
        board_by_player.setdefault(player_key, []).append(row)

    rows: list[dict[str, str]] = []
    for line in line_rows:
        line_date = str(line.get("date") or args.date)
        line_tour = str(line.get("tour") or "").upper()
        line_player = str(line.get("player") or "").strip()
        line_opponent = str(line.get("opponent") or "").strip()
        key = (
            line_date,
            line_tour,
            norm_name(line_player),
            norm_name(line_opponent),
        )
        board_row = board.get(key)
        if board_row is None and is_placeholder_player(line_player) and line_opponent:
            player_only_key = (line_date, line_tour, norm_name(line_opponent))
            candidates = board_by_player.get(player_only_key, [])
            if len(candidates) == 1:
                board_row = candidates[0]
                line_player = str(board_row.get("player") or line_opponent)
                line_opponent = str(board_row.get("opponent") or "")
        if board_row is None:
            # Allow matching when the manual line date is tomorrow but the board was
            # generated today.
            candidates = [
                row
                for k, row in board.items()
                if k[1] == key[1] and k[2] == key[2] and k[3] == key[3]
            ]
            board_row = candidates[0] if len(candidates) == 1 else None
        market = str(line.get("market") or "").strip()
        mean = market_mean(board_row or {}, market) if board_row else None
        line_value = parse_float(line.get("line"))
        over_odds = parse_float(line.get("over_odds"))
        under_odds = parse_float(line.get("under_odds"))
        if mean is not None and line_value is not None:
            if args.distribution == "poisson":
                p_over, p_under, p_push = poisson_line_probabilities(line_value, mean)
            else:
                p_over, p_under, p_push = count_line_probabilities(
                    line_value,
                    mean,
                    distribution=args.distribution,
                    tour=str(line.get("tour") or ""),
                    market=market,
                )
        else:
            p_over, p_under, p_push = None, None, None
        fair_over = (
            push_adjusted_fair_odds(p_over, p_push or 0.0)
            if p_over is not None and p_push is not None
            else None
        )
        fair_under = (
            push_adjusted_fair_odds(p_under, p_push or 0.0)
            if p_under is not None and p_push is not None
            else None
        )
        raw_value_over = (
            push_adjusted_value_pct(p_over, p_push or 0.0, over_odds)
            if p_over is not None and p_push is not None and over_odds is not None
            else None
        )
        raw_value_under = (
            push_adjusted_value_pct(p_under, p_push or 0.0, under_odds)
            if p_under is not None and p_push is not None and under_odds is not None
            else None
        )
        value_over = raw_value_over / 100.0 if raw_value_over is not None else None
        value_under = raw_value_under / 100.0 if raw_value_under is not None else None
        confidence = market_confidence(board_row or {}, market)
        notes = str((board_row or {}).get("notes") or "")
        complete_line = over_odds is not None and under_odds is not None
        deep_alt = False
        if complete_line and over_odds is not None and under_odds is not None:
            deep_alt = max(over_odds, under_odds) > 4.0 or min(over_odds, under_odds) < 1.12
        if mean is not None and line_value is not None:
            deep_alt = deep_alt or abs(line_value - mean) > max(1.2, mean * 0.25)
        line_quality = "one_sided" if not complete_line else "deep_alt" if deep_alt else "complete"
        recommended = ""
        if confidence == "HIGH" and not notes and line_quality == "complete":
            if value_over is not None and value_over >= args.min_value:
                recommended = "OVER"
            if value_under is not None and value_under >= args.min_value and (
                value_over is None or value_under > value_over
            ):
                recommended = "UNDER"

        rows.append(
            {
                **line,
                "player": line_player,
                "opponent": line_opponent,
                "matched_board": "yes" if board_row else "no",
                "projection_mean": fmt(mean, 3),
                "confidence": confidence,
                "line_quality": line_quality,
                "notes": notes,
                "fair_p_over": fmt(p_over),
                "fair_p_under": fmt(p_under),
                "fair_p_push": fmt(p_push),
                "distribution": args.distribution,
                "fair_over_odds": fmt(fair_over, 3),
                "fair_under_odds": fmt(fair_under, 3),
                "value_over_pct": fmt((value_over * 100.0) if value_over is not None else None, 2),
                "value_under_pct": fmt((value_under * 100.0) if value_under is not None else None, 2),
                "recommended_side": recommended,
            }
        )

    fieldnames = [
        "date",
        "tour",
        "tournament",
        "player",
        "opponent",
        "market",
        "line",
        "over_odds",
        "under_odds",
        "matched_board",
        "projection_mean",
        "confidence",
        "line_quality",
        "notes",
        "fair_p_over",
        "fair_p_under",
        "fair_p_push",
        "distribution",
        "fair_over_odds",
        "fair_under_odds",
        "value_over_pct",
        "value_under_pct",
        "recommended_side",
    ]
    write_csv(out_path, rows, fieldnames)
    print(f"Saved {len(rows)} rows: {out_path}")
    if not lines_path.exists():
        print(f"Lines file not found: {lines_path}")


if __name__ == "__main__":
    main()
