#!/usr/bin/env python3
"""Compare the tennis props projection board with manual Bet365 aces/DF lines."""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime
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
UNMATCHED_FIELDS = [
    "date",
    "tour",
    "tournament",
    "player",
    "opponent",
    "market",
    "line",
    "over_odds",
    "under_odds",
    "reason",
    "candidate_count",
    "candidate_players",
    "lines_file",
    "board_file",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
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


def compatible_player_name(left: object, right: object) -> bool:
    left_norm = norm_name(left)
    right_norm = norm_name(right)
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm:
        return True
    left_parts = left_norm.split()
    right_parts = right_norm.split()
    left_last = left_parts[-1] if left_parts else ""
    right_last = right_parts[-1] if right_parts else ""
    return bool(left_last and left_last == right_last and len(left_last) >= 4)


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


def no_vig_probabilities(over_odds: float | None, under_odds: float | None) -> tuple[float | None, float | None]:
    if over_odds is None or under_odds is None or over_odds <= 1.0 or under_odds <= 1.0:
        return None, None
    over_imp = 1.0 / over_odds
    under_imp = 1.0 / under_odds
    total = over_imp + under_imp
    if total <= 0:
        return None, None
    return over_imp / total, under_imp / total


def push_excluded_probabilities(
    p_over: float | None,
    p_under: float | None,
    p_push: float | None,
) -> tuple[float | None, float | None]:
    if p_over is None or p_under is None:
        return None, None
    denominator = 1.0 - (p_push or 0.0)
    if denominator <= 0:
        return None, None
    return p_over / denominator, p_under / denominator


def market_mean(board_row: dict[str, str], market: str) -> float | None:
    lower = market.lower().replace(" ", "_")
    if lower in {"aces", "ace", "player_aces", "match_aces"}:
        return parse_float(board_row.get("projected_aces"))
    if lower in {"double_faults", "double_fault", "dfs", "df", "match_double_faults"}:
        return parse_float(board_row.get("projected_dfs"))
    return None


def market_confidence(board_row: dict[str, str], market: str) -> str:
    lower = market.lower().replace(" ", "_")
    if lower in {"aces", "ace", "player_aces", "match_aces"}:
        return str(board_row.get("ace_confidence") or "")
    if lower in {"double_faults", "double_fault", "dfs", "df", "match_double_faults"}:
        return str(board_row.get("df_confidence") or "")
    return ""


def is_match_total_count_market(market: str) -> bool:
    return market.lower().replace(" ", "_") in {"match_aces", "match_double_faults"}


def combine_confidence(left: str, right: str) -> str:
    order = {"LOW": 0, "MED": 1, "HIGH": 2}
    left_key = left.upper()
    right_key = right.upper()
    if left_key not in order or right_key not in order:
        return left or right
    return left_key if order[left_key] <= order[right_key] else right_key


def candidate_summary(rows: list[dict[str, str]], limit: int = 6) -> str:
    bits = []
    for row in rows[:limit]:
        bits.append(
            " | ".join(
                part
                for part in (
                    str(row.get("date") or ""),
                    str(row.get("tour") or ""),
                    str(row.get("tournament") or ""),
                    f"{row.get('player') or ''} vs {row.get('opponent') or ''}",
                )
                if part
            )
        )
    if len(rows) > limit:
        bits.append(f"+{len(rows) - limit} more")
    return " ; ".join(bits)


def unique_row(rows: list[dict[str, str]]) -> dict[str, str] | None:
    return rows[0] if len(rows) == 1 else None


def date_drift_days(left: str, right: str) -> int | None:
    try:
        a = datetime.strptime(left, "%Y-%m-%d").date()
        b = datetime.strptime(right, "%Y-%m-%d").date()
    except ValueError:
        return None
    return abs((a - b).days)


def within_date_drift(line_date: str, row: dict[str, str], max_days: int) -> bool:
    drift = date_drift_days(line_date, str(row.get("date") or ""))
    return drift is not None and drift <= max_days


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--board", default=str(DEFAULT_BOARD))
    parser.add_argument("--lines", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--unmatched-out", default="")
    parser.add_argument("--min-value", type=float, default=0.10)
    parser.add_argument("--min-novig-edge", type=float, default=0.05)
    parser.add_argument("--max-model-market-gap", type=float, default=0.12)
    parser.add_argument(
        "--max-date-drift-days",
        type=int,
        default=1,
        help="Maximum date mismatch allowed for fallback name matching.",
    )
    parser.add_argument(
        "--distribution",
        choices=["negative_binomial", "nb", "poisson"],
        default="negative_binomial",
        help="Count distribution used for aces/DF O/U prices. Negative binomial is the default research surface.",
    )
    args = parser.parse_args()

    lines_path = Path(args.lines) if args.lines else INBOX_DIR / f"bet365-lines-{args.date}.csv"
    out_path = Path(args.out) if args.out else PROPS_DIR / f"comparison-{args.date}.csv"
    unmatched_out_path = (
        Path(args.unmatched_out)
        if args.unmatched_out
        else PROPS_DIR / f"comparison-{args.date}-unmatched.csv"
    )
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
    board_by_player_any_date: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in board_rows:
        player_key = (str(row.get("date") or ""), str(row.get("tour") or "").upper(), norm_name(row.get("player")))
        board_by_player.setdefault(player_key, []).append(row)
        any_date_key = (str(row.get("tour") or "").upper(), norm_name(row.get("player")))
        board_by_player_any_date.setdefault(any_date_key, []).append(row)

    rows: list[dict[str, str]] = []
    unmatched_rows: list[dict[str, str]] = []
    for line in line_rows:
        line_date = str(line.get("date") or args.date)
        line_tour = str(line.get("tour") or "").upper()
        line_player = str(line.get("player") or "").strip()
        line_opponent = str(line.get("opponent") or "").strip()
        line_market = str(line.get("market") or "").strip()
        requires_exact_pair = is_match_total_count_market(line_market)
        original_player = line_player
        original_opponent = line_opponent
        match_source = ""
        unmatched_reason = ""
        candidate_rows: list[dict[str, str]] = []
        key = (
            line_date,
            line_tour,
            norm_name(line_player),
            norm_name(line_opponent),
        )
        board_row = board.get(key)
        if board_row is not None:
            match_source = "exact"
        if board_row is None and not requires_exact_pair and is_placeholder_player(line_player) and line_opponent:
            player_only_key = (line_date, line_tour, norm_name(line_opponent))
            candidates = board_by_player.get(player_only_key, [])
            candidate_rows = candidates
            if len(candidates) == 1:
                board_row = candidates[0]
                line_player = str(board_row.get("player") or line_opponent)
                line_opponent = str(board_row.get("opponent") or "")
                match_source = "placeholder_player_same_date"
            elif len(candidates) > 1:
                unmatched_reason = "AMBIGUOUS_PLACEHOLDER_PLAYER_SAME_DATE"
            else:
                unmatched_reason = "PLACEHOLDER_PLAYER_NOT_ON_BOARD_DATE"
        if board_row is None and line_player and not is_placeholder_player(line_player) and (
            not requires_exact_pair and (not line_opponent or is_placeholder_player(line_opponent))
        ):
            player_only_key = (line_date, line_tour, norm_name(line_player))
            candidates = board_by_player.get(player_only_key, [])
            candidate_rows = candidates
            if len(candidates) == 1:
                board_row = candidates[0]
                line_player = str(board_row.get("player") or line_player)
                line_opponent = str(board_row.get("opponent") or "")
                match_source = "player_only_same_date"
            elif len(candidates) > 1:
                unmatched_reason = "AMBIGUOUS_PLAYER_SAME_DATE"
            else:
                unmatched_reason = "PLAYER_NOT_ON_BOARD_DATE"
        if board_row is None:
            # Allow matching when the manual line date is tomorrow but the board was
            # generated today.
            candidates = [
                row
                for k, row in board.items()
                if k[1] == key[1]
                and k[2] == key[2]
                and k[3] == key[3]
                and within_date_drift(line_date, row, args.max_date_drift_days)
            ]
            candidate_rows = candidates
            if len(candidates) == 1:
                board_row = candidates[0]
                match_source = "exact_any_date"
            elif len(candidates) > 1:
                unmatched_reason = "AMBIGUOUS_EXACT_ANY_DATE"
        if board_row is None and requires_exact_pair and line_player and line_opponent:
            candidates = [
                row
                for row in board_by_player_any_date.get((line_tour, norm_name(line_player)), [])
                if within_date_drift(line_date, row, args.max_date_drift_days)
                and compatible_player_name(line_opponent, row.get("opponent"))
            ]
            candidate_rows = candidates
            if len(candidates) == 1:
                board_row = candidates[0]
                line_player = str(board_row.get("player") or line_player)
                line_opponent = str(board_row.get("opponent") or line_opponent)
                match_source = "pair_alias_any_date"
            elif len(candidates) > 1:
                unmatched_reason = "AMBIGUOUS_PAIR_ALIAS_ANY_DATE"
            else:
                unmatched_reason = unmatched_reason or "PAIR_NOT_ON_BOARD"
        if board_row is None and not requires_exact_pair:
            lookup_player = ""
            if is_placeholder_player(original_player) and original_opponent:
                lookup_player = original_opponent
            elif line_player and not is_placeholder_player(line_player):
                lookup_player = line_player
            if lookup_player:
                candidates = [
                    row
                    for row in board_by_player_any_date.get((line_tour, norm_name(lookup_player)), [])
                    if within_date_drift(line_date, row, args.max_date_drift_days)
                ]
                candidate_rows = candidates
                if len(candidates) == 1:
                    board_row = candidates[0]
                    line_player = str(board_row.get("player") or lookup_player)
                    line_opponent = str(board_row.get("opponent") or "")
                    match_source = "player_only_any_date"
                elif len(candidates) > 1:
                    unmatched_reason = unmatched_reason or "AMBIGUOUS_PLAYER_ANY_DATE"
                else:
                    unmatched_reason = unmatched_reason or "PLAYER_NOT_ON_BOARD"
            else:
                unmatched_reason = unmatched_reason or "NO_PLAYER_NAME"
        if board_row is None:
            unmatched_rows.append(
                {
                    **line,
                    "reason": unmatched_reason or "NO_BOARD_MATCH",
                    "candidate_count": str(len(candidate_rows)),
                    "candidate_players": candidate_summary(candidate_rows),
                    "lines_file": str(lines_path),
                    "board_file": str(Path(args.board)),
                }
            )
        market = line_market
        counterpart_row: dict[str, str] | None = None
        if board_row and is_match_total_count_market(market):
            counterpart_row = board.get(
                (
                    str(board_row.get("date") or ""),
                    str(board_row.get("tour") or "").upper(),
                    norm_name(board_row.get("opponent")),
                    norm_name(board_row.get("player")),
                )
            )
        if board_row and counterpart_row:
            left_mean = market_mean(board_row, market)
            right_mean = market_mean(counterpart_row, market)
            mean = (
                left_mean + right_mean
                if left_mean is not None and right_mean is not None
                else None
            )
        else:
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
        novig_over, novig_under = no_vig_probabilities(over_odds, under_odds)
        model_over, model_under = push_excluded_probabilities(p_over, p_under, p_push)
        edge_over_novig = (
            model_over - novig_over
            if model_over is not None and novig_over is not None
            else None
        )
        edge_under_novig = (
            model_under - novig_under
            if model_under is not None and novig_under is not None
            else None
        )
        model_market_gap = max(
            [abs(value) for value in (edge_over_novig, edge_under_novig) if value is not None],
            default=None,
        )
        confidence = market_confidence(board_row or {}, market)
        notes = str((board_row or {}).get("notes") or "")
        if counterpart_row:
            confidence = combine_confidence(confidence, market_confidence(counterpart_row, market))
            other_notes = str(counterpart_row.get("notes") or "")
            notes = " | ".join(part for part in (notes, other_notes) if part)
        elif board_row and is_match_total_count_market(market):
            notes = " | ".join(part for part in (notes, "MATCH_TOTAL_COUNTERPART_MISSING") if part)
        complete_line = over_odds is not None and under_odds is not None
        deep_alt = False
        if complete_line and over_odds is not None and under_odds is not None:
            deep_alt = max(over_odds, under_odds) > 4.0 or min(over_odds, under_odds) < 1.12
        if mean is not None and line_value is not None:
            deep_alt = deep_alt or abs(line_value - mean) > max(1.2, mean * 0.25)
        line_quality = "one_sided" if not complete_line else "deep_alt" if deep_alt else "complete"
        recommended = ""
        blocked_reason = ""
        if confidence == "HIGH" and not notes and line_quality == "complete":
            candidates: list[tuple[str, float]] = []
            if novig_over is None or novig_under is None:
                blocked_reason = "NO_NOVIG_PAIR"
            else:
                if value_over is not None and value_over >= args.min_value:
                    if edge_over_novig is None or edge_over_novig < args.min_novig_edge:
                        blocked_reason = blocked_reason or "NOVIG_EDGE_BELOW_GATE"
                    elif edge_over_novig > args.max_model_market_gap:
                        blocked_reason = blocked_reason or "MODEL_MARKET_GAP"
                    else:
                        candidates.append(("OVER", value_over))
                if value_under is not None and value_under >= args.min_value:
                    if edge_under_novig is None or edge_under_novig < args.min_novig_edge:
                        blocked_reason = blocked_reason or "NOVIG_EDGE_BELOW_GATE"
                    elif edge_under_novig > args.max_model_market_gap:
                        blocked_reason = blocked_reason or "MODEL_MARKET_GAP"
                    else:
                        candidates.append(("UNDER", value_under))
                if candidates:
                    recommended = max(candidates, key=lambda item: item[1])[0]
                    blocked_reason = ""
                elif not blocked_reason:
                    blocked_reason = "RAW_EDGE_BELOW_GATE"
        elif confidence != "HIGH":
            blocked_reason = "CONF_NOT_HIGH"
        elif notes:
            blocked_reason = "BOARD_WARNINGS"
        elif line_quality != "complete":
            blocked_reason = f"LINE_{line_quality.upper()}"

        rows.append(
            {
                **line,
                "date": str((board_row or {}).get("date") or line_date),
                "tour": str((board_row or {}).get("tour") or line_tour),
                "tournament": str((board_row or {}).get("tournament") or line.get("tournament") or ""),
                "player": line_player,
                "opponent": line_opponent,
                "matched_board": "yes" if board_row else "no",
                "match_source": match_source,
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
                "novig_p_over": fmt(novig_over),
                "novig_p_under": fmt(novig_under),
                "edge_over_novig_pp": fmt((edge_over_novig * 100.0) if edge_over_novig is not None else None, 2),
                "edge_under_novig_pp": fmt((edge_under_novig * 100.0) if edge_under_novig is not None else None, 2),
                "model_market_gap_pp": fmt((model_market_gap * 100.0) if model_market_gap is not None else None, 2),
                "blocked_reason": blocked_reason,
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
        "match_source",
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
        "novig_p_over",
        "novig_p_under",
        "edge_over_novig_pp",
        "edge_under_novig_pp",
        "model_market_gap_pp",
        "blocked_reason",
        "recommended_side",
    ]
    write_csv(out_path, rows, fieldnames)
    print(f"Saved {len(rows)} rows: {out_path}")
    write_csv(unmatched_out_path, unmatched_rows, UNMATCHED_FIELDS)
    print(f"Saved {len(unmatched_rows)} unmatched rows: {unmatched_out_path}")
    if not lines_path.exists():
        print(f"Lines file not found: {lines_path}")


if __name__ == "__main__":
    main()
