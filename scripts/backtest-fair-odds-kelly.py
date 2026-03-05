"""
Kelly-style stepped staking backtest on top of scripts/backtest-fair-odds.py core logic.

Uses the same historical data + model pipeline:
- tennis-data Pinnacle closing odds (atp-2024.xlsx, atp-2025.xlsx, optional 2026)
- OnCourt mapping/history/features
- same model probability computation as backtest-fair-odds.py

Adds:
- value-band stake sizing (0.25u..2u by default)
- confidence multipliers (high/medium/low/none)
- unit-based P&L and ROI by threshold and segment

Examples:
  python scripts/backtest-fair-odds-kelly.py
  python scripts/backtest-fair-odds-kelly.py --value-thresholds 5,10,15 --report-threshold 10
  python scripts/backtest-fair-odds-kelly.py --stake-bands "0:0.25,5:0.5,10:1,15:1.5,20:2" --confidence-mults "high:1,medium:0.5,low:0.25,none:0"
  python scripts/backtest-fair-odds-kelly.py --dry-run --limit-matches 500
"""

from __future__ import annotations

import argparse
import csv
import runpy
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
CORE_PATH = SCRIPTS_DIR / "backtest-fair-odds.py"


def _emit(lines: list[str], msg: str) -> None:
    print(msg)
    lines.append(msg)


def _resolve_path(p: str) -> Path:
    pp = Path(p)
    return pp if pp.is_absolute() else (ROOT / pp)


def _parse_percent_thresholds(spec: str) -> list[float]:
    out: list[float] = []
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            v = float(part)
        except ValueError:
            continue
        out.append(v)
    out = sorted(set(out))
    if not out:
        out = [2.0, 5.0, 10.0]
    return out


def _parse_stake_bands(spec: str) -> list[tuple[float, float]]:
    """
    Parse "0:0.25,5:0.5,10:1,15:1.5,20:2"
    Returns list of (lower_bound_value_pct, stake_units), sorted ascending.
    """
    bands: dict[float, float] = {}
    for chunk in str(spec).split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            raise ValueError(f"Bad stake band '{chunk}'. Expected lower_pct:units.")
        left, right = chunk.split(":", 1)
        try:
            lower_pct = float(left.strip())
            units = float(right.strip())
        except ValueError as e:
            raise ValueError(f"Bad stake band '{chunk}': {e}") from e
        if lower_pct < 0:
            raise ValueError(f"Stake band lower_pct must be >= 0, got {lower_pct}.")
        if units < 0:
            raise ValueError(f"Stake units must be >= 0, got {units}.")
        bands[lower_pct] = units

    if not bands:
        raise ValueError("No stake bands parsed.")
    return sorted(bands.items(), key=lambda x: x[0])


def _parse_confidence_mults(spec: str) -> dict[str, float]:
    """
    Parse "high:1,medium:0.5,low:0.25,none:0"
    """
    out = {"high": 1.0, "medium": 0.5, "low": 0.25, "none": 0.0}
    for chunk in str(spec).split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            raise ValueError(f"Bad confidence multiplier '{chunk}'. Expected confidence:mult.")
        left, right = chunk.split(":", 1)
        key = left.strip().lower()
        try:
            mult = float(right.strip())
        except ValueError as e:
            raise ValueError(f"Bad confidence multiplier '{chunk}': {e}") from e
        if mult < 0:
            raise ValueError(f"Confidence multiplier must be >= 0, got {mult}.")
        out[key] = mult
    return out


def _units_for_value_pct(value_pct: float, bands: list[tuple[float, float]]) -> float:
    units = 0.0
    for lower_pct, band_units in bands:
        if value_pct >= lower_pct:
            units = band_units
        else:
            break
    return units


def _value_band_label(value_pct: float, bands: list[tuple[float, float]]) -> str:
    for i, (lower_pct, _) in enumerate(bands):
        upper_pct = bands[i + 1][0] if i + 1 < len(bands) else None
        if value_pct < lower_pct:
            continue
        if upper_pct is None:
            return f">={lower_pct:g}%"
        if value_pct < upper_pct:
            return f"{lower_pct:g}-{upper_pct:g}%"
    return f"<{bands[0][0]:g}%"


def _summarize_bets(bets: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(bets)
    if n == 0:
        return {
            "bets": 0,
            "wins": 0,
            "losses": 0,
            "staked_units": 0.0,
            "profit_units": 0.0,
            "roi": 0.0,
            "hit_rate": 0.0,
            "avg_stake": 0.0,
            "avg_value_pct": 0.0,
            "max_losing_streak": 0,
            "max_losing_streak_units": 0.0,
            "max_drawdown_units": 0.0,
            "flat_profit_units": 0.0,
            "flat_roi": 0.0,
        }

    wins = sum(1 for b in bets if b["won"])
    losses = n - wins
    staked = sum(float(b["stake_units"]) for b in bets)
    profit = sum(float(b["pnl_units"]) for b in bets)
    roi = (profit / staked) if staked > 0 else 0.0
    hit = wins / n
    avg_stake = staked / n
    avg_value = mean(float(b["value_pct"]) for b in bets)

    # Losing streak (count + stake units)
    cur_ls = 0
    cur_ls_units = 0.0
    max_ls = 0
    max_ls_units = 0.0
    for b in bets:
        if b["won"]:
            cur_ls = 0
            cur_ls_units = 0.0
        else:
            cur_ls += 1
            cur_ls_units += float(b["stake_units"])
            if cur_ls > max_ls:
                max_ls = cur_ls
            if cur_ls_units > max_ls_units:
                max_ls_units = cur_ls_units

    # Max drawdown in units
    eq = 0.0
    peak = 0.0
    max_dd = 0.0
    for b in bets:
        eq += float(b["pnl_units"])
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd

    # Flat stake baseline on same picks (1u each)
    flat_profit = sum((float(b["odds"]) - 1.0) if b["won"] else -1.0 for b in bets)
    flat_roi = flat_profit / n if n > 0 else 0.0

    return {
        "bets": n,
        "wins": wins,
        "losses": losses,
        "staked_units": staked,
        "profit_units": profit,
        "roi": roi,
        "hit_rate": hit,
        "avg_stake": avg_stake,
        "avg_value_pct": avg_value,
        "max_losing_streak": max_ls,
        "max_losing_streak_units": max_ls_units,
        "max_drawdown_units": max_dd,
        "flat_profit_units": flat_profit,
        "flat_roi": flat_roi,
    }


def _segment_summaries(bets: list[dict[str, Any]], key: str) -> list[tuple[str, dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for b in bets:
        grouped[str(b.get(key) or "N/A")].append(b)

    out: list[tuple[str, dict[str, Any]]] = []
    for bucket, sample in sorted(grouped.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        out.append((bucket, _summarize_bets(sample)))
    return out


def _build_staked_bets(
    rows: list[dict[str, Any]],
    min_value_pct: float,
    stake_bands: list[tuple[float, float]],
    confidence_mults: dict[str, float],
    max_unit: float,
) -> tuple[list[dict[str, Any]], Counter]:
    bets: list[dict[str, Any]] = []
    skipped = Counter()

    for r in rows:
        value_w = float(r["value_w"])
        value_l = float(r["value_l"])

        if value_w >= value_l:
            side = "winner"
            edge = value_w
            odds = float(r["psw"])
            won = True
            bet_player = str(r["player1"])
            p_model_side = float(r["p_model_winner"])
            p_pin_side = float(r["p_pin_winner"])
        else:
            side = "loser"
            edge = value_l
            odds = float(r["psl"])
            won = False
            bet_player = str(r["player2"])
            p_model_side = 1.0 - float(r["p_model_winner"])
            p_pin_side = 1.0 - float(r["p_pin_winner"])

        edge_pct = edge * 100.0
        if edge_pct < min_value_pct:
            skipped["below_threshold"] += 1
            continue

        conf = str(r.get("confidence") or "none").lower()
        conf_mult = float(confidence_mults.get(conf, 0.0))
        if conf_mult <= 0.0:
            skipped[f"confidence_{conf}_filtered"] += 1
            continue

        base_units = _units_for_value_pct(edge_pct, stake_bands)
        if base_units <= 0.0:
            skipped["zero_band_units"] += 1
            continue

        stake_units = min(max_unit, base_units * conf_mult)
        if stake_units <= 0.0:
            skipped["zero_stake"] += 1
            continue

        pnl_units = (stake_units * (odds - 1.0)) if won else (-stake_units)

        bets.append(
            {
                "year": int(r["year"]),
                "date_ord": int(r["date_ord"]),
                "date": r["date"],
                "tournament": r["tournament"],
                "surface": r["surface"],
                "series": r["series"],
                "bet_side": side,
                "bet_player": bet_player,
                "confidence": conf,
                "value_pct": edge_pct,
                "value_band": _value_band_label(edge_pct, stake_bands),
                "base_units": base_units,
                "confidence_mult": conf_mult,
                "stake_units": stake_units,
                "odds": odds,
                "won": won,
                "pnl_units": pnl_units,
                "p_model_side": p_model_side,
                "p_pin_side": p_pin_side,
                "player1": r["player1"],
                "player2": r["player2"],
                "player1_id": r["player1_id"],
                "player2_id": r["player2_id"],
                "actual_winner": r["player1"],  # row is winner/loser oriented
            }
        )

    bets.sort(key=lambda x: (x["date_ord"], x["year"], x["tournament"], x["bet_player"]))
    running = 0.0
    for b in bets:
        running += float(b["pnl_units"])
        b["cum_pnl_units"] = running

    return bets, skipped


def _write_bets_csv(path: Path, bets: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "year",
        "date",
        "tournament",
        "surface",
        "series",
        "player1",
        "player2",
        "player1_id",
        "player2_id",
        "actual_winner",
        "bet_side",
        "bet_player",
        "confidence",
        "value_pct",
        "value_band",
        "base_units",
        "confidence_mult",
        "stake_units",
        "odds",
        "won",
        "pnl_units",
        "cum_pnl_units",
        "p_model_side",
        "p_pin_side",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in bets:
            out = dict(row)
            out["won"] = 1 if row["won"] else 0
            w.writerow({k: out.get(k) for k in fields})


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backtest fair-odds model with Kelly-style stepped staking (value/confidence weighted)."
    )
    parser.add_argument(
        "--files",
        nargs="*",
        default=None,
        help="Backtest XLSX files (default: data/backtest/atp-2024.xlsx data/backtest/atp-2025.xlsx)",
    )
    parser.add_argument("--include-2026", action="store_true", help="Also include data/backtest/atp-2026.xlsx")
    parser.add_argument("--limit-matches", type=int, default=None, help="Process first N matches after sorting (debug)")
    parser.add_argument("--dry-run", action="store_true", help="Do not write CSV/summary files.")
    parser.add_argument("--show-unmatched", action="store_true", help="Print unmatched tennis-data names.")
    parser.add_argument("--unmatched-limit", type=int, default=40)

    parser.add_argument(
        "--value-thresholds",
        default="2,5,10",
        help="Value%% entry thresholds to evaluate (comma-separated, percent).",
    )
    parser.add_argument(
        "--report-threshold",
        type=float,
        default=5.0,
        help="Value%% threshold used for detailed segmentation + CSV export.",
    )
    parser.add_argument(
        "--stake-bands",
        default="0:0.25,5:0.5,10:1,15:1.5,20:2",
        help="Stake schedule lower%%:units (comma-separated). Example: 0:0.25,5:0.5,10:1,15:1.5,20:2",
    )
    parser.add_argument(
        "--confidence-mults",
        default="high:1,medium:0.5,low:0.25,none:0",
        help="Confidence multipliers confidence:mult (comma-separated).",
    )
    parser.add_argument("--max-unit", type=float, default=2.0, help="Hard cap on stake units per bet.")

    parser.add_argument(
        "--out-csv",
        default="data/backtest/backtest-kelly-bets.csv",
        help="Output CSV for bets at --report-threshold",
    )
    parser.add_argument(
        "--out-summary",
        default="data/backtest/backtest-kelly-summary.txt",
        help="Output text summary path",
    )

    args = parser.parse_args()

    # Load core namespace from existing backtest script.
    core = runpy.run_path(str(CORE_PATH), run_name="backtest_fair_odds_core")

    # Pull functions/classes from core script (same pipeline).
    _load_backtest_matches = core["_load_backtest_matches"]
    _load_oncourt_players = core["_load_oncourt_players"]
    _load_lefties = core["_load_lefties"]
    _load_tour_info = core["_load_tour_info"]
    _load_player_popularity = core["_load_player_popularity"]
    _build_tennis_data_name_map = core["_build_tennis_data_name_map"]
    _load_stat_map = core["_load_stat_map"]
    _history_from_oncourt = core["_history_from_oncourt"]
    _compute_match_probability = core["_compute_match_probability"]
    _safe_prob = core["_safe_prob"]
    _log_loss = core["_log_loss"]
    _summarize_calibration = core["_summarize_calibration"]
    ModelState = core["ModelState"]
    UNKNOWN_PLAYER_IDS = set(core["UNKNOWN_PLAYER_IDS"])

    thresholds = _parse_percent_thresholds(args.value_thresholds)
    if args.report_threshold not in thresholds:
        thresholds.append(float(args.report_threshold))
        thresholds = sorted(set(thresholds))

    stake_bands = _parse_stake_bands(args.stake_bands)
    confidence_mults = _parse_confidence_mults(args.confidence_mults)

    log_lines: list[str] = []
    _emit(log_lines, "Loading tennis-data files...")

    backtest_dir = ROOT / "data" / "backtest"
    if args.files:
        xlsx_paths = [_resolve_path(p) for p in args.files]
    else:
        xlsx_paths = [backtest_dir / "atp-2024.xlsx", backtest_dir / "atp-2025.xlsx"]
    if args.include_2026:
        p2026 = backtest_dir / "atp-2026.xlsx"
        if p2026 not in xlsx_paths:
            xlsx_paths.append(p2026)

    matches, skip_from_xlsx, short_names = _load_backtest_matches(xlsx_paths)
    if args.limit_matches:
        matches = matches[: args.limit_matches]
    if not matches:
        _emit(log_lines, "No usable matches loaded.")
        return

    _emit(log_lines, f"Backtest matches loaded: {len(matches):,}")
    if skip_from_xlsx:
        _emit(log_lines, f"  Skipped while reading XLSX: {dict(skip_from_xlsx)}")

    data_oncourt = ROOT / "data" / "oncourt"
    players_path = data_oncourt / "players_atp.csv"
    games_path = data_oncourt / "games_atp.csv"
    stat_path = data_oncourt / "stat_atp.csv"
    tours_path = data_oncourt / "tours_atp.csv"
    courts_path = data_oncourt / "courts.csv"
    categories_path = data_oncourt / "categories_atp.csv"

    for p in [players_path, games_path, stat_path, tours_path, courts_path]:
        if not p.exists():
            raise FileNotFoundError(f"Missing required OnCourt file: {p}")

    _emit(log_lines, "Loading OnCourt players/tours...")
    oncourt_players = _load_oncourt_players(players_path)
    players_by_id = {int(r["id"]): r for r in oncourt_players}
    birthdate_by_player = {int(r["id"]): r.get("birthdate") for r in oncourt_players}
    lefties = _load_lefties(categories_path, set(players_by_id.keys()))
    tours = _load_tour_info(tours_path, courts_path)
    popularity_by_pid = _load_player_popularity(games_path, players_by_id, tours)

    _emit(log_lines, "Mapping tennis-data names to OnCourt IDs...")
    name_map, map_report = _build_tennis_data_name_map(
        short_names,
        oncourt_players,
        popularity_by_pid=popularity_by_pid,
    )

    _emit(log_lines, f"  OnCourt players: {len(oncourt_players):,}")
    _emit(log_lines, f"  Lefties from categories_atp.csv: {len(lefties):,}")
    _emit(log_lines, f"  OnCourt index players (singles only): {map_report['oncourt_index_players']:,}")
    _emit(log_lines, f"  Popularity rows: {len(popularity_by_pid):,}")
    _emit(log_lines, f"  Tennis-data short names: {map_report['source_names']:,}")
    _emit(log_lines, f"  Mapped short names: {map_report['mapped_names']:,}")
    _emit(log_lines, f"  Unmapped short names: {map_report['unmapped_names']:,}")
    _emit(log_lines, f"  Mapping methods: {map_report['method_counts']}")
    if args.show_unmatched and map_report["unmapped_examples"]:
        _emit(log_lines, "  Unmapped examples:")
        for nm in map_report["unmapped_examples"][: args.unmatched_limit]:
            _emit(log_lines, f"    - {nm}")

    skipped = Counter()
    filtered_matches: list[Any] = []
    for m in matches:
        wid = name_map.get(m.winner_name_short)
        lid = name_map.get(m.loser_name_short)
        if wid is None:
            skipped["unmapped_winner"] += 1
            continue
        if lid is None:
            skipped["unmapped_loser"] += 1
            continue
        if wid == lid:
            skipped["same_player_after_mapping"] += 1
            continue
        if wid in UNKNOWN_PLAYER_IDS or lid in UNKNOWN_PLAYER_IDS:
            skipped["unknown_player_id"] += 1
            continue
        if "/" in (players_by_id.get(wid, {}).get("name") or "") or "/" in (players_by_id.get(lid, {}).get("name") or ""):
            skipped["mapped_to_doubles_team"] += 1
            continue
        m.winner_id = wid
        m.loser_id = lid
        filtered_matches.append(m)

    if not filtered_matches:
        _emit(log_lines, "No matches left after ID mapping.")
        return

    _emit(log_lines, f"Matches after ID mapping: {len(filtered_matches):,}")
    if skipped:
        _emit(log_lines, f"  Skipped after mapping: {dict(skipped)}")

    _emit(log_lines, "Loading historical OnCourt stat/games...")
    stat_map = _load_stat_map(stat_path)
    max_date_ord = max(m.date_ord for m in filtered_matches)
    history_events, history_skip = _history_from_oncourt(
        games_path,
        players_by_id,
        tours,
        stat_map,
        max_date_ord=max_date_ord,
    )
    _emit(log_lines, f"  History events loaded: {len(history_events):,}")
    if history_skip:
        _emit(log_lines, f"  History skipped: {dict(history_skip)}")

    _emit(log_lines, "Running strict chronological backtest (no future leakage)...")
    state = ModelState()
    hist_idx = 0
    results: list[dict[str, Any]] = []
    confidence_counts = Counter()

    for m in filtered_matches:
        while hist_idx < len(history_events) and history_events[hist_idx].date_ord < m.date_ord:
            state.update(history_events[hist_idx], lefties)
            hist_idx += 1

        p_winner, confidence, debug = _compute_match_probability(m, state, birthdate_by_player, lefties)
        confidence_counts[confidence] += 1

        our_odds_w = 1.0 / _safe_prob(p_winner)
        our_odds_l = 1.0 / _safe_prob(1.0 - p_winner)

        p_pin_w_raw = 1.0 / float(m.psw)
        p_pin_l_raw = 1.0 / float(m.psl)
        pin_sum = p_pin_w_raw + p_pin_l_raw
        p_pin_w = p_pin_w_raw / pin_sum if pin_sum > 0 else 0.5

        value_w = (float(m.psw) / our_odds_w) - 1.0
        value_l = (float(m.psl) / our_odds_l) - 1.0

        results.append(
            {
                "year": int(m.year),
                "date_ord": int(m.date_ord),
                "date": m.date_iso,
                "tournament": m.tournament,
                "surface": m.surface,
                "round": m.round_name,
                "series": m.series,
                "player1": players_by_id[m.winner_id]["name"],
                "player2": players_by_id[m.loser_id]["name"],
                "player1_id": m.winner_id,
                "player2_id": m.loser_id,
                "p_model_winner": float(p_winner),
                "p_pin_winner": float(p_pin_w),
                "psw": float(m.psw),
                "psl": float(m.psl),
                "value_w": float(value_w),
                "value_l": float(value_l),
                "confidence": confidence,
                "p_raw": float(debug.get("p_raw") or p_winner),
                "fav_prob": max(float(p_winner), 1.0 - float(p_winner)),
                "fav_won": 1 if float(p_winner) >= 0.5 else 0,
            }
        )

    if not results:
        _emit(log_lines, "No model results produced.")
        return

    _emit(log_lines, f"Completed predictions: {len(results):,}")
    _emit(log_lines, f"  Confidence: {dict(confidence_counts)}")

    ll_ours = mean(_log_loss(r["p_model_winner"]) for r in results)
    ll_pin = mean(_log_loss(r["p_pin_winner"]) for r in results)
    brier_ours = mean((1.0 - r["p_model_winner"]) ** 2 for r in results)
    brier_pin = mean((1.0 - r["p_pin_winner"]) ** 2 for r in results)
    acc_ours = mean(1.0 if r["p_model_winner"] >= 0.5 else 0.0 for r in results)
    acc_pin = mean(1.0 if r["p_pin_winner"] >= 0.5 else 0.0 for r in results)

    _emit(log_lines, "\n=== Model vs Pinnacle (No-Vig) ===")
    _emit(log_lines, f"Matches evaluated: {len(results):,}")
    _emit(log_lines, f"Log loss: ours={ll_ours:.5f} | pinnacle={ll_pin:.5f} | delta={ll_ours - ll_pin:+.5f}")
    _emit(log_lines, f"Brier score: ours={brier_ours:.5f} | pinnacle={brier_pin:.5f} | delta={brier_ours - brier_pin:+.5f}")
    _emit(log_lines, f"Accuracy (favorite wins): ours={acc_ours:.3%} | pinnacle={acc_pin:.3%}")

    _emit(log_lines, "\n=== Calibration (favorite probability bins) ===")
    for row in _summarize_calibration(results):
        if row["n"] == 0:
            _emit(log_lines, f"{row['bin']:>8}  n=0")
        else:
            _emit(
                log_lines,
                f"{row['bin']:>8}  n={row['n']:4d}  pred={row['pred']:.3f}  actual={row['actual']:.3f}  gap={row['gap']:+.3f}",
            )

    _emit(log_lines, "\n=== Kelly-Style Stake Policy ===")
    _emit(log_lines, f"Stake bands (value%% -> units): {stake_bands}")
    _emit(log_lines, f"Confidence multipliers: {confidence_mults}")
    _emit(log_lines, f"Stake cap per bet: {args.max_unit:.2f}u")

    threshold_results: dict[float, dict[str, Any]] = {}
    _emit(log_lines, "\n=== Unit P&L by Value% Threshold ===")
    for th in thresholds:
        bets, skipped_bets = _build_staked_bets(
            results,
            min_value_pct=float(th),
            stake_bands=stake_bands,
            confidence_mults=confidence_mults,
            max_unit=float(args.max_unit),
        )
        summary = _summarize_bets(bets)
        threshold_results[float(th)] = {
            "bets": bets,
            "skipped": skipped_bets,
            "summary": summary,
        }
        _emit(
            log_lines,
            (
                f"Value>={th:.1f}%  bets={summary['bets']:4d}  wins={summary['wins']:4d}  "
                f"staked={summary['staked_units']:.2f}u  P/L={summary['profit_units']:+.2f}u  "
                f"ROI={summary['roi']:+.3%}  hit={summary['hit_rate']:.3%}  "
                f"flatROI(same picks)={summary['flat_roi']:+.3%}  maxDD={summary['max_drawdown_units']:.2f}u"
            ),
        )

    report_threshold = float(args.report_threshold)
    report_pack = threshold_results.get(report_threshold)
    if report_pack is None:
        report_threshold = thresholds[0]
        report_pack = threshold_results[report_threshold]

    report_bets = report_pack["bets"]
    report_summary = report_pack["summary"]

    _emit(log_lines, f"\n=== Detailed Segmentation (Value>={report_threshold:.1f}%) ===")
    _emit(
        log_lines,
        (
            f"Overall: bets={report_summary['bets']}  staked={report_summary['staked_units']:.2f}u  "
            f"P/L={report_summary['profit_units']:+.2f}u  ROI={report_summary['roi']:+.3%}  "
            f"hit={report_summary['hit_rate']:.3%}  avgStake={report_summary['avg_stake']:.3f}u  "
            f"avgEdge={report_summary['avg_value_pct']:.2f}%  "
            f"maxLS={report_summary['max_losing_streak']} ({report_summary['max_losing_streak_units']:.2f}u)  "
            f"maxDD={report_summary['max_drawdown_units']:.2f}u"
        ),
    )

    def print_segment(title: str, key: str) -> None:
        _emit(log_lines, f"\n{title}")
        rows = _segment_summaries(report_bets, key)
        if not rows:
            _emit(log_lines, "  (no bets)")
            return
        for bucket, s in rows:
            _emit(
                log_lines,
                (
                    f"{bucket:>16}  bets={s['bets']:4d}  staked={s['staked_units']:.2f}u  "
                    f"P/L={s['profit_units']:+.2f}u  ROI={s['roi']:+.3%}  "
                    f"hit={s['hit_rate']:.3%}  avgStake={s['avg_stake']:.3f}u"
                ),
            )

    print_segment("By Value Band", "value_band")
    print_segment("By Confidence", "confidence")
    print_segment("By Surface", "surface")
    print_segment("By Series", "series")
    print_segment("By Year", "year")

    if args.dry_run:
        _emit(log_lines, "\nDry run: skipped CSV/summary writes.")
        return

    out_csv_path = _resolve_path(args.out_csv)
    out_summary_path = _resolve_path(args.out_summary)

    _write_bets_csv(out_csv_path, report_bets)
    _emit(log_lines, f"\nWrote bets CSV ({len(report_bets):,} rows) -> {out_csv_path}")

    out_summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")
    _emit(log_lines, f"Wrote summary -> {out_summary_path}")


if __name__ == "__main__":
    main()
