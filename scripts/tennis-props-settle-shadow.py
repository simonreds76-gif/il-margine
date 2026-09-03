#!/usr/bin/env python3
"""Settle internal Bet365 tennis aces/DF shadow signals from Sackmann service stats."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parent.parent
PROPS_DIR = ROOT / "data" / "tennis-props"
DEFAULT_SIGNALS = PROPS_DIR / "shadow" / "aces-dfs-shadow-signals.csv"
DEFAULT_PERFORMANCE = PROPS_DIR / "shadow" / "aces-dfs-shadow-performance.txt"
DEFAULT_SACKMANN = ROOT / "data" / "sackmann"
DEFAULT_ONCOURT = ROOT / "data" / "oncourt"
BREAK_CALIBRATION_MODE = "breaks_calibration_unfiltered"

FIELDNAMES = [
    "signal_id",
    "logged_at_utc",
    "date",
    "tour",
    "tournament",
    "scope",
    "player",
    "opponent",
    "market",
    "line",
    "side",
    "projection_mean",
    "projection_p1",
    "projection_p2",
    "confidence",
    "p1_confidence",
    "p2_confidence",
    "combined_surface_svpt_sample",
    "bookmaker",
    "event_id",
    "capture_ts",
    "match_start_utc",
    "decision_key",
    "entry_novig_p_over",
    "latest_line",
    "latest_over_odds",
    "latest_under_odds",
    "latest_capture_ts",
    "latest_novig_p_over",
    "market_p_over_move_pp",
    "line_move",
    "market_move_status",
    "over_odds",
    "under_odds",
    "selected_odds",
    "closing_odds",
    "closing_ts_utc",
    "closing_snapshot_count",
    "clv_pct",
    "clv_method",
    "fair_over_odds",
    "fair_under_odds",
    "fair_odds",
    "fair_p_push",
    "distribution",
    "totals_alpha",
    "totals_stage0_passed",
    "breaks_alpha",
    "breaks_stage0_passed",
    "value_over_pct",
    "value_under_pct",
    "value_pct",
    "novig_p_over",
    "novig_p_under",
    "edge_over_novig_pct",
    "edge_under_novig_pct",
    "matched_board",
    "decision_mode",
    "price_pair_status",
    "cohort",
    "gate_version",
    "trackable_shadow",
    "shadow_side",
    "shadow_block_reasons",
    "calibration_eligible",
    "line_quality",
    "main_line",
    "best_available_line",
    "model_market_gap_pp",
    "source_agreement",
    "source_agreement_bookmakers",
    "source_agreement_gap_pp",
    "observed_side",
    "observed_odds",
    "observed_value_pct",
    "notes",
    "source_file",
    "settlement_status",
    "actual",
    "result",
    "pnl",
    "settled_at_utc",
    "settlement_note",
    "control_projection_mean",
    "candidate_projection_mean",
    "control_p_over_no_push",
    "candidate_p_over_no_push",
    "venue_v1_factor",
    "venue_v1_control_factor",
    "venue_v1_prior_svpt",
    "venue_v1_source_seasons",
    "venue_v1_model",
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


def participant_key(name: object) -> tuple[str, str]:
    return ("__participant__", norm_text(name))


def normalize_legacy_break_row(row: dict[str, str]) -> dict[str, str]:
    normalized = dict(row)
    market = str(normalized.get("market") or "").strip().lower()
    mode = str(normalized.get("decision_mode") or "").strip()
    if market not in {"player_breaks", "match_breaks"} or mode not in {"", "breaks_shadow"}:
        return normalized
    normalized["observed_side"] = normalized.get("observed_side") or normalized.get("side", "")
    normalized["observed_odds"] = normalized.get("observed_odds") or normalized.get("selected_odds", "")
    normalized["observed_value_pct"] = normalized.get("observed_value_pct") or normalized.get("value_pct", "")
    for field in (
        "side",
        "selected_odds",
        "closing_odds",
        "closing_ts_utc",
        "closing_snapshot_count",
        "clv_pct",
        "clv_method",
        "fair_odds",
        "value_pct",
        "shadow_side",
    ):
        normalized[field] = ""
    normalized["decision_mode"] = BREAK_CALIBRATION_MODE
    normalized["cohort"] = BREAK_CALIBRATION_MODE
    normalized["gate_version"] = "breaks_v1_p0"
    normalized["trackable_shadow"] = "false"
    if (normalized.get("settlement_status") or "").lower() == "settled":
        normalized["result"] = "calibration"
        normalized["pnl"] = ""
    return normalized


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


def parse_signal_date(value: object) -> date | None:
    text = str(value or "").strip()
    if len(text) >= 10:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def parse_sackmann_date(value: object) -> date | None:
    text = str(value or "").strip()
    if len(text) >= 8 and text[:8].isdigit():
        try:
            return datetime.strptime(text[:8], "%Y%m%d").date()
        except ValueError:
            return None
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


def iter_csv(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            yield dict(row)


def parse_utc_datetime(value: object) -> datetime | None:
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


def history_key(row: dict[str, str], *, fallback: bool = False) -> tuple[object, ...]:
    line = parse_float(row.get("line"))
    line_key = round(line, 3) if line is not None else None
    market = norm_text(row.get("market"))
    subject = "" if market in {"match aces", "match double faults", "match breaks"} else norm_text(row.get("player"))
    common = (
        norm_text(row.get("bookmaker")),
        market,
        subject,
        line_key,
    )
    event_id = str(row.get("event_id") or "").strip()
    if event_id and not fallback:
        return ("event", event_id, *common)
    return (
        "pair",
        str(row.get("date") or "").strip(),
        str(row.get("tour") or "").upper(),
        pair_key(row.get("player"), row.get("opponent")),
        *common,
    )


def load_price_history(paths: list[Path]) -> tuple[dict[tuple[object, ...], list[dict[str, str]]], dict[tuple[object, ...], list[dict[str, str]]]]:
    by_event: dict[tuple[object, ...], list[dict[str, str]]] = defaultdict(list)
    by_pair: dict[tuple[object, ...], list[dict[str, str]]] = defaultdict(list)
    for path in paths:
        for row in read_csv(path):
            by_event[history_key(row)].append(row)
            by_pair[history_key(row, fallback=True)].append(row)
    return by_event, by_pair


def enrich_closing_price(
    signal: dict[str, str],
    by_event: dict[tuple[object, ...], list[dict[str, str]]],
    by_pair: dict[tuple[object, ...], list[dict[str, str]]],
) -> bool:
    for field in (
        "closing_odds",
        "closing_ts_utc",
        "closing_snapshot_count",
        "clv_pct",
        "clv_method",
    ):
        signal[field] = ""
    if signal.get("decision_mode") == BREAK_CALIBRATION_MODE:
        return False
    match_start = parse_utc_datetime(signal.get("match_start_utc"))
    entry_ts = parse_utc_datetime(signal.get("capture_ts")) or parse_utc_datetime(signal.get("logged_at_utc"))
    side = str(signal.get("side") or "").upper()
    selected_odds = parse_float(signal.get("selected_odds"))
    if match_start is None or entry_ts is None or side not in {"OVER", "UNDER"} or selected_odds is None:
        return False
    candidates = by_event.get(history_key(signal), [])
    method = "event_id_latest_prestart"
    if not candidates:
        candidates = by_pair.get(history_key(signal, fallback=True), [])
        method = "pair_latest_prestart"
    price_field = "over_odds" if side == "OVER" else "under_odds"
    priced: list[tuple[datetime, float]] = []
    for row in candidates:
        captured_at = parse_utc_datetime(row.get("capture_ts"))
        odds = parse_float(row.get(price_field))
        if captured_at is None or odds is None or odds <= 1.0 or captured_at > match_start:
            continue
        priced.append((captured_at, odds))
    distinct_timestamps = {captured_at for captured_at, _odds in priced}
    if len(distinct_timestamps) < 2:
        return False
    priced.sort(key=lambda item: item[0])
    closing_ts, closing_odds = priced[-1]
    if closing_ts <= entry_ts:
        return False
    clv_pct = (selected_odds / closing_odds - 1.0) * 100.0
    signal["closing_odds"] = f"{closing_odds:.3f}"
    signal["closing_ts_utc"] = closing_ts.isoformat(timespec="seconds")
    signal["closing_snapshot_count"] = str(len(distinct_timestamps))
    signal["clv_pct"] = f"{clv_pct:.3f}"
    signal["clv_method"] = f"{method}_min2_postentry"
    return True


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
    if lower == "match_aces":
        left = parse_float(row.get("w_ace"))
        right = parse_float(row.get("l_ace"))
        if left is None or right is None:
            return None, "missing_match_ace_stats"
        return int(round(left + right)), "ok"
    if lower == "match_double_faults":
        left = parse_float(row.get("w_df"))
        right = parse_float(row.get("l_df"))
        if left is None or right is None:
            return None, "missing_match_df_stats"
        return int(round(left + right)), "ok"
    if lower == "match_breaks":
        winner_breaks = parse_float(row.get("l_bpFaced"))
        winner_saved = parse_float(row.get("l_bpSaved"))
        loser_breaks = parse_float(row.get("w_bpFaced"))
        loser_saved = parse_float(row.get("w_bpSaved"))
        if None in {winner_breaks, winner_saved, loser_breaks, loser_saved}:
            return None, "missing_match_break_stats"
        total = max(0.0, winner_breaks - winner_saved) + max(0.0, loser_breaks - loser_saved)
        return int(round(total)), "ok"
    if lower in {"aces", "ace", "player_aces"}:
        raw = row.get("w_ace") if is_winner else row.get("l_ace")
    elif lower in {"double_faults", "double_fault", "dfs", "df"}:
        raw = row.get("w_df") if is_winner else row.get("l_df")
    elif lower == "player_breaks":
        faced = parse_float(row.get("l_bpFaced") if is_winner else row.get("w_bpFaced"))
        saved = parse_float(row.get("l_bpSaved") if is_winner else row.get("w_bpSaved"))
        if faced is None or saved is None:
            return None, "missing_player_break_stats"
        return int(round(max(0.0, faced - saved))), "ok"
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


def load_sackmann_index(
    sackmann_dir: Path,
    signals: list[dict[str, str]] | None = None,
) -> dict[tuple[str, int, tuple[str, str]], list[dict[str, str]]]:
    index: dict[tuple[str, int, tuple[str, str]], list[dict[str, str]]] = defaultdict(list)
    wanted: dict[tuple[str, int], set[tuple[str, str]]] = defaultdict(set)
    for signal in signals or []:
        tour = (signal.get("tour") or "").upper()
        year = parse_year(signal.get("date"))
        if tour in {"ATP", "WTA"} and year is not None:
            wanted[(tour, year)].add(pair_key(signal.get("player"), signal.get("opponent")))
    for path in sorted(sackmann_dir.glob("*_matches_20*.csv")):
        if "qual_chall" in path.name:
            continue
        tour = "ATP" if path.name.startswith("atp_") else "WTA" if path.name.startswith("wta_") else ""
        if not tour:
            continue
        for row in iter_csv(path):
            year = sackmann_year(row.get("tourney_date"))
            if year is None:
                continue
            pair = pair_key(row.get("winner_name"), row.get("loser_name"))
            if wanted and pair not in wanted.get((tour, year), set()):
                continue
            key = (tour, year, pair)
            index[key].append(row)
    return index


def load_oncourt_index(
    oncourt_dir: Path,
    signals: list[dict[str, str]],
) -> dict[tuple[str, int, tuple[str, str]], list[dict[str, str]]]:
    """Resolve current results from the local OnCourt game/stat exports."""
    wanted: dict[tuple[str, int], set[tuple[str, str]]] = defaultdict(set)
    wanted_participants: dict[tuple[str, int], set[str]] = defaultdict(set)
    for signal in signals:
        tour = (signal.get("tour") or "").upper()
        year = parse_year(signal.get("date"))
        if tour in {"ATP", "WTA"} and year is not None:
            wanted[(tour, year)].add(pair_key(signal.get("player"), signal.get("opponent")))
            wanted_participants[(tour, year)].update(
                {norm_text(signal.get("player")), norm_text(signal.get("opponent"))}
            )
    if not wanted:
        return {}

    index: dict[tuple[str, int, tuple[str, str]], list[dict[str, str]]] = defaultdict(list)
    for tour in ("ATP", "WTA"):
        relevant_years = {year for candidate_tour, year in wanted if candidate_tour == tour}
        if not relevant_years:
            continue
        suffix = tour.lower()
        players = {
            str(row.get("id") or "").strip(): str(row.get("name") or "").strip()
            for row in read_csv(oncourt_dir / f"players_{suffix}.csv")
            if row.get("id") and row.get("name")
        }
        tours = {
            str(row.get("id") or "").strip(): str(row.get("name") or "").strip()
            for row in read_csv(oncourt_dir / f"tours_{suffix}.csv")
            if row.get("id")
        }
        candidate_games: list[tuple[dict[str, str], tuple[str, str, str], tuple[str, int, tuple[str, str]]]] = []
        stat_keys: set[tuple[str, str, str]] = set()
        for game in iter_csv(oncourt_dir / f"games_{suffix}.csv"):
            game_date = parse_signal_date(game.get("date"))
            if game_date is None or game_date.year not in relevant_years:
                continue
            winner_id = str(game.get("winner_id") or "").strip()
            loser_id = str(game.get("loser_id") or "").strip()
            winner_name = players.get(winner_id, "")
            loser_name = players.get(loser_id, "")
            pair = pair_key(winner_name, loser_name)
            lookup_key = (tour, game_date.year, pair)
            participant_names = wanted_participants.get((tour, game_date.year), set())
            matching_participants = {
                name for name in (norm_text(winner_name), norm_text(loser_name)) if name in participant_names
            }
            if matching_participants:
                appearance = {
                    "winner_name": winner_name,
                    "loser_name": loser_name,
                    "tourney_name": tours.get(str(game.get("tour_id") or "").strip(), str(game.get("tour_id") or "")),
                    "tourney_date": game_date.strftime("%Y%m%d"),
                    "score": str(game.get("result") or ""),
                    "_settlement_source": "oncourt",
                }
                for participant in matching_participants:
                    index[(tour, game_date.year, participant_key(participant))].append(appearance)

            if pair not in wanted.get((tour, game_date.year), set()):
                continue
            stat_key = (
                winner_id,
                loser_id,
                str(game.get("tour_id") or "").strip(),
            )
            stat_keys.add(stat_key)
            candidate_games.append((game, stat_key, lookup_key))

        stats: dict[tuple[str, str, str], dict[str, str]] = {}
        if stat_keys:
            for stat in iter_csv(oncourt_dir / f"stat_{suffix}.csv"):
                stat_key = (
                    str(stat.get("winner_id") or "").strip(),
                    str(stat.get("loser_id") or "").strip(),
                    str(stat.get("tour_id") or "").strip(),
                )
                if stat_key in stat_keys:
                    stats.setdefault(stat_key, stat)

        for game, stat_key, lookup_key in candidate_games:
            stat = stats.get(stat_key)
            if not stat:
                continue
            game_date = parse_signal_date(game.get("date"))
            winner_name = players.get(stat_key[0], "")
            loser_name = players.get(stat_key[1], "")
            index[lookup_key].append(
                {
                    "winner_name": winner_name,
                    "loser_name": loser_name,
                    "tourney_name": tours.get(stat_key[2], stat_key[2]),
                    "tourney_date": game_date.strftime("%Y%m%d") if game_date else "",
                    "score": str(game.get("result") or ""),
                    "w_ace": str(stat.get("w_ace") or ""),
                    "l_ace": str(stat.get("l_ace") or ""),
                    "w_df": str(stat.get("w_df") or ""),
                    "l_df": str(stat.get("l_df") or ""),
                    "w_bpSaved": str(stat.get("w_bpsaved") or ""),
                    "w_bpFaced": str(stat.get("w_bpfaced") or ""),
                    "l_bpSaved": str(stat.get("l_bpsaved") or ""),
                    "l_bpFaced": str(stat.get("l_bpfaced") or ""),
                    "_settlement_source": "oncourt",
                }
            )
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

    def canonical(value: str) -> str:
        for alias, canonical_name in slam_aliases.items():
            if alias in value:
                return canonical_name
        return value

    return canonical(sig) == canonical(sm)


def choose_candidate(signal: dict[str, str], candidates: list[dict[str, str]]) -> dict[str, str] | None:
    if not candidates:
        return None
    tournament = signal.get("tournament", "")
    signal_date = parse_signal_date(signal.get("date"))
    if signal_date:
        same_day = [
            row
            for row in candidates
            if parse_sackmann_date(row.get("tourney_date")) == signal_date
        ]
        if len(same_day) == 1:
            return same_day[0]
        same_day_overlapped = [
            row for row in same_day if tournament_overlap(tournament, row.get("tourney_name", ""))
        ]
        if len(same_day_overlapped) == 1:
            return same_day_overlapped[0]
        if same_day:
            return None

    overlapped = [r for r in candidates if tournament_overlap(tournament, r.get("tourney_name", ""))]
    if overlapped:
        pool = overlapped
    else:
        # A unique same-pair match at another event is still the wrong match.
        # Never use it merely because no second candidate exists.
        return None

    if signal_date:
        dated = [(row, parse_sackmann_date(row.get("tourney_date"))) for row in pool]
        with_dates = [(row, dt) for row, dt in dated if dt is not None]
        if with_dates:
            return sorted(with_dates, key=lambda item: abs((item[1] - signal_date).days))[0][0]
    return sorted(pool, key=lambda r: str(r.get("tourney_date") or ""), reverse=True)[0]


def find_replacement_candidate(
    signal: dict[str, str], candidates: list[dict[str, str]]
) -> dict[str, str] | None:
    """Find an unambiguous same-day replacement match for a cancelled market."""
    signal_date = parse_signal_date(signal.get("date"))
    if signal_date is None:
        return None
    original_pair = pair_key(signal.get("player"), signal.get("opponent"))
    original_participants = set(original_pair)
    matches: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for candidate in candidates:
        candidate_date = parse_sackmann_date(candidate.get("tourney_date"))
        candidate_pair = pair_key(candidate.get("winner_name"), candidate.get("loser_name"))
        if candidate_date != signal_date or candidate_pair == original_pair:
            continue
        if not original_participants.intersection(candidate_pair):
            continue
        if not tournament_overlap(signal.get("tournament", ""), candidate.get("tourney_name", "")):
            continue
        dedupe_key = (
            candidate_pair[0],
            candidate_pair[1],
            str(candidate.get("tourney_date") or ""),
            norm_text(candidate.get("tourney_name")),
        )
        matches[dedupe_key] = candidate
    return next(iter(matches.values())) if len(matches) == 1 else None


def resolve_count_candidate(
    signal: dict[str, str],
    oncourt_candidates: list[dict[str, str]],
    sackmann_candidates: list[dict[str, str]],
) -> tuple[dict[str, str] | None, int | None, str]:
    """Prefer OnCourt, but fall back when its export lacks break-point fields."""
    fallback_note = "result_match_not_found"
    fallback_candidate: dict[str, str] | None = None
    for candidates in (oncourt_candidates, sackmann_candidates):
        candidate = choose_candidate(signal, candidates)
        if candidate is None:
            continue
        if fallback_candidate is None:
            fallback_candidate = candidate
        if is_void_score(candidate.get("score")):
            return candidate, None, "void_score"
        actual, note = market_count(candidate, norm_text(signal.get("player")), signal.get("market", ""))
        if actual is not None:
            return candidate, actual, note
        fallback_note = note
    return fallback_candidate, None, fallback_note


def write_performance(path: Path, rows: list[dict[str, str]]) -> None:
    calibration = [r for r in rows if r.get("decision_mode") == BREAK_CALIBRATION_MODE]
    betting_rows = [r for r in rows if r.get("decision_mode") != BREAK_CALIBRATION_MODE]
    settled = [r for r in betting_rows if (r.get("settlement_status") or "").lower() == "settled"]
    pending = [r for r in betting_rows if (r.get("settlement_status") or "").lower() == "pending"]
    voids = [r for r in betting_rows if (r.get("settlement_status") or "").lower() == "void"]
    calibration_settled = [r for r in calibration if (r.get("settlement_status") or "").lower() == "settled"]
    pnl = sum(parse_float(r.get("pnl")) or 0.0 for r in settled)
    roi = pnl / len(settled) * 100.0 if settled else 0.0
    settled_clv = [parse_float(r.get("clv_pct")) for r in settled]
    settled_clv = [value for value in settled_clv if value is not None]
    mean_clv = sum(settled_clv) / len(settled_clv) if settled_clv else 0.0
    positive_clv = sum(value > 0 for value in settled_clv) / len(settled_clv) * 100.0 if settled_clv else 0.0

    def bucket(label: str, key: str) -> list[str]:
        out = [f"\n{label}:"]
        for value in sorted({r.get(key, "") or "-" for r in betting_rows}):
            subset = [r for r in betting_rows if (r.get(key, "") or "-") == value]
            settled_subset = [r for r in subset if (r.get("settlement_status") or "").lower() == "settled"]
            subset_pnl = sum(parse_float(r.get("pnl")) or 0.0 for r in settled_subset)
            subset_roi = subset_pnl / len(settled_subset) * 100.0 if settled_subset else 0.0
            out.append(f"  {value}: rows={len(subset)} settled={len(settled_subset)} pnl={subset_pnl:+.2f}u roi={subset_roi:+.1f}%")
        return out

    lines = [
        "Tennis aces/DF shadow evidence",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "Status: internal shadow only; no public betting record or live staking.",
        f"Betting rows: {len(betting_rows)} | settled: {len(settled)} | pending: {len(pending)} | void: {len(voids)}",
        f"Break calibration rows: {len(calibration)} | counts settled: {len(calibration_settled)} | excluded from ROI/CLV",
        f"PnL: {pnl:+.2f}u | ROI: {roi:+.1f}%",
        f"CLV: coverage={len(settled_clv)}/{len(settled)} | mean={mean_clv:+.2f}% | positive={positive_clv:.1f}%",
        "Promotion guard: do not read ROI seriously before 300 settled lines across at least two Slams.",
    ]
    for label, key in [("By market", "market"), ("By side", "side"), ("By tour", "tour"), ("By confidence", "confidence")]:
        lines.extend(bucket(label, key))
    break_rows = [r for r in betting_rows if r.get("market") in {"player_breaks", "match_breaks"}]
    if break_rows:
        lines.append("\nBreak watchlist by market and side:")
        for market in ("player_breaks", "match_breaks"):
            for side in ("OVER", "UNDER"):
                subset = [r for r in break_rows if r.get("market") == market and r.get("side") == side]
                settled_subset = [r for r in subset if (r.get("settlement_status") or "").lower() == "settled"]
                wins = sum((r.get("result") or "").lower() == "win" for r in settled_subset)
                losses = sum((r.get("result") or "").lower() == "loss" for r in settled_subset)
                pushes = sum((r.get("result") or "").lower() == "push" for r in settled_subset)
                subset_pnl = sum(parse_float(r.get("pnl")) or 0.0 for r in settled_subset)
                subset_roi = subset_pnl / len(settled_subset) * 100.0 if settled_subset else 0.0
                pending_subset = sum((r.get("settlement_status") or "").lower() == "pending" for r in subset)
                lines.append(
                    f"  {market} {side}: settled={len(settled_subset)} "
                    f"W-L-P={wins}-{losses}-{pushes} staked={len(settled_subset):.2f}u "
                    f"pnl={subset_pnl:+.2f}u roi={subset_roi:+.1f}% pending={pending_subset}"
                )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Settle tennis aces/DF shadow signals from Sackmann service stats")
    parser.add_argument("--signals", default=str(DEFAULT_SIGNALS))
    parser.add_argument("--performance", default=str(DEFAULT_PERFORMANCE))
    parser.add_argument("--sackmann-dir", default=str(DEFAULT_SACKMANN))
    parser.add_argument("--oncourt-dir", default=str(DEFAULT_ONCOURT))
    parser.add_argument("--history-glob", default=str(PROPS_DIR / "inbox" / "bet365-lines-history-*.csv"))
    args = parser.parse_args()

    signals_path = Path(args.signals)
    rows = [normalize_legacy_break_row(row) for row in read_csv(signals_path)]
    if not rows:
        write_performance(Path(args.performance), rows)
        print(f"No shadow rows to settle: {signals_path}")
        return 0

    pending_rows = [row for row in rows if (row.get("settlement_status") or "pending").lower() in {"", "pending"}]
    history_pattern = Path(args.history_glob)
    history_paths = sorted(history_pattern.parent.glob(history_pattern.name))
    history_by_event, history_by_pair = load_price_history(history_paths)
    clv_updated = sum(enrich_closing_price(row, history_by_event, history_by_pair) for row in rows)
    oncourt_index = load_oncourt_index(Path(args.oncourt_dir), pending_rows)
    sackmann_index = load_sackmann_index(Path(args.sackmann_dir), pending_rows)
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
        oncourt_candidates = oncourt_index.get(key, [])
        sackmann_candidates = sackmann_index.get(key, [])
        candidate, actual, note = resolve_count_candidate(
            row,
            oncourt_candidates,
            sackmann_candidates,
        )
        if candidate is None:
            replacement_candidates = [
                *oncourt_index.get((tour, year, participant_key(row.get("player"))), []),
                *oncourt_index.get((tour, year, participant_key(row.get("opponent"))), []),
            ]
            replacement = find_replacement_candidate(row, replacement_candidates)
            if replacement is not None:
                row["settlement_status"] = "void"
                row["actual"] = ""
                row["result"] = "void"
                row["pnl"] = "0.000"
                row["settled_at_utc"] = now
                row["settlement_note"] = (
                    "void_replaced_match:"
                    f"{replacement.get('_settlement_source', 'oncourt')}:"
                    f"{replacement.get('winner_name', '')} vs {replacement.get('loser_name', '')}:"
                    f"{replacement.get('tourney_name', '')}"
                )
                settled_now += 1
                continue
            row["settlement_status"] = "pending"
            row["settlement_note"] = (
                "result_match_ambiguous"
                if oncourt_candidates or sackmann_candidates
                else "result_match_not_found"
            )
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
        line = parse_float(row.get("line"))
        odds = parse_float(row.get("selected_odds"))
        if actual is None or line is None:
            row["settlement_status"] = "pending"
            row["settlement_note"] = note if actual is None else "missing_line"
            still_pending += 1
            continue
        is_calibration = row.get("decision_mode") == BREAK_CALIBRATION_MODE
        result = "calibration" if is_calibration else result_for(actual, line, (row.get("side") or "").upper())
        row["settlement_status"] = "settled" if result != "void" else "void"
        row["actual"] = str(actual)
        row["result"] = result
        row["pnl"] = "" if is_calibration else f"{pnl_for(result, odds):.3f}"
        row["settled_at_utc"] = now
        source = candidate.get("_settlement_source") or "sackmann"
        row["settlement_note"] = f"{source}:{candidate.get('tourney_name','')}:{candidate.get('score','')}"
        settled_now += 1

    write_csv(signals_path, rows)
    write_performance(Path(args.performance), rows)
    print(f"Settled/voided now: {settled_now}; CLV rows refreshed: {clv_updated}; still pending checked: {still_pending}; total rows: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
