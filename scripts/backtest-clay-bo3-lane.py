"""
Backtest and diagnostics for the internal clay_bo3 tennis lane.

The historical backtest-results-YYYY.csv files are match-winner only. This
script therefore scores the clay_bo3 ML lane across 2022-2025, then appends
dog-handicap diagnostics from the available spread archive/training data.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Callable, Iterable


ROOT = Path(__file__).resolve().parents[1]
BACKTEST_DIR = ROOT / "data" / "backtest"

DEFAULT_ML_FILES = [BACKTEST_DIR / f"backtest-results-{year}.csv" for year in (2022, 2023, 2024, 2025)]
DEFAULT_SPREAD_ARCHIVE = BACKTEST_DIR / "strict-signals-spreadv1-archive.csv"
DEFAULT_SPREAD_DATASET = BACKTEST_DIR / "spread-v1-training-dataset.csv"
DEFAULT_OUT_TXT = BACKTEST_DIR / "clay-bo3-backtest-2022-2025.txt"
DEFAULT_OUT_CSV = BACKTEST_DIR / "clay-bo3-backtest-2022-2025.csv"
DEFAULT_OUT_PICKS = BACKTEST_DIR / "clay-bo3-backtest-picks-2022-2025.csv"

ALLOWED_SERIES = {"ATP250", "ATP500", "Masters 1000", "Masters Cup"}
ALLOWED_CONFIDENCE = {"high"}
ML_MIN_EDGE_PCT = 5.0
ML_MAX_EDGE_PCT = 13.0
DOG_HC_MIN_EDGE_PCT = 6.0
DOG_HC_MAX_EDGE_PCT = 25.0
MODEL_FAV_ODDS_MIN = 1.25
MISPRICE_MODEL_MARKET_FAV_GAP_MAX = 0.10
MISPRICE_MODEL_MARKET_FAV_SIDE_FLIP_BUFFER = 0.03
HEAVY_FAV_DOG_GUARD_MIN_FAV_PROB = 0.74


@dataclass(frozen=True)
class Pick:
    lane: str
    source: str
    year: str
    date_iso: str
    tournament: str
    surface: str
    series: str
    confidence: str
    market: str
    side: str
    player1: str
    player2: str
    selection: str
    edge_pct: float
    odds: float
    result: str
    pnl: float
    staked: float
    segment: str


def parse_float(value: object, default: float | None = None) -> float | None:
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def parse_bool(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def clean(value: object) -> str:
    return str(value or "").strip()


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def selected_player_from_ml_row(row: dict[str, str]) -> str:
    actual_winner = clean(row.get("actual_winner"))
    player1 = clean(row.get("player1"))
    player2 = clean(row.get("player2"))
    if clean(row.get("bet_side")) == "winner":
        return actual_winner
    if actual_winner == player1:
        return player2
    if actual_winner == player2:
        return player1
    return ""


def selected_odds_from_ml_row(row: dict[str, str]) -> float | None:
    if clean(row.get("bet_side")) == "winner":
        return parse_float(row.get("pinnacle_odds"))
    return parse_float(row.get("pinnacle_odds_loser"))


def opposite_name(row: dict[str, str], name: str) -> str:
    player1 = clean(row.get("player1"))
    player2 = clean(row.get("player2"))
    if name == player1:
        return player2
    if name == player2:
        return player1
    return ""


def ml_skip_reason(row: dict[str, str]) -> str | None:
    if clean(row.get("surface")) != "Clay":
        return "surface"
    if clean(row.get("series")) not in ALLOWED_SERIES:
        return "series"
    if clean(row.get("confidence")).lower() not in ALLOWED_CONFIDENCE:
        return "confidence"
    if parse_bool(row.get("policy_excluded")):
        return "policy_excluded"
    if clean(row.get("bet_result")).lower() not in {"win", "loss"}:
        return "unsettled"

    edge = parse_float(row.get("value_pct"))
    if edge is None:
        return "missing_edge"
    if edge < ML_MIN_EDGE_PCT:
        return "edge_below_floor"
    if edge > ML_MAX_EDGE_PCT:
        return "edge_above_cap"

    odds = selected_odds_from_ml_row(row)
    if odds is None or odds <= 1.0:
        return "missing_odds"

    model_favorite_prob = parse_float(row.get("model_favorite_prob"))
    if model_favorite_prob is None:
        return "missing_model_fav"
    if (1.0 / max(model_favorite_prob, 1e-9)) < MODEL_FAV_ODDS_MIN:
        return "model_fav_too_short"

    pin_odds_winner = parse_float(row.get("pinnacle_odds"))
    pin_odds_loser = parse_float(row.get("pinnacle_odds_loser"))
    if pin_odds_winner is None or pin_odds_loser is None:
        return "missing_pin_pair"
    if min(pin_odds_winner, pin_odds_loser) < MODEL_FAV_ODDS_MIN:
        return "pin_fav_too_short"

    pin_prob_winner = parse_float(row.get("pinnacle_prob_novig"))
    if pin_prob_winner is not None:
        pin_favorite_prob = max(pin_prob_winner, 1.0 - pin_prob_winner)
        if abs(model_favorite_prob - pin_favorite_prob) > MISPRICE_MODEL_MARKET_FAV_GAP_MAX:
            return "model_market_gap"
        actual_winner = clean(row.get("actual_winner"))
        model_favorite = clean(row.get("model_favorite"))
        model_favorite_side = "winner" if model_favorite == actual_winner else "loser"
        pin_favorite_side = "winner" if pin_prob_winner >= 0.5 else "loser"
        if (
            model_favorite_side != pin_favorite_side
            and abs(pin_prob_winner - 0.5) >= MISPRICE_MODEL_MARKET_FAV_SIDE_FLIP_BUFFER
            and abs(model_favorite_prob - 0.5) >= MISPRICE_MODEL_MARKET_FAV_SIDE_FLIP_BUFFER
        ):
            return "model_market_side_flip"

    selection = selected_player_from_ml_row(row)
    model_favorite = clean(row.get("model_favorite"))
    if (
        selection
        and model_favorite
        and selection != model_favorite
        and model_favorite_prob >= HEAVY_FAV_DOG_GUARD_MIN_FAV_PROB
    ):
        return "heavy_favorite_dog"

    return None


def score_ml_rows(rows: Iterable[dict[str, str]]) -> list[Pick]:
    picks: list[Pick] = []
    for row in rows:
        if ml_skip_reason(row) is not None:
            continue
        odds = selected_odds_from_ml_row(row)
        edge = parse_float(row.get("value_pct"))
        if odds is None or edge is None:
            continue
        result = clean(row.get("bet_result")).lower()
        pnl = (odds - 1.0) if result == "win" else -1.0
        selection = selected_player_from_ml_row(row)
        model_favorite = clean(row.get("model_favorite"))
        side = "favorite_ml" if selection and selection == model_favorite else "dog_ml"
        picks.append(
            Pick(
                lane="clay_bo3",
                source="historical_ml_backtest",
                year=clean(row.get("date"))[:4],
                date_iso=clean(row.get("date")),
                tournament=clean(row.get("tournament")),
                surface=clean(row.get("surface")),
                series=clean(row.get("series")),
                confidence=clean(row.get("confidence")).lower(),
                market="ml",
                side=side,
                player1=clean(row.get("player1")),
                player2=clean(row.get("player2")),
                selection=selection,
                edge_pct=float(edge),
                odds=float(odds),
                result=result,
                pnl=float(pnl),
                staked=1.0,
                segment=f"{clean(row.get('series'))}|{side}",
            )
        )
    return picks


def spread_archive_orientation(row: dict[str, str]) -> str:
    side = clean(row.get("side"))
    if side.endswith("+"):
        return "dog_hc"
    if side.endswith("-"):
        return "favorite_hc"
    line = parse_float(row.get("spread_line"))
    if line is None:
        return "unknown"
    if line > 0:
        return "dog_hc"
    if line < 0:
        return "favorite_hc"
    return "unknown"


def score_spread_archive(rows: Iterable[dict[str, str]]) -> list[Pick]:
    picks: list[Pick] = []
    for row in rows:
        if clean(row.get("bet_type")).lower() != "spread":
            continue
        if clean(row.get("settlement_status")).lower() != "settled":
            continue
        if clean(row.get("surface")) != "Clay":
            continue
        if clean(row.get("series")) not in ALLOWED_SERIES:
            continue
        if clean(row.get("confidence")).lower() not in ALLOWED_CONFIDENCE:
            continue
        if spread_archive_orientation(row) != "dog_hc":
            continue
        edge = parse_float(row.get("value_pct"))
        odds = parse_float(row.get("spread_odds"))
        if edge is None or odds is None or odds <= 1.0:
            continue
        if not (DOG_HC_MIN_EDGE_PCT <= edge <= DOG_HC_MAX_EDGE_PCT):
            continue
        outcome = clean(row.get("bet_outcome") or row.get("result")).lower()
        if outcome in {"push", "void"}:
            pnl = 0.0
            result = "push"
        elif outcome in {"win", "won"} or parse_bool(row.get("won_bet")):
            pnl = odds - 1.0
            result = "win"
        elif outcome in {"loss", "lost"} or clean(row.get("won_bet")) == "0":
            pnl = -1.0
            result = "loss"
        else:
            continue
        picks.append(
            Pick(
                lane="clay_bo3",
                source="spread_archive_live_proxy",
                year=clean(row.get("date"))[:4],
                date_iso=clean(row.get("date")),
                tournament="",
                surface=clean(row.get("surface")),
                series=clean(row.get("series")),
                confidence=clean(row.get("confidence")).lower(),
                market="dog_hc",
                side=clean(row.get("side")),
                player1=clean(row.get("player1")),
                player2=clean(row.get("player2")),
                selection=clean(row.get("side")),
                edge_pct=float(edge),
                odds=float(odds),
                result=result,
                pnl=float(pnl),
                staked=1.0,
                segment=f"{clean(row.get('series'))}|dog_hc",
            )
        )
    return picks


def score_spread_dataset(rows: Iterable[dict[str, str]]) -> list[Pick]:
    picks: list[Pick] = []
    for row in rows:
        if clean(row.get("surface")) != "Clay":
            continue
        p1_prob = parse_float(row.get("p1_match_prob"))
        base_prob = parse_float(row.get("base_prob"))
        line = parse_float(row.get("spread_line"))
        cover = parse_float(row.get("cover_result"))
        if p1_prob is None or base_prob is None or line is None or cover is None:
            continue

        if p1_prob < 0.5 and line > 0:
            side = "P1+"
            odds = parse_float(row.get("spread_odds1"))
            edge = (base_prob * odds - 1.0) * 100.0 if odds and odds > 1.0 else None
            won = cover >= 0.5
            selection = clean(row.get("player1"))
        elif p1_prob > 0.5 and line < 0:
            side = "P2+"
            odds = parse_float(row.get("spread_odds2"))
            p2_cover_prob = 1.0 - base_prob
            edge = (p2_cover_prob * odds - 1.0) * 100.0 if odds and odds > 1.0 else None
            won = cover < 0.5
            selection = clean(row.get("player2"))
        else:
            continue

        if edge is None or odds is None or odds <= 1.0:
            continue
        if not (DOG_HC_MIN_EDGE_PCT <= edge <= DOG_HC_MAX_EDGE_PCT):
            continue
        result = "win" if won else "loss"
        picks.append(
            Pick(
                lane="clay_bo3",
                source="spread_training_dataset_proxy",
                year=clean(row.get("year")) or clean(row.get("date_iso"))[:4],
                date_iso=clean(row.get("date_iso")),
                tournament="",
                surface=clean(row.get("surface")),
                series=clean(row.get("series")) or "unknown",
                confidence="unknown",
                market="dog_hc",
                side=side,
                player1=clean(row.get("player1")),
                player2=clean(row.get("player2")),
                selection=selection,
                edge_pct=float(edge),
                odds=float(odds),
                result=result,
                pnl=(float(odds) - 1.0) if won else -1.0,
                staked=1.0,
                segment="spread_training_dataset|dog_hc",
            )
        )
    return picks


def summary(picks: Iterable[Pick]) -> dict[str, float]:
    selected = list(picks)
    n = len(selected)
    wins = sum(1 for pick in selected if pick.result == "win")
    losses = sum(1 for pick in selected if pick.result == "loss")
    pushes = sum(1 for pick in selected if pick.result == "push")
    pnl = sum(pick.pnl for pick in selected)
    staked = sum(pick.staked for pick in selected)
    edges = [pick.edge_pct for pick in selected]
    odds = [pick.odds for pick in selected]
    return {
        "bets": float(n),
        "wins": float(wins),
        "losses": float(losses),
        "pushes": float(pushes),
        "pnl": pnl,
        "staked": staked,
        "roi_pct": (pnl / staked * 100.0) if staked else 0.0,
        "win_rate_pct": (wins / max(1, wins + losses) * 100.0) if n else 0.0,
        "avg_edge_pct": mean(edges) if edges else 0.0,
        "median_edge_pct": median(edges) if edges else 0.0,
        "avg_odds": mean(odds) if odds else 0.0,
    }


def group_by(picks: Iterable[Pick], key_fn: Callable[[Pick], str]) -> list[tuple[str, list[Pick]]]:
    buckets: dict[str, list[Pick]] = defaultdict(list)
    for pick in picks:
        buckets[key_fn(pick)].append(pick)
    return sorted(buckets.items(), key=lambda item: item[0])


def edge_bucket(edge: float) -> str:
    if edge < 7:
        return "05-07" if edge < 7 else "07-09"
    if edge < 9:
        return "07-09"
    if edge < 11:
        return "09-11"
    if edge <= 13:
        return "11-13"
    if edge < 15:
        return "13-15"
    if edge < 20:
        return "15-20"
    return "20-25"


def bootstrap_roi_ci(picks: list[Pick], *, runs: int = 1000, seed: int = 1337) -> tuple[float, float] | None:
    if not picks:
        return None
    rng = random.Random(seed)
    rois: list[float] = []
    n = len(picks)
    for _ in range(runs):
        sample = [picks[rng.randrange(n)] for _ in range(n)]
        staked = sum(pick.staked for pick in sample)
        pnl = sum(pick.pnl for pick in sample)
        rois.append((pnl / staked * 100.0) if staked else 0.0)
    rois.sort()
    low_idx = max(0, math.floor(0.025 * (runs - 1)))
    high_idx = min(runs - 1, math.ceil(0.975 * (runs - 1)))
    return rois[low_idx], rois[high_idx]


def max_drawdown_units(picks: list[Pick]) -> float:
    ordered = sorted(picks, key=lambda pick: (pick.date_iso, pick.player1, pick.player2, pick.market))
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for pick in ordered:
        equity += pick.pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def threshold_sweep(picks: list[Pick]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for lo in (5, 6, 7, 8, 9, 10, 11, 12):
        for hi in (lo + 1, lo + 2, lo + 3, 13):
            if hi > 13:
                continue
            bucket = [pick for pick in picks if lo <= pick.edge_pct <= hi]
            if len(bucket) < 40:
                continue
            stats = summary(bucket)
            by_year = {
                year: summary(year_picks)["roi_pct"]
                for year, year_picks in group_by(bucket, lambda pick: pick.year)
            }
            rows.append(
                {
                    "lo": lo,
                    "hi": hi,
                    "bets": len(bucket),
                    "roi_pct": stats["roi_pct"],
                    "min_year_roi_pct": min(by_year.values()) if by_year else 0.0,
                    "roi_2025_pct": by_year.get("2025", 0.0),
                    "by_year": by_year,
                }
            )
    rows.sort(key=lambda row: (float(row["min_year_roi_pct"]), float(row["roi_2025_pct"]), float(row["roi_pct"])), reverse=True)
    return rows


def fmt_stats(stats: dict[str, float]) -> str:
    return (
        f"{int(stats['bets'])} bets, {int(stats['wins'])}W/"
        f"{int(stats['losses'])}L/{int(stats['pushes'])}P, "
        f"PnL {stats['pnl']:+.2f}u on {stats['staked']:.1f}u, "
        f"ROI {stats['roi_pct']:+.1f}%, WR {stats['win_rate_pct']:.1f}%, "
        f"avg edge {stats['avg_edge_pct']:.1f}%, avg odds {stats['avg_odds']:.3f}"
    )


def append_group_lines(lines: list[str], title: str, picks: list[Pick], key_fn: Callable[[Pick], str], *, min_n: int = 1) -> None:
    lines.append(title)
    rows = []
    for key, bucket in group_by(picks, key_fn):
        if len(bucket) < min_n:
            continue
        rows.append((key, summary(bucket)))
    rows.sort(key=lambda item: (-int(item[1]["bets"]), item[0]))
    if not rows:
        lines.append("- none")
    for key, stats in rows:
        lines.append(f"- {key}: {fmt_stats(stats)}")
    lines.append("")


def build_summary_rows(label: str, picks: list[Pick], key_fn: Callable[[Pick], str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for key, bucket in group_by(picks, key_fn):
        stats = summary(bucket)
        ci = bootstrap_roi_ci(bucket, runs=500) if len(bucket) >= 5 else None
        rows.append(
            {
                "section": label,
                "bucket": key,
                "bets": int(stats["bets"]),
                "wins": int(stats["wins"]),
                "losses": int(stats["losses"]),
                "pushes": int(stats["pushes"]),
                "pnl": round(stats["pnl"], 4),
                "staked": round(stats["staked"], 4),
                "roi_pct": round(stats["roi_pct"], 4),
                "win_rate_pct": round(stats["win_rate_pct"], 4),
                "avg_edge_pct": round(stats["avg_edge_pct"], 4),
                "median_edge_pct": round(stats["median_edge_pct"], 4),
                "avg_odds": round(stats["avg_odds"], 4),
                "bootstrap_roi_low_pct": round(ci[0], 4) if ci else "",
                "bootstrap_roi_high_pct": round(ci[1], 4) if ci else "",
                "max_drawdown_units": round(max_drawdown_units(bucket), 4),
            }
        )
    return rows


def write_summary_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "section",
        "bucket",
        "bets",
        "wins",
        "losses",
        "pushes",
        "pnl",
        "staked",
        "roi_pct",
        "win_rate_pct",
        "avg_edge_pct",
        "median_edge_pct",
        "avg_odds",
        "bootstrap_roi_low_pct",
        "bootstrap_roi_high_pct",
        "max_drawdown_units",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_picks_csv(path: Path, picks: list[Pick]) -> None:
    fieldnames = list(Pick.__dataclass_fields__.keys())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for pick in picks:
            writer.writerow({field: getattr(pick, field) for field in fieldnames})


def report_lines(ml_picks: list[Pick], spread_archive_picks: list[Pick], spread_dataset_picks: list[Pick], rows_loaded: int) -> list[str]:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "Clay bo3 lane backtest",
        f"Generated UTC: {generated}",
        f"ML rows loaded from historical files: {rows_loaded:,}",
        "",
        "Scope",
        f"- ML: ATP clay bo3, series in {', '.join(sorted(ALLOWED_SERIES))}, confidence=high, edge {ML_MIN_EDGE_PCT:.0f}-{ML_MAX_EDGE_PCT:.0f}%, 1u flat stake.",
        f"- Dog HC diagnostic: clay dog-handicap edge {DOG_HC_MIN_EDGE_PCT:.0f}-{DOG_HC_MAX_EDGE_PCT:.0f}%, 1u flat stake.",
        "- Historical caveat: backtest-results-YYYY.csv files do not contain spread lines/odds, so dog HC cannot be scored over 2022-2025 from those files.",
        "- CLV caveat: historical ML CSVs contain one Pinnacle price snapshot, not open/close pairs. CLV remains a live archive audit metric.",
        "",
        "ML historical verdict",
        f"- Overall: {fmt_stats(summary(ml_picks))}",
    ]
    ci = bootstrap_roi_ci(ml_picks)
    if ci:
        lines.append(f"- Bootstrap ROI 95% CI: {ci[0]:+.1f}% to {ci[1]:+.1f}%")
    lines.append(f"- Max drawdown: {max_drawdown_units(ml_picks):.2f}u")
    lines.append("")
    append_group_lines(lines, "ML by year", ml_picks, lambda pick: pick.year)
    append_group_lines(lines, "ML by series", ml_picks, lambda pick: pick.series)
    append_group_lines(lines, "ML by favorite/dog", ml_picks, lambda pick: pick.side)
    append_group_lines(lines, "ML by edge bucket", ml_picks, lambda pick: edge_bucket(pick.edge_pct))

    sweep = threshold_sweep(ml_picks)
    lines.append("ML threshold sweep")
    lines.append("- Tested simple edge bands inside 5-13% with at least 40 bets.")
    if not sweep:
        lines.append("- no sweep rows")
    else:
        for row in sweep[:8]:
            by_year = ", ".join(f"{year}:{roi:+.1f}%" for year, roi in sorted(dict(row["by_year"]).items()))
            lines.append(
                f"- edge {int(row['lo'])}-{int(row['hi'])}%: "
                f"{int(row['bets'])} bets, ROI {float(row['roi_pct']):+.1f}%, "
                f"min-year {float(row['min_year_roi_pct']):+.1f}%, 2025 {float(row['roi_2025_pct']):+.1f}% "
                f"({by_year})"
            )
    lines.append("")

    lines.extend(
        [
            "Dog HC diagnostics",
            f"- Settled spread archive proxy: {fmt_stats(summary(spread_archive_picks))}",
            f"- Spread training dataset proxy: {fmt_stats(summary(spread_dataset_picks))}",
            "",
            "Dog HC interpretation",
            "- Treat these as diagnostics, not a 2022-2025 backtest, because historical spread market data was not persisted in the main backtest files.",
            "- If dog HC remains negative in live archive samples, the clay_bo3 implementation should keep ML only or tighten dog-HC gates before any promotion.",
            "",
        ]
    )
    append_group_lines(lines, "Dog HC archive by series", spread_archive_picks, lambda pick: pick.series)
    append_group_lines(lines, "Dog HC archive by edge bucket", spread_archive_picks, lambda pick: edge_bucket(pick.edge_pct))
    append_group_lines(lines, "Dog HC training dataset by year", spread_dataset_picks, lambda pick: pick.year)

    lines.extend(
        [
            "Decision notes",
            "- Keep clay_bo3 ML disabled by default. No simple edge band in the historical sweep clears a basic by-year robustness test.",
            "- Dog HC needs either recovered historical spread snapshots or continued live shadow settlement before it can be treated as more than a diagnostic lane.",
            "- Next useful improvement: add per-tournament clay cohorts and compare ML ROI by Monte Carlo/Madrid/Rome/other clay before changing model math.",
        ]
    )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest the internal clay_bo3 tennis lane.")
    parser.add_argument("--ml-files", nargs="*", default=[str(path) for path in DEFAULT_ML_FILES])
    parser.add_argument("--spread-archive", default=str(DEFAULT_SPREAD_ARCHIVE))
    parser.add_argument("--spread-dataset", default=str(DEFAULT_SPREAD_DATASET))
    parser.add_argument("--out-txt", default=str(DEFAULT_OUT_TXT))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-picks", default=str(DEFAULT_OUT_PICKS))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ml_rows: list[dict[str, str]] = []
    missing = []
    for raw_path in args.ml_files:
        path = Path(raw_path)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            missing.append(str(path))
            continue
        ml_rows.extend(load_csv(path))
    if missing:
        raise FileNotFoundError(f"Missing ML backtest files: {', '.join(missing)}")

    spread_archive = Path(args.spread_archive)
    if not spread_archive.is_absolute():
        spread_archive = ROOT / spread_archive
    spread_dataset = Path(args.spread_dataset)
    if not spread_dataset.is_absolute():
        spread_dataset = ROOT / spread_dataset

    ml_picks = score_ml_rows(ml_rows)
    spread_archive_picks = score_spread_archive(load_csv(spread_archive))
    spread_dataset_picks = score_spread_dataset(load_csv(spread_dataset))
    all_picks = ml_picks + spread_archive_picks + spread_dataset_picks

    lines = report_lines(ml_picks, spread_archive_picks, spread_dataset_picks, len(ml_rows))
    output = "\n".join(lines).rstrip() + "\n"
    print(output)

    summary_rows: list[dict[str, object]] = []
    summary_rows.extend(build_summary_rows("ml_overall", ml_picks, lambda pick: "overall"))
    summary_rows.extend(build_summary_rows("ml_year", ml_picks, lambda pick: pick.year))
    summary_rows.extend(build_summary_rows("ml_series", ml_picks, lambda pick: pick.series))
    summary_rows.extend(build_summary_rows("ml_side", ml_picks, lambda pick: pick.side))
    summary_rows.extend(build_summary_rows("ml_edge_bucket", ml_picks, lambda pick: edge_bucket(pick.edge_pct)))
    for row in threshold_sweep(ml_picks):
        summary_rows.append(
            {
                "section": "ml_threshold_sweep",
                "bucket": f"{row['lo']}-{row['hi']}",
                "bets": int(row["bets"]),
                "wins": "",
                "losses": "",
                "pushes": "",
                "pnl": "",
                "staked": "",
                "roi_pct": round(float(row["roi_pct"]), 4),
                "win_rate_pct": "",
                "avg_edge_pct": "",
                "median_edge_pct": "",
                "avg_odds": "",
                "bootstrap_roi_low_pct": round(float(row["min_year_roi_pct"]), 4),
                "bootstrap_roi_high_pct": round(float(row["roi_2025_pct"]), 4),
                "max_drawdown_units": "",
            }
        )
    summary_rows.extend(build_summary_rows("dog_hc_archive_overall", spread_archive_picks, lambda pick: "overall"))
    summary_rows.extend(build_summary_rows("dog_hc_archive_series", spread_archive_picks, lambda pick: pick.series))
    summary_rows.extend(build_summary_rows("dog_hc_archive_edge_bucket", spread_archive_picks, lambda pick: edge_bucket(pick.edge_pct)))
    summary_rows.extend(build_summary_rows("dog_hc_training_overall", spread_dataset_picks, lambda pick: "overall"))
    summary_rows.extend(build_summary_rows("dog_hc_training_year", spread_dataset_picks, lambda pick: pick.year))

    if not args.dry_run:
        out_txt = Path(args.out_txt)
        out_csv = Path(args.out_csv)
        out_picks = Path(args.out_picks)
        for path in (out_txt, out_csv, out_picks):
            if not path.is_absolute():
                path = ROOT / path
        out_txt.parent.mkdir(parents=True, exist_ok=True)
        out_txt.write_text(output, encoding="utf-8")
        write_summary_csv(Path(args.out_csv) if Path(args.out_csv).is_absolute() else ROOT / args.out_csv, summary_rows)
        write_picks_csv(Path(args.out_picks) if Path(args.out_picks).is_absolute() else ROOT / args.out_picks, all_picks)
        print(f"Wrote report -> {args.out_txt}")
        print(f"Wrote summary -> {args.out_csv}")
        print(f"Wrote picks -> {args.out_picks}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
