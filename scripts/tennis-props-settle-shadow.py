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
    # Match-total prices belong to the fixture. Player props at the same line
    # belong to different subjects and must never share a closing-price key.
    subject = "" if market in {"match aces", "match double faults"} else norm_text(row.get("player"))
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
    match_start = parse_utc_datetime(signal.get("match_start_utc"))
    registered_at = parse_utc_datetime(signal.get("logged_at_utc") or signal.get("capture_ts"))
    side = str(signal.get("side") or "").upper()
    selected_odds = parse_float(signal.get("selected_odds"))
    for field in ("closing_odds", "closing_ts_utc", "closing_snapshot_count", "clv_pct", "clv_method"):
        signal[field] = ""
    if match_start is None or registered_at is None or side not in {"OVER", "UNDER"} or selected_odds is None:
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
        if (
            captured_at is None
            or odds is None
            or odds <= 1.0
            or captured_at <= registered_at
            or captured_at > match_start
        ):
            continue
        priced.append((captured_at, odds))
    if not priced:
        return False
    priced.sort(key=lambda item: item[0])
    closing_ts, closing_odds = priced[-1]
    clv_pct = (selected_odds / closing_odds - 1.0) * 100.0
    signal["closing_odds"] = f"{closing_odds:.3f}"
    signal["closing_ts_utc"] = closing_ts.isoformat(timespec="seconds")
    signal["closing_snapshot_count"] = str(len({captured_at for captured_at, _odds in priced}))
    signal["clv_pct"] = f"{clv_pct:.3f}"
    signal["clv_method"] = method
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


def load_oncourt_index(
    oncourt_dir: Path,
    signals: list[dict[str, str]],
) -> dict[tuple[str, int, tuple[str, str]], list[dict[str, str]]]:
    """Resolve current results from the local OnCourt game/stat exports."""
    wanted: dict[tuple[str, int], set[tuple[str, str]]] = defaultdict(set)
    for signal in signals:
        tour = (signal.get("tour") or "").upper()
        year = parse_year(signal.get("date"))
        if tour in {"ATP", "WTA"} and year is not None:
            wanted[(tour, year)].add(pair_key(signal.get("player"), signal.get("opponent")))
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
        for game in read_csv(oncourt_dir / f"games_{suffix}.csv"):
            game_date = parse_signal_date(game.get("date"))
            if game_date is None or game_date.year not in relevant_years:
                continue
            winner_id = str(game.get("winner_id") or "").strip()
            loser_id = str(game.get("loser_id") or "").strip()
            winner_name = players.get(winner_id, "")
            loser_name = players.get(loser_id, "")
            pair = pair_key(winner_name, loser_name)
            lookup_key = (tour, game_date.year, pair)
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
            for stat in read_csv(oncourt_dir / f"stat_{suffix}.csv"):
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
    return slam_aliases.get(sig, sig) == slam_aliases.get(sm, sm)


def choose_candidate(signal: dict[str, str], candidates: list[dict[str, str]]) -> dict[str, str] | None:
    if not candidates:
        return None
    tournament = signal.get("tournament", "")
    overlapped = [r for r in candidates if tournament_overlap(tournament, r.get("tourney_name", ""))]
    if overlapped:
        pool = overlapped
    elif len(candidates) == 1:
        pool = candidates
    else:
        # If the same pair met multiple times in the year and tournament names
        # do not overlap, settling from the most recent match can fabricate a
        # result. Leave it pending for manual review instead.
        return None

    signal_date = parse_signal_date(signal.get("date"))
    if signal_date:
        dated = [(row, parse_sackmann_date(row.get("tourney_date"))) for row in pool]
        with_dates = [(row, dt) for row, dt in dated if dt is not None]
        if with_dates:
            return sorted(with_dates, key=lambda item: abs((item[1] - signal_date).days))[0][0]
    return sorted(pool, key=lambda r: str(r.get("tourney_date") or ""), reverse=True)[0]


def write_performance(path: Path, rows: list[dict[str, str]]) -> None:
    settled = [r for r in rows if (r.get("settlement_status") or "").lower() == "settled"]
    pending = [r for r in rows if (r.get("settlement_status") or "").lower() == "pending"]
    voids = [r for r in rows if (r.get("settlement_status") or "").lower() == "void"]
    pnl = sum(parse_float(r.get("pnl")) or 0.0 for r in settled)
    roi = pnl / len(settled) * 100.0 if settled else 0.0
    now = datetime.now(timezone.utc)
    started = [
        row for row in rows
        if (parse_utc_datetime(row.get("match_start_utc")) or datetime.max.replace(tzinfo=timezone.utc)) <= now
    ]
    clv_values = [parse_float(r.get("clv_pct")) for r in started]
    clv_values = [value for value in clv_values if value is not None]
    mean_clv = sum(clv_values) / len(clv_values) if clv_values else 0.0
    positive_clv = sum(value > 0 for value in clv_values) / len(clv_values) * 100.0 if clv_values else 0.0

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
        f"CLV: coverage={len(clv_values)}/{len(started)} started rows | mean={mean_clv:+.2f}% | positive={positive_clv:.1f}%",
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
    parser.add_argument("--oncourt-dir", default=str(DEFAULT_ONCOURT))
    parser.add_argument("--history-glob", default=str(PROPS_DIR / "inbox" / "bet365-lines-history-*.csv"))
    args = parser.parse_args()

    signals_path = Path(args.signals)
    rows = read_csv(signals_path)
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
    sackmann_index = load_sackmann_index(Path(args.sackmann_dir))
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
        candidates = oncourt_index.get(key, [])
        if not candidates:
            candidates = sackmann_index.get(key, [])
        candidate = choose_candidate(row, candidates)
        if candidate is None:
            row["settlement_status"] = "pending"
            row["settlement_note"] = "sackmann_match_ambiguous" if candidates else "sackmann_match_not_found"
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
        source = candidate.get("_settlement_source") or "sackmann"
        row["settlement_note"] = f"{source}:{candidate.get('tourney_name','')}:{candidate.get('score','')}"
        settled_now += 1

    write_csv(signals_path, rows)
    write_performance(Path(args.performance), rows)
    print(f"Settled/voided now: {settled_now}; CLV rows refreshed: {clv_updated}; still pending checked: {still_pending}; total rows: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
