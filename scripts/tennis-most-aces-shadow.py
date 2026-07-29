#!/usr/bin/env python3
"""Compare, register, close and settle the BetMGM Most Aces 1X2 shadow lane."""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from tennis_most_aces import devig_three_way, norm_name, pair_key, result_from_counts, value_pct


ROOT = Path(__file__).resolve().parent.parent
PROPS = ROOT / "data" / "tennis-props"
DEFAULT_BOARD = PROPS / "shadow" / "most-aces-1x2-board.csv"
DEFAULT_LEDGER = PROPS / "shadow" / "most-aces-1x2-observations.csv"
DEFAULT_REPORT = PROPS / "shadow" / "most-aces-1x2-performance.txt"
DEFAULT_SACKMANN = ROOT / "data" / "sackmann"
MIN_VALUE_PCT = 8.0
MAX_OVERROUND = 1.20
MAX_MODEL_MARKET_GAP_PP = 20.0
FIELDS = [
    "observation_id", "registered_at_utc", "event_id", "date", "tour", "tournament",
    "round", "surface", "bookmaker", "player1", "player2", "player1_mean",
    "player2_mean", "rho", "p_player1", "p_draw", "p_player2", "fair_player1",
    "fair_draw", "fair_player2", "open_player1_odds", "open_draw_odds",
    "open_player2_odds", "market_p_player1", "market_p_draw", "market_p_player2",
    "overround", "model_market_gap_pp", "value_player1_pct", "value_draw_pct", "value_player2_pct",
    "recommended_side", "selected_odds", "bet_eligible", "eligibility_reason",
    "match_start_utc", "closing_player1_odds", "closing_draw_odds",
    "closing_player2_odds", "closing_ts_utc", "clv_pct", "settlement_status",
    "actual_player1_aces", "actual_player2_aces", "outcome", "result", "pnl",
    "model_brier", "model_logloss", "market_brier", "market_logloss",
    "settled_at_utc", "settlement_note", "model", "notes",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDS})


def number(value: object) -> float | None:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def parse_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def market_key(row: dict[str, str]) -> str:
    event_id = str(row.get("event_id") or "").strip()
    if event_id:
        return f"betmgm|{event_id}|most_aces"
    players = "|".join(pair_key(row.get("player1"), row.get("player2")))
    return f"betmgm|{row.get('date','')}|{players}|most_aces"


def observation_id(row: dict[str, str]) -> str:
    model = str(row.get("model") or "unknown").strip()
    return f"{market_key(row)}|{model}"


def board_index(
    rows: list[dict[str, str]],
) -> dict[tuple[str, tuple[str, str]], list[dict[str, str]]]:
    index: dict[tuple[str, tuple[str, str]], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (row.get("date", ""), pair_key(row.get("player1"), row.get("player2")))
        index[key].append(row)
    return index


def orient_board(board: dict[str, str], capture: dict[str, str]) -> dict[str, str]:
    if norm_name(board.get("player1")) == norm_name(capture.get("player1")):
        return board
    swapped = dict(board)
    swaps = (
        ("player1", "player2"), ("player1_mean", "player2_mean"),
        ("alpha1", "alpha2"), ("p_player1", "p_player2"),
        ("fair_player1", "fair_player2"), ("player1_confidence", "player2_confidence"),
    )
    for left, right in swaps:
        swapped[left], swapped[right] = board.get(right, ""), board.get(left, "")
    return swapped


def registration_row(board: dict[str, str], capture: dict[str, str]) -> dict[str, str] | None:
    if str(board.get("quote_status") or "").upper() != "READY":
        return None
    prices = (
        number(capture.get("player1_odds")),
        number(capture.get("draw_odds")),
        number(capture.get("player2_odds")),
    )
    probabilities = (
        number(board.get("p_player1")),
        number(board.get("p_draw")),
        number(board.get("p_player2")),
    )
    if any(value is None for value in prices + probabilities):
        return None
    p1_price, draw_price, p2_price = prices  # type: ignore[misc]
    p1, draw, p2 = probabilities  # type: ignore[misc]
    market_p1, market_draw, market_p2, overround = devig_three_way(prices)  # type: ignore[arg-type]
    model_market_gap_pp = 100.0 * max(
        abs(p1 - market_p1),
        abs(draw - market_draw),
        abs(p2 - market_p2),
    )
    values = {
        "P1": value_pct(p1, p1_price),
        "DRAW": value_pct(draw, draw_price),
        "P2": value_pct(p2, p2_price),
    }
    recommended = max(values, key=values.get)
    selected_odds = {"P1": p1_price, "DRAW": draw_price, "P2": p2_price}[recommended]
    model = str(board.get("model") or "")
    if model == "most_aces_direct_1x2_v1":
        confidence_ok = (
            board.get("live_parity_status") == "EXACT_REGISTERED_FEATURES"
            and board.get("evidence_tier") in {"RECENT", "CAREER"}
        )
    else:
        confidence_ok = (
            board.get("player1_confidence") in {"MED", "HIGH"}
            and board.get("player2_confidence") in {"MED", "HIGH"}
        )
    reasons = []
    if values[recommended] < MIN_VALUE_PCT:
        reasons.append("VALUE_LT_8")
    if overround > MAX_OVERROUND:
        reasons.append("OVERROUND_GT_20")
    if model_market_gap_pp > MAX_MODEL_MARKET_GAP_PP:
        reasons.append("MODEL_MARKET_GAP_GT_20PP")
    if not confidence_ok:
        reasons.append("LOW_COUNT_CONFIDENCE")
    eligible = not reasons
    row = {
        "registered_at_utc": capture.get("capture_ts", ""),
        "event_id": capture.get("event_id", ""),
        "date": capture.get("date", ""),
        "tour": board.get("tour", ""),
        "tournament": board.get("tournament", ""),
        "round": board.get("round", ""),
        "surface": board.get("surface", ""),
        "bookmaker": capture.get("bookmaker", "BetMGM"),
        "player1": capture.get("player1", ""),
        "player2": capture.get("player2", ""),
        "player1_mean": board.get("player1_mean", ""),
        "player2_mean": board.get("player2_mean", ""),
        "rho": board.get("rho", ""),
        "p_player1": board.get("p_player1", ""),
        "p_draw": board.get("p_draw", ""),
        "p_player2": board.get("p_player2", ""),
        "fair_player1": board.get("fair_player1", ""),
        "fair_draw": board.get("fair_draw", ""),
        "fair_player2": board.get("fair_player2", ""),
        "open_player1_odds": f"{p1_price:.3f}",
        "open_draw_odds": f"{draw_price:.3f}",
        "open_player2_odds": f"{p2_price:.3f}",
        "market_p_player1": f"{market_p1:.6f}",
        "market_p_draw": f"{market_draw:.6f}",
        "market_p_player2": f"{market_p2:.6f}",
        "overround": f"{overround:.6f}",
        "model_market_gap_pp": f"{model_market_gap_pp:.3f}",
        "value_player1_pct": f"{values['P1']:.3f}",
        "value_draw_pct": f"{values['DRAW']:.3f}",
        "value_player2_pct": f"{values['P2']:.3f}",
        "recommended_side": recommended,
        "selected_odds": f"{selected_odds:.3f}",
        "bet_eligible": "yes" if eligible else "no",
        "eligibility_reason": "ELIGIBLE_SHADOW" if eligible else "|".join(reasons),
        "match_start_utc": capture.get("match_start_utc", ""),
        "settlement_status": "pending",
        "model": board.get("model", ""),
        "notes": "MOST_ACES_1X2_RESEARCH_ONLY",
    }
    row["observation_id"] = observation_id(row)
    return row


def register(board_rows: list[dict[str, str]], captures: list[dict[str, str]], ledger: list[dict[str, str]]) -> int:
    index = board_index(board_rows)
    known = {row.get("observation_id", "") for row in ledger}
    added = 0
    for capture in captures:
        boards = index.get(
            (capture.get("date", ""), pair_key(capture.get("player1"), capture.get("player2"))),
            [],
        )
        for board in boards:
            oriented = orient_board(board, capture)
            candidate = registration_row(oriented, capture)
            if not candidate or candidate["observation_id"] in known:
                continue
            known.add(candidate["observation_id"])
            ledger.append(candidate)
            added += 1
    return added


def update_closes(ledger: list[dict[str, str]], history: list[dict[str, str]]) -> int:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in history:
        grouped[market_key(row)].append(row)
    updated = 0
    for row in ledger:
        registration = parse_datetime(row.get("registered_at_utc"))
        start = parse_datetime(row.get("match_start_utc"))
        if not registration or not start:
            continue
        candidates = []
        for capture in grouped.get(market_key(row), []):
            captured = parse_datetime(capture.get("capture_ts"))
            if captured and registration < captured <= start:
                candidates.append((captured, capture))
        if not candidates:
            row["closing_player1_odds"] = ""
            row["closing_draw_odds"] = ""
            row["closing_player2_odds"] = ""
            row["closing_ts_utc"] = ""
            row["clv_pct"] = ""
            continue
        captured, close = max(candidates, key=lambda item: item[0])
        close_prices = (
            number(close.get("player1_odds")),
            number(close.get("draw_odds")),
            number(close.get("player2_odds")),
        )
        if any(price is None or price <= 1.0 for price in close_prices):
            continue
        row["closing_player1_odds"] = f"{close_prices[0]:.3f}"
        row["closing_draw_odds"] = f"{close_prices[1]:.3f}"
        row["closing_player2_odds"] = f"{close_prices[2]:.3f}"
        row["closing_ts_utc"] = captured.isoformat(timespec="seconds")
        close_price = number({
            "P1": row["closing_player1_odds"],
            "DRAW": row["closing_draw_odds"],
            "P2": row["closing_player2_odds"],
        }.get(row.get("recommended_side", ""), ""))
        selected = number(row.get("selected_odds"))
        row["clv_pct"] = f"{(selected / close_price - 1.0) * 100.0:.3f}" if selected and close_price else ""
        updated += 1
    return updated


def sackmann_matches(directory: Path) -> dict[tuple[str, str], list[dict[str, str]]]:
    index: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for path in directory.glob("atp_matches_*.csv"):
        for row in read_csv(path):
            index[pair_key(row.get("winner_name"), row.get("loser_name"))].append(row)
    return index


def sackmann_date(row: dict[str, str]) -> date | None:
    text = str(row.get("tourney_date") or "")
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None


def settle(ledger: list[dict[str, str]], index: dict[tuple[str, str], list[dict[str, str]]]) -> int:
    settled = 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for row in ledger:
        if row.get("settlement_status") not in {"", "pending"}:
            continue
        try:
            target_date = date.fromisoformat(row["date"])
        except (KeyError, ValueError):
            continue
        candidates = []
        for match in index.get(pair_key(row.get("player1"), row.get("player2")), []):
            played = sackmann_date(match)
            if played and abs((played - target_date).days) <= 2:
                candidates.append((abs((played - target_date).days), match))
        if not candidates:
            row["settlement_note"] = "sackmann_match_not_found"
            continue
        match = min(candidates, key=lambda item: item[0])[1]
        score = str(match.get("score") or "").upper()
        if any(token in score for token in ("RET", "W/O", "WO", "DEF", "ABD")):
            row.update({
                "settlement_status": "void", "result": "void", "pnl": "0.000",
                "settled_at_utc": now, "settlement_note": f"void_score:{score}",
            })
            settled += 1
            continue
        winner = norm_name(match.get("winner_name"))
        first = norm_name(row.get("player1"))
        try:
            winner_aces = int(round(float(match["w_ace"])))
            loser_aces = int(round(float(match["l_ace"])))
        except (KeyError, TypeError, ValueError):
            row["settlement_note"] = "missing_ace_stats"
            continue
        actual1, actual2 = (winner_aces, loser_aces) if first == winner else (loser_aces, winner_aces)
        outcome = result_from_counts(actual1, actual2)
        probabilities = [
            float(row["p_player1"]), float(row["p_draw"]), float(row["p_player2"])
        ]
        market_probabilities = [
            float(row["market_p_player1"]), float(row["market_p_draw"]), float(row["market_p_player2"])
        ]
        outcome_index = {"P1": 0, "DRAW": 1, "P2": 2}[outcome]
        model_brier = sum((p - (1.0 if idx == outcome_index else 0.0)) ** 2 for idx, p in enumerate(probabilities))
        market_brier = sum((p - (1.0 if idx == outcome_index else 0.0)) ** 2 for idx, p in enumerate(market_probabilities))
        recommended = row.get("recommended_side", "")
        result = "win" if recommended == outcome else "loss"
        odds = number(row.get("selected_odds")) or 0.0
        pnl = odds - 1.0 if result == "win" else -1.0
        row.update({
            "settlement_status": "settled",
            "actual_player1_aces": str(actual1),
            "actual_player2_aces": str(actual2),
            "outcome": outcome,
            "result": result,
            "pnl": f"{pnl:.3f}",
            "model_brier": f"{model_brier:.6f}",
            "model_logloss": f"{-math.log(max(probabilities[outcome_index], 1e-12)):.6f}",
            "market_brier": f"{market_brier:.6f}",
            "market_logloss": f"{-math.log(max(market_probabilities[outcome_index], 1e-12)):.6f}",
            "settled_at_utc": now,
            "settlement_note": f"sackmann:{match.get('tourney_name','')}:{score}",
        })
        settled += 1
    return settled


def mean(rows: list[dict[str, str]], field: str) -> float | None:
    values = [number(row.get(field)) for row in rows]
    clean = [value for value in values if value is not None]
    return sum(clean) / len(clean) if clean else None


def write_report(path: Path, rows: list[dict[str, str]]) -> None:
    settled = [row for row in rows if row.get("settlement_status") == "settled"]
    eligible = [row for row in settled if row.get("bet_eligible") == "yes"]
    pnl = sum(number(row.get("pnl")) or 0.0 for row in eligible)
    clv = [row for row in rows if number(row.get("clv_pct")) is not None]
    model_brier = mean(settled, "model_brier")
    market_brier = mean(settled, "market_brier")
    lines = [
        "BetMGM Most Aces 1X2 shadow evidence",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "Status: research-only; ATP Hard/Clay; no live staking.",
        f"Rows: {len(rows)} | settled: {len(settled)} | pending: {sum(row.get('settlement_status') == 'pending' for row in rows)}",
        f"Eligible shadow bets settled: {len(eligible)} | P/L {pnl:+.2f}u | ROI {(100.0 * pnl / len(eligible)) if eligible else 0.0:+.1f}%",
        f"Model Brier: {model_brier:.6f}" if model_brier is not None else "Model Brier: pending",
        f"De-vigged BetMGM Brier: {market_brier:.6f}" if market_brier is not None else "De-vigged BetMGM Brier: pending",
        f"CLV: coverage {len(clv)}/{len(rows)} | mean {(mean(clv, 'clv_pct') or 0.0):+.2f}%",
        "Gate: no profitability claim before real-price settlement and positive CLV evidence.",
    ]
    for model in sorted({row.get("model", "") for row in rows if row.get("model")}):
        model_rows = [row for row in rows if row.get("model") == model]
        model_settled = [
            row for row in model_rows if row.get("settlement_status") == "settled"
        ]
        model_eligible = [
            row for row in model_settled if row.get("bet_eligible") == "yes"
        ]
        model_pnl = sum(number(row.get("pnl")) or 0.0 for row in model_eligible)
        model_clv = [
            row for row in model_rows if number(row.get("clv_pct")) is not None
        ]
        lines.extend(
            [
                "",
                f"Model: {model}",
                (
                    f"Rows: {len(model_rows)} | settled: {len(model_settled)} | "
                    f"eligible settled: {len(model_eligible)}"
                ),
                (
                    f"P/L {model_pnl:+.2f}u | "
                    f"ROI {(100.0 * model_pnl / len(model_eligible)) if model_eligible else 0.0:+.1f}% | "
                    f"CLV {(mean(model_clv, 'clv_pct') or 0.0):+.2f}% n={len(model_clv)}"
                ),
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", default=str(DEFAULT_BOARD))
    parser.add_argument(
        "--additional-board",
        action="append",
        default=[],
        help="Register another model board against the same captured prices.",
    )
    parser.add_argument("--capture", default="")
    parser.add_argument("--history-glob", default=str(PROPS / "inbox" / "betmgm-most-aces-history-*.csv"))
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--sackmann-dir", default=str(DEFAULT_SACKMANN))
    args = parser.parse_args()
    ledger = read_csv(Path(args.ledger))
    captures = read_csv(Path(args.capture)) if args.capture else []
    board_rows = read_csv(Path(args.board))
    for additional in args.additional_board:
        board_rows.extend(read_csv(Path(additional)))
    added = register(board_rows, captures, ledger)
    pattern = Path(args.history_glob)
    history = []
    for path in sorted(pattern.parent.glob(pattern.name)):
        history.extend(read_csv(path))
    closes = update_closes(ledger, history)
    settled = settle(ledger, sackmann_matches(Path(args.sackmann_dir)))
    write_csv(Path(args.ledger), ledger)
    write_report(Path(args.report), ledger)
    print(f"Most Aces shadow: added={added}, closes={closes}, settled={settled}, rows={len(ledger)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
