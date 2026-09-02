#!/usr/bin/env python3
"""Compare the tennis props projection board with manual Bet365 aces/DF lines."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timezone
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
DEFAULT_TOTALS_GATE = PROPS_DIR / "backtest" / "aces-dfs-totals-gate.json"
DEFAULT_BREAK_GATE = PROPS_DIR / "backtest" / "breaks-stage0-gate.json"
BREAK_MARKETS = {"player_breaks", "match_breaks"}
MATCH_TOTAL_MARKETS = {"match_aces", "match_double_faults", "match_breaks"}
CONFIDENCE_RANK = {"LOW": 0, "MED": 1, "HIGH": 2}
MIN_COMBINED_SAMPLE = 800.0
STALE_CAPTURE_HOURS = 6.0
ONE_SIDED_SHADOW_CAPTURE_HOURS = 18.0
BREAK_PROSPECTIVE_CAPTURE_HOURS = 1.5
ONE_SIDED_MIN_ODDS = 1.50
ONE_SIDED_MAX_ODDS = 3.50
ONE_SIDED_MIN_VALUE = 0.08
BREAK_MIN_VALUE_PCT = 3.0
BREAK_MAX_VALUE_PCT = 12.0
BREAK_MAX_MODEL_MARKET_GAP_PP = 12.0
BREAK_SOURCE_AGREEMENT_MAX_PP = 5.0
BREAK_PLAYER_LINE_RANGE = (1.5, 5.5)
BREAK_MATCH_LINE_RANGE = (3.5, 9.5)
BREAK_GATE_VERSION = "breaks_v1_p1"
BREAK_STRICT_MODE = "breaks_prospective_shadow"
BREAK_SINGLE_SOURCE_MODE = "breaks_single_source_shadow"
TWO_WAY_SHADOW_NOTE_BLOCKERS = (
    "NO_PLAYER_DATA",
    "NO_OPP_DATA",
    "PLAYER_NAME_UNRESOLVED",
    "OPPONENT_NAME_UNRESOLVED",
)
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


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def filter_line_rows_for_as_of(
    rows: list[dict[str, str]], as_of: str
) -> tuple[list[dict[str, str]], int]:
    """Exclude completed event dates when a prior capture is reused."""
    target = date.fromisoformat(as_of)
    kept: list[dict[str, str]] = []
    excluded = 0
    for row in rows:
        raw_date = str(row.get("date") or "").strip()
        if not raw_date:
            kept.append(row)
            continue
        try:
            event_date = date.fromisoformat(raw_date)
        except ValueError:
            kept.append(row)
            continue
        if event_date < target:
            excluded += 1
            continue
        kept.append(row)
    return kept, excluded


def filter_line_rows_by_market(
    rows: list[dict[str, str]], market_filter: str
) -> list[dict[str, str]]:
    allowed = {
        item.strip().lower()
        for item in str(market_filter or "").split(",")
        if item.strip()
    }
    if not allowed:
        return rows
    return [row for row in rows if str(row.get("market") or "").strip().lower() in allowed]


def totals_gate_result(gate: dict[str, object], tour: str, market: str) -> tuple[bool, float | None]:
    markets = gate.get("markets")
    if not isinstance(markets, dict):
        return False, None
    market_row = markets.get(market)
    if not isinstance(market_row, dict) or market_row.get("passed") is not True:
        return False, None
    tours = market_row.get("tours")
    tour_row = tours.get(str(tour or "").upper()) if isinstance(tours, dict) else None
    if not isinstance(tour_row, dict) or tour_row.get("passed") is not True:
        return False, None
    alpha = parse_float(tour_row.get("model_alpha"))
    return alpha is not None and alpha > 0, alpha


def break_gate_result(
    gate: dict[str, object], tour: str, market: str
) -> tuple[bool, str, float | None]:
    scope = "match_breaks" if market == "match_breaks" else "player_breaks"
    scopes = gate.get("scopes")
    scope_row = scopes.get(scope) if isinstance(scopes, dict) else None
    tours = scope_row.get("tours") if isinstance(scope_row, dict) else None
    row = tours.get(str(tour or "").upper()) if isinstance(tours, dict) else None
    if not isinstance(scope_row, dict) or not isinstance(row, dict):
        return False, "poisson", None
    alpha = parse_float(row.get("model_alpha"))
    distribution = str(row.get("distribution") or "poisson")
    passed = scope_row.get("passed") is True and row.get("passed") is True
    return passed, distribution, alpha


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


def can_fallback_player_only(player: object, opponent: object) -> bool:
    """Only allow player-only matching when one side is genuinely missing.

    If both names are present, ignoring the opponent can attach yesterday's
    price to the same player's next-round match.
    """
    if is_placeholder_player(player):
        return not is_placeholder_player(opponent)
    return not is_placeholder_player(player) and is_placeholder_player(opponent)


def normalize_legacy_team_total_row(row: dict[str, str]) -> dict[str, str]:
    """Repair team-total rows written by the pre-2026-07-21 scraper.

    The old parser treated Bet365's player/team totals as match totals and
    assigned Away ladders to the home player. Keep this compatibility layer in
    the comparator so already-captured files remain usable without another API
    request.
    """
    normalized = dict(row)
    raw_market = norm_name(row.get("raw_market_name"))
    market = str(row.get("market") or "").strip().lower()
    if "team total" not in raw_market or market not in MATCH_TOTAL_MARKETS:
        return normalized

    normalized["market"] = "double_faults" if "double faults" in raw_market else "aces"
    if raw_market.endswith(" away"):
        normalized["player"] = str(row.get("opponent") or "")
        normalized["opponent"] = str(row.get("player") or "")
    return normalized


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


def no_vig_edge_ratio(model_prob: float | None, market_prob: float | None) -> float | None:
    if model_prob is None or market_prob is None or market_prob <= 0:
        return None
    return (model_prob / market_prob) - 1.0


def confidence_rank(value: object) -> int:
    return CONFIDENCE_RANK.get(str(value or "").upper(), 0)


def confidence_floor(*values: object) -> str:
    ranks = [confidence_rank(value) for value in values if str(value or "").strip()]
    rank = min(ranks) if ranks else 0
    for label, label_rank in CONFIDENCE_RANK.items():
        if label_rank == rank:
            return label
    return "LOW"


def board_sample(row: dict[str, str] | None) -> float:
    if not row:
        return 0.0
    return parse_float(row.get("player_surface_svpt_sample"), 0.0) or 0.0


def combined_board_sample(*rows: dict[str, str] | None) -> float:
    return sum(board_sample(row) for row in rows if row)


def parse_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def hours_since(value: object, now: datetime) -> float | None:
    parsed = parse_timestamp(value)
    if not parsed:
        return None
    return (now - parsed).total_seconds() / 3600.0


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def line_group_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    players = " v ".join(sorted([norm_name(row.get("player")), norm_name(row.get("opponent"))]))
    market = str(row.get("market") or "")
    identity = (
        players
        if is_match_total_count_market(market)
        else f"{norm_name(row.get('player'))} @ {players}"
    )
    return (
        str(row.get("date") or ""),
        str(row.get("tour") or "").upper(),
        str(row.get("tournament") or ""),
        identity,
        market,
    )


def price_pair_status(over_odds: float | None, under_odds: float | None) -> str:
    if over_odds is not None and under_odds is not None:
        return "two_way"
    if over_odds is not None:
        return "over_only"
    if under_odds is not None:
        return "under_only"
    return "missing_prices"


def line_quality_from_shape(
    over_odds: float | None,
    under_odds: float | None,
    line_value: float | None,
    mean: float | None,
) -> tuple[str, str]:
    if over_odds is None and under_odds is None:
        return "one_sided", "MISSING_BOTH_PRICES"
    if over_odds is None:
        return "one_sided", "UNDER_ONLY_PRICE"
    if under_odds is None:
        return "one_sided", "OVER_ONLY_PRICE"

    reasons: list[str] = []
    if max(over_odds, under_odds) > 4.0 or min(over_odds, under_odds) < 1.12:
        reasons.append("EXTREME_PRICE")
    if mean is not None and line_value is not None:
        distance = abs(line_value - mean)
        threshold = max(1.2, mean * 0.25)
        if distance > threshold:
            reasons.append("FAR_FROM_PROJECTION")
    if reasons:
        return "deep_alt", "|".join(reasons)
    return "complete", "TWO_WAY_MAIN_CANDIDATE"


def select_main_lines(rows: list[dict[str, str]]) -> None:
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        row["main_line"] = "false"
        row["best_available_line"] = "false"
        row["line_rank"] = ""
        row["group_line_count"] = "0"
        row["complete_line_count"] = "0"
        grouped.setdefault(line_group_key(row), []).append(row)
    for group_rows in grouped.values():
        two_way_candidates = [
            row for row in group_rows
            if row.get("matched_board") == "yes" and row.get("price_pair_status") == "two_way"
        ]
        group_size = len(group_rows)
        complete_count = len(two_way_candidates)
        for row in group_rows:
            row["group_line_count"] = str(group_size)
            row["complete_line_count"] = str(complete_count)
        if not two_way_candidates:
            # Odds-API currently exposes Bet365 player-count ladders as
            # over-only prices. Select exactly one representative row for
            # prospective shadow evaluation without pretending it is a
            # complete two-way main line.
            over_only_candidates = [
                row
                for row in group_rows
                if row.get("matched_board") == "yes"
                and row.get("price_pair_status") == "over_only"
                and ONE_SIDED_MIN_ODDS
                <= (parse_float(row.get("over_odds"), 0.0) or 0.0)
                <= ONE_SIDED_MAX_ODDS
            ]

            def over_only_score(row: dict[str, str]) -> tuple[float, float]:
                odds = parse_float(row.get("over_odds"), 0.0) or 0.0
                mean = parse_float(row.get("projection_mean"), 0.0) or 0.0
                line_value = parse_float(row.get("line"), mean) or mean
                return (abs(odds - 2.0), abs(line_value - mean))

            ranked_over_only = sorted(over_only_candidates, key=over_only_score)
            for index, row in enumerate(ranked_over_only, start=1):
                row["line_rank"] = str(index)
            if ranked_over_only:
                ranked_over_only[0]["best_available_line"] = "true"
            continue

        def score(row: dict[str, str]) -> tuple[float, float, float]:
            novig = parse_float(row.get("novig_p_over"), 0.5) or 0.5
            mean = parse_float(row.get("projection_mean"), 0.0) or 0.0
            line_value = parse_float(row.get("line"), mean) or mean
            price_imbalance = abs(novig - 0.5)
            projection_distance = abs(line_value - mean)
            price_min = min(parse_float(row.get("over_odds"), 999.0) or 999.0, parse_float(row.get("under_odds"), 999.0) or 999.0)
            return (price_imbalance, projection_distance, -price_min)

        ranked = sorted(two_way_candidates, key=score)
        for index, row in enumerate(ranked, start=1):
            row["line_rank"] = str(index)
        ranked[0]["best_available_line"] = "true"

        candidates = [
            row for row in ranked
            if row.get("line_quality") == "complete"
        ]
        if not candidates:
            continue
        min(candidates, key=score)["main_line"] = "true"


def best_candidate(row: dict[str, str], args: argparse.Namespace) -> tuple[str, float] | None:
    candidates: list[tuple[str, float, float]] = []
    for side, raw_field, ratio_field in (
        ("OVER", "value_over_pct", "edge_over_novig_pct"),
        ("UNDER", "value_under_pct", "edge_under_novig_pct"),
    ):
        raw = (parse_float(row.get(raw_field), 0.0) or 0.0) / 100.0
        ratio = (parse_float(row.get(ratio_field), 0.0) or 0.0) / 100.0
        if raw >= args.min_value and ratio >= args.min_novig_edge:
            candidates.append((side, raw, ratio))
    if not candidates:
        return None
    side, raw, _ratio = max(candidates, key=lambda item: (item[1], item[2]))
    return side, raw


def apply_decision_gates(rows: list[dict[str, str]], args: argparse.Namespace, now: datetime) -> None:
    select_main_lines(rows)
    for row in rows:
        reasons: list[str] = []
        market = str(row.get("market") or "")
        scope = str(row.get("scope") or "")
        if scope != "match_total" or market not in MATCH_TOTAL_MARKETS:
            reasons.append("PLAYER_LINE_RESEARCH_ONLY")
        if scope == "match_total" and row.get("totals_stage0_passed") != "true":
            reasons.append("TOTALS_STAGE0_BLOCKED")
        if row.get("matched_board") != "yes":
            reasons.append("NO_BOARD_MATCH")
        if row.get("line_quality") != "complete":
            reasons.append(f"LINE_{str(row.get('line_quality') or 'UNKNOWN').upper()}")
        if row.get("main_line") != "true":
            reasons.append("NOT_MAIN_LINE")
        if not row.get("capture_ts"):
            reasons.append("MISSING_CAPTURE_TS")
        else:
            age = hours_since(row.get("capture_ts"), now)
            if age is not None and age > STALE_CAPTURE_HOURS:
                reasons.append("STALE_CAPTURE")
        start = parse_timestamp(row.get("match_start_utc"))
        if not row.get("match_start_utc"):
            reasons.append("MISSING_MATCH_START")
        elif start is not None and start <= now:
            reasons.append("MATCH_STARTED")
        if scope == "match_total" and (not row.get("projection_p1") or not row.get("projection_p2")):
            reasons.append("PROJECTION_COMPONENT_MISSING")
        if confidence_rank(row.get("confidence")) < confidence_rank("MED"):
            reasons.append("CONF_BELOW_MED")
        sample = parse_float(row.get("combined_surface_svpt_sample"), 0.0) or 0.0
        if sample < MIN_COMBINED_SAMPLE:
            reasons.append("SAMPLE_BELOW_800")
        gap = parse_float(row.get("model_market_gap_pp"), 0.0) or 0.0
        if gap > args.max_model_market_gap * 100.0:
            reasons.append("MODEL_MARKET_GAP")
        if row.get("notes"):
            reasons.append("BOARD_WARNINGS")
        candidate = best_candidate(row, args)
        if candidate is None:
            reasons.append("EDGE_BELOW_GATE")
        row["block_reasons"] = "|".join(dict.fromkeys(reasons))
        row["bettable"] = bool_text(not reasons and candidate is not None)
        row["recommended_side"] = candidate[0] if not reasons and candidate is not None else ""
        row["blocked_reason"] = "" if row["bettable"] == "true" else (row["block_reasons"].split("|")[0] if row["block_reasons"] else "GATE_BLOCKED")

        shadow_reasons: list[str] = []
        two_way_shadow = row.get("price_pair_status") == "two_way"
        shadow_candidate = best_candidate(row, args) if two_way_shadow else None
        if scope != "player" or market in MATCH_TOTAL_MARKETS:
            shadow_reasons.append("NOT_PLAYER_PROP")
        if row.get("matched_board") != "yes":
            shadow_reasons.append("NO_BOARD_MATCH")
        if two_way_shadow:
            if row.get("line_quality") != "complete":
                shadow_reasons.append("LINE_NOT_COMPLETE")
            if row.get("main_line") != "true":
                shadow_reasons.append("NOT_MAIN_LINE")
        else:
            if row.get("price_pair_status") != "over_only":
                shadow_reasons.append("NOT_OVER_ONLY")
            if row.get("best_available_line") != "true":
                shadow_reasons.append("NOT_BEST_AVAILABLE_LINE")
        if not row.get("capture_ts"):
            shadow_reasons.append("MISSING_CAPTURE_TS")
        else:
            shadow_age = hours_since(row.get("capture_ts"), now)
            if shadow_age is not None and shadow_age > ONE_SIDED_SHADOW_CAPTURE_HOURS:
                shadow_reasons.append("STALE_CAPTURE")
        if not row.get("match_start_utc"):
            shadow_reasons.append("MISSING_MATCH_START")
        elif start is not None and start <= now:
            shadow_reasons.append("MATCH_STARTED")
        if confidence_rank(row.get("confidence")) < confidence_rank("MED"):
            shadow_reasons.append("CONF_BELOW_MED")
        if sample < MIN_COMBINED_SAMPLE:
            shadow_reasons.append("SAMPLE_BELOW_800")
        if two_way_shadow:
            if gap > args.max_model_market_gap * 100.0:
                shadow_reasons.append("MODEL_MARKET_GAP")
            note_text = str(row.get("notes") or "").upper()
            if any(marker in note_text for marker in TWO_WAY_SHADOW_NOTE_BLOCKERS):
                shadow_reasons.append("NAME_OR_DATA_WARNING")
            if shadow_candidate is None:
                shadow_reasons.append("EDGE_BELOW_GATE")
        else:
            over_odds = parse_float(row.get("over_odds"), 0.0) or 0.0
            if not (ONE_SIDED_MIN_ODDS <= over_odds <= ONE_SIDED_MAX_ODDS):
                shadow_reasons.append("PRICE_OUTSIDE_RESEARCH_RANGE")
            raw_over = (parse_float(row.get("value_over_pct"), 0.0) or 0.0) / 100.0
            if raw_over < ONE_SIDED_MIN_VALUE:
                shadow_reasons.append("EDGE_BELOW_GATE")

        trackable_shadow = not shadow_reasons
        row["trackable_shadow"] = bool_text(trackable_shadow)
        row["shadow_side"] = (
            shadow_candidate[0]
            if trackable_shadow and two_way_shadow and shadow_candidate is not None
            else ("OVER" if trackable_shadow else "")
        )
        row["shadow_block_reasons"] = "|".join(dict.fromkeys(shadow_reasons))
        if row["bettable"] == "true":
            row["decision_mode"] = "two_way_decision"
        elif trackable_shadow:
            row["decision_mode"] = "two_way_player_shadow" if two_way_shadow else "one_sided_over_shadow"
        else:
            row["decision_mode"] = "blocked"


def market_mean(board_row: dict[str, str], market: str) -> float | None:
    lower = market.lower().replace(" ", "_")
    if lower in {"aces", "ace", "player_aces", "match_aces"}:
        return parse_float(board_row.get("projected_aces"))
    if lower in {"double_faults", "double_fault", "dfs", "df", "match_double_faults"}:
        return parse_float(board_row.get("projected_dfs"))
    if lower in BREAK_MARKETS:
        return parse_float(board_row.get("projected_breaks_for"))
    return None


def market_confidence(board_row: dict[str, str], market: str) -> str:
    lower = market.lower().replace(" ", "_")
    if lower in {"aces", "ace", "player_aces", "match_aces"}:
        return str(board_row.get("ace_confidence") or "")
    if lower in {"double_faults", "double_fault", "dfs", "df", "match_double_faults"}:
        return str(board_row.get("df_confidence") or "")
    if lower in BREAK_MARKETS:
        return str(board_row.get("break_confidence") or "")
    return ""


def is_match_total_count_market(market: str) -> bool:
    return market.lower().replace(" ", "_") in MATCH_TOTAL_MARKETS


def annotate_break_source_agreement(rows: list[dict[str, str]], now: datetime) -> None:
    """Mark exact-line cross-book agreement for the higher-confidence break cohort."""
    grouped: dict[tuple[object, ...], list[dict[str, str]]] = {}
    for row in rows:
        market = str(row.get("market") or "").lower()
        if market not in BREAK_MARKETS:
            continue
        line = parse_float(row.get("line"))
        identity = line_group_key(row)[:4]
        key = (*identity, market, round(line, 3) if line is not None else None)
        grouped.setdefault(key, []).append(row)

    for group_rows in grouped.values():
        prices_by_book: dict[str, float] = {}
        display_names: dict[str, str] = {}
        for row in group_rows:
            bookmaker = str(row.get("bookmaker") or "").strip()
            book_key = norm_name(bookmaker)
            captured_at = parse_timestamp(row.get("capture_ts"))
            starts_at = parse_timestamp(row.get("match_start_utc"))
            capture_age = hours_since(row.get("capture_ts"), now)
            over = parse_float(row.get("over_odds"))
            under = parse_float(row.get("under_odds"))
            no_vig_over, _no_vig_under = no_vig_probabilities(over, under)
            if (
                not book_key
                or no_vig_over is None
                or captured_at is None
                or capture_age is None
                or capture_age > BREAK_PROSPECTIVE_CAPTURE_HOURS
                or (starts_at is not None and starts_at <= now)
            ):
                continue
            prices_by_book.setdefault(book_key, no_vig_over)
            display_names.setdefault(book_key, bookmaker)

        probabilities = list(prices_by_book.values())
        spread_pp = (
            (max(probabilities) - min(probabilities)) * 100.0
            if len(probabilities) >= 2
            else None
        )
        agreed = spread_pp is not None and spread_pp <= BREAK_SOURCE_AGREEMENT_MAX_PP
        books = ",".join(sorted(display_names.values()))
        for row in group_rows:
            row["source_agreement"] = bool_text(agreed)
            row["source_agreement_bookmakers"] = books
            row["source_agreement_gap_pp"] = fmt(spread_pp, 2)


def break_line_supported(row: dict[str, str]) -> bool:
    line = parse_float(row.get("line"))
    if line is None or abs(line * 2.0 - round(line * 2.0)) > 1e-6:
        return False
    lower, upper = BREAK_MATCH_LINE_RANGE if row.get("scope") == "match_total" else BREAK_PLAYER_LINE_RANGE
    return lower <= line <= upper


def apply_break_shadow_gates(rows: list[dict[str, str]], now: datetime) -> None:
    """Split raw count calibration from strict prospective ROI/CLV evidence."""
    annotate_break_source_agreement(rows, now)
    for row in rows:
        if str(row.get("market") or "").lower() not in BREAK_MARKETS:
            continue
        structural_reasons: list[str] = []
        strict_reasons: list[str] = []
        if row.get("breaks_stage0_passed") != "true":
            strict_reasons.append("OUTCOME_GATE_FAIL")
        if row.get("matched_board") != "yes":
            strict_reasons.append("NO_BOARD_MATCH")
        if parse_float(row.get("line")) is None:
            structural_reasons.append("MISSING_LINE")
        if row.get("price_pair_status") == "missing_prices":
            structural_reasons.append("MISSING_PRICES")
        capture = parse_timestamp(row.get("capture_ts"))
        start = parse_timestamp(row.get("match_start_utc"))
        if capture is None:
            structural_reasons.append("MISSING_CAPTURE_TS")
        if start is None:
            structural_reasons.append("MISSING_MATCH_START")
        elif capture is not None and capture > start:
            structural_reasons.append("CAPTURE_AFTER_START")

        strict_reasons = [*structural_reasons, *strict_reasons]
        if row.get("price_pair_status") != "two_way":
            strict_reasons.append("TWO_WAY_PRICE_REQUIRED")
        if row.get("line_quality") != "complete":
            strict_reasons.append("LINE_NOT_COMPLETE")
        if row.get("main_line") != "true":
            strict_reasons.append("NOT_MAIN_LINE")
        if capture is not None:
            capture_age = hours_since(row.get("capture_ts"), now)
            if capture_age is not None and capture_age > BREAK_PROSPECTIVE_CAPTURE_HOURS:
                strict_reasons.append("STALE_CAPTURE_90M")
        if start is not None and start <= now:
            strict_reasons.append("MATCH_STARTED")
        if confidence_rank(row.get("confidence")) < confidence_rank("HIGH"):
            strict_reasons.append("CONF_BELOW_HIGH")
        sample = parse_float(row.get("combined_surface_svpt_sample"), 0.0) or 0.0
        if sample < MIN_COMBINED_SAMPLE:
            strict_reasons.append("SAMPLE_BELOW_800")
        gap = parse_float(row.get("model_market_gap_pp"), 0.0) or 0.0
        if gap > BREAK_MAX_MODEL_MARKET_GAP_PP:
            strict_reasons.append("MODEL_MARKET_GAP")
        note_text = str(row.get("notes") or "").upper()
        if any(marker in note_text for marker in TWO_WAY_SHADOW_NOTE_BLOCKERS):
            strict_reasons.append("NAME_OR_DATA_WARNING")
        if not break_line_supported(row):
            strict_reasons.append("UNSUPPORTED_LINE")
        candidates: list[tuple[str, float, float]] = []
        for side, value_key, odds_key in (
            ("OVER", "value_over_pct", "over_odds"),
            ("UNDER", "value_under_pct", "under_odds"),
        ):
            value = parse_float(row.get(value_key))
            odds = parse_float(row.get(odds_key))
            if (
                value is not None
                and BREAK_MIN_VALUE_PCT <= value <= BREAK_MAX_VALUE_PCT
                and odds is not None
                and ONE_SIDED_MIN_ODDS <= odds <= ONE_SIDED_MAX_ODDS
            ):
                candidates.append((side, value, odds))
        if not candidates:
            strict_reasons.append("EDGE_OUTSIDE_3_TO_12_PCT")
        selected = max(candidates, key=lambda item: item[1])[0] if candidates else ""
        strict_reasons = list(dict.fromkeys(strict_reasons))
        structural_reasons = list(dict.fromkeys(structural_reasons))
        source_verified = row.get("source_agreement") == "true"
        single_source_bet365 = norm_name(row.get("bookmaker")) == "bet365"
        trackable = not strict_reasons and (source_verified or single_source_bet365)
        calibration_eligible = not structural_reasons
        if not trackable and not source_verified and not single_source_bet365:
            strict_reasons.append("PRICE_SOURCE_UNVERIFIED")
        row["bettable"] = "false"
        row["recommended_side"] = ""
        row["trackable_shadow"] = bool_text(trackable)
        row["shadow_side"] = selected if trackable else ""
        row["calibration_eligible"] = bool_text(calibration_eligible)
        row["gate_version"] = BREAK_GATE_VERSION
        if trackable:
            row["decision_mode"] = BREAK_STRICT_MODE if source_verified else BREAK_SINGLE_SOURCE_MODE
        elif calibration_eligible:
            row["decision_mode"] = "breaks_calibration_unfiltered"
        else:
            row["decision_mode"] = "breaks_blocked"
        row["cohort"] = row["decision_mode"]
        row["shadow_block_reasons"] = "|".join(strict_reasons)


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
    parser.add_argument("--totals-gate", default=str(DEFAULT_TOTALS_GATE))
    parser.add_argument("--breaks-gate", default=str(DEFAULT_BREAK_GATE))
    parser.add_argument("--lines", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--unmatched-out", default="")
    parser.add_argument(
        "--market-filter",
        default="",
        help="Optional comma-separated market keys to retain before matching.",
    )
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
    if not lines_path.exists():
        print(f"Lines file not found: {lines_path}")
        return
    input_line_rows = [normalize_legacy_team_total_row(row) for row in read_csv(lines_path)]
    line_rows, stale_event_rows = filter_line_rows_for_as_of(input_line_rows, args.date)
    line_rows = filter_line_rows_by_market(line_rows, args.market_filter)
    if not line_rows:
        print(
            f"Lines file has no eligible market rows: {lines_path} "
            f"(input={len(input_line_rows)}, past_event_rows_excluded={stale_event_rows})"
        )
        return
    board_rows = read_csv(Path(args.board))
    totals_gate = read_json(Path(args.totals_gate))
    breaks_gate = read_json(Path(args.breaks_gate))
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
    now_utc = datetime.now(timezone.utc)
    for line in line_rows:
        line_date = str(line.get("date") or args.date)
        line_tour = str(line.get("tour") or "").upper()
        line_player = str(line.get("player") or "").strip()
        line_opponent = str(line.get("opponent") or "").strip()
        line_market = str(line.get("market") or "").strip()
        totals_passed, totals_alpha = totals_gate_result(totals_gate, line_tour, line_market)
        breaks_passed, breaks_distribution, breaks_alpha = break_gate_result(
            breaks_gate, line_tour, line_market
        )
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
        if board_row is None and not requires_exact_pair and can_fallback_player_only(
            original_player, original_opponent
        ):
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
        left_mean: float | None = None
        right_mean: float | None = None
        p1_confidence = market_confidence(board_row or {}, market) if board_row else "LOW"
        p2_confidence = ""
        if board_row and counterpart_row:
            left_mean = market_mean(board_row, market)
            right_mean = market_mean(counterpart_row, market)
            p2_confidence = market_confidence(counterpart_row, market)
            mean = (
                left_mean + right_mean
                if left_mean is not None and right_mean is not None
                else None
            )
        else:
            left_mean = market_mean(board_row or {}, market) if board_row else None
            mean = left_mean
        line_value = parse_float(line.get("line"))
        over_odds = parse_float(line.get("over_odds"))
        under_odds = parse_float(line.get("under_odds"))
        if mean is not None and line_value is not None:
            selected_distribution = (
                breaks_distribution if market in BREAK_MARKETS else args.distribution
            )
            if selected_distribution == "poisson":
                p_over, p_under, p_push = poisson_line_probabilities(line_value, mean)
            else:
                p_over, p_under, p_push = count_line_probabilities(
                    line_value,
                    mean,
                    distribution=selected_distribution,
                    alpha=(
                        breaks_alpha
                        if market in BREAK_MARKETS
                        else totals_alpha
                        if is_match_total_count_market(market)
                        else None
                    ),
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
        edge_over_novig_ratio = no_vig_edge_ratio(model_over, novig_over)
        edge_under_novig_ratio = no_vig_edge_ratio(model_under, novig_under)
        model_market_gap = max(
            [abs(value) for value in (edge_over_novig, edge_under_novig) if value is not None],
            default=None,
        )
        confidence = p1_confidence
        notes = str((board_row or {}).get("notes") or "")
        combined_sample = combined_board_sample(board_row, counterpart_row)
        if counterpart_row:
            confidence = confidence_floor(confidence, p2_confidence)
            other_notes = str(counterpart_row.get("notes") or "")
            notes = " | ".join(part for part in (notes, other_notes) if part)
        elif board_row and is_match_total_count_market(market):
            notes = " | ".join(part for part in (notes, "MATCH_TOTAL_COUNTERPART_MISSING") if part)
        price_status = price_pair_status(over_odds, under_odds)
        line_quality, line_quality_reason = line_quality_from_shape(over_odds, under_odds, line_value, mean)
        recommended = ""
        blocked_reason = ""

        rows.append(
            {
                **line,
                "date": str((board_row or {}).get("date") or line_date),
                "tour": str((board_row or {}).get("tour") or line_tour),
                "tournament": str((board_row or {}).get("tournament") or line.get("tournament") or ""),
                "surface": str((board_row or {}).get("surface") or ""),
                "player": line_player,
                "opponent": line_opponent,
                "event_id": str(line.get("event_id") or ""),
                "bookmaker": str(line.get("bookmaker") or ""),
                "raw_market_name": str(line.get("raw_market_name") or ""),
                "raw_outcome_count": str(line.get("raw_outcome_count") or ""),
                "raw_label_sample": str(line.get("raw_label_sample") or ""),
                "matched_board": "yes" if board_row else "no",
                "match_source": match_source,
                "scope": "match_total" if is_match_total_count_market(market) else "player",
                "totals_stage0_passed": bool_text(totals_passed) if market in {"match_aces", "match_double_faults"} else "false",
                "totals_alpha": fmt(totals_alpha, 6),
                "breaks_stage0_passed": bool_text(breaks_passed) if market in BREAK_MARKETS else "false",
                "breaks_alpha": fmt(breaks_alpha, 6),
                "projection_mean": fmt(mean, 3),
                "projection_p1": fmt(left_mean, 3),
                "projection_p2": fmt(right_mean, 3),
                "p1_confidence": p1_confidence,
                "p2_confidence": p2_confidence,
                "combined_surface_svpt_sample": fmt(combined_sample, 0),
                "confidence": confidence,
                "line_quality": line_quality,
                "line_quality_reason": line_quality_reason,
                "price_pair_status": price_status,
                "source_agreement": "false",
                "source_agreement_bookmakers": "",
                "source_agreement_gap_pp": "",
                "calibration_eligible": "false",
                "cohort": "",
                "gate_version": "",
                "decision_mode": "",
                "main_line": "false",
                "best_available_line": "false",
                "line_rank": "",
                "group_line_count": "",
                "complete_line_count": "",
                "capture_ts": str(line.get("capture_ts") or line.get("captured_at") or ""),
                "match_start_utc": str(line.get("match_start_utc") or line.get("kickoff_at") or ""),
                "notes": notes,
                "fair_p_over": fmt(p_over),
                "fair_p_under": fmt(p_under),
                "fair_p_push": fmt(p_push),
                "distribution": selected_distribution if mean is not None and line_value is not None else args.distribution,
                "fair_over_odds": fmt(fair_over, 3),
                "fair_under_odds": fmt(fair_under, 3),
                "value_over_pct": fmt((value_over * 100.0) if value_over is not None else None, 2),
                "value_under_pct": fmt((value_under * 100.0) if value_under is not None else None, 2),
                "novig_p_over": fmt(novig_over),
                "novig_p_under": fmt(novig_under),
                "edge_over_novig_pp": fmt((edge_over_novig * 100.0) if edge_over_novig is not None else None, 2),
                "edge_under_novig_pp": fmt((edge_under_novig * 100.0) if edge_under_novig is not None else None, 2),
                "edge_over_novig_pct": fmt((edge_over_novig_ratio * 100.0) if edge_over_novig_ratio is not None else None, 2),
                "edge_under_novig_pct": fmt((edge_under_novig_ratio * 100.0) if edge_under_novig_ratio is not None else None, 2),
                "model_market_gap_pp": fmt((model_market_gap * 100.0) if model_market_gap is not None else None, 2),
                "blocked_reason": blocked_reason,
                "block_reasons": "",
                "bettable": "false",
                "recommended_side": recommended,
            }
        )

    apply_decision_gates(rows, args, now_utc)
    apply_break_shadow_gates(rows, now_utc)

    fieldnames = [
        "date",
        "tour",
        "tournament",
        "surface",
        "player",
        "opponent",
        "market",
        "line",
        "over_odds",
        "under_odds",
        "event_id",
        "bookmaker",
        "raw_market_name",
        "raw_outcome_count",
        "raw_label_sample",
        "scope",
        "totals_stage0_passed",
        "totals_alpha",
        "breaks_stage0_passed",
        "breaks_alpha",
        "matched_board",
        "match_source",
        "projection_mean",
        "projection_p1",
        "projection_p2",
        "p1_confidence",
        "p2_confidence",
        "combined_surface_svpt_sample",
        "confidence",
        "line_quality",
        "line_quality_reason",
        "price_pair_status",
        "source_agreement",
        "source_agreement_bookmakers",
        "source_agreement_gap_pp",
        "calibration_eligible",
        "cohort",
        "gate_version",
        "main_line",
        "best_available_line",
        "line_rank",
        "group_line_count",
        "complete_line_count",
        "capture_ts",
        "match_start_utc",
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
        "edge_over_novig_pct",
        "edge_under_novig_pct",
        "model_market_gap_pp",
        "decision_mode",
        "trackable_shadow",
        "shadow_side",
        "shadow_block_reasons",
        "blocked_reason",
        "block_reasons",
        "bettable",
        "recommended_side",
    ]
    write_csv(out_path, rows, fieldnames)
    print(f"Saved {len(rows)} rows: {out_path}")
    write_csv(unmatched_out_path, unmatched_rows, UNMATCHED_FIELDS)
    print(f"Saved {len(unmatched_rows)} unmatched rows: {unmatched_out_path}")
    print(
        "Comparison funnel: "
        f"input={len(input_line_rows)} "
        f"past_event_rows_excluded={stale_event_rows} "
        f"eligible={len(line_rows)} "
        f"matched={sum(row.get('matched_board') == 'yes' for row in rows)} "
        f"unmatched={len(unmatched_rows)}"
    )
    if not lines_path.exists():
        print(f"Lines file not found: {lines_path}")


if __name__ == "__main__":
    main()
