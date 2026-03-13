#!/usr/bin/env python3
"""
Build tournament-level historical aggregates from backtest + Sackmann data.

Phases implemented:
  - Phase 0: tournament key map + coverage QA
  - Phase 1: tournament favorite/dog ROI (raw + shrunk)
  - Phase 2: tournament seed/entry stats (raw + shrunk)

Outputs (default: data/backtest):
  - tournament-key-map.csv
  - tournament-fav-dog-roi.csv
  - tournament-seed-entry-stats.csv
  - tournament-stats-qa-report.txt

Notes:
  - `season_year` is taken from source file names, not calendar match dates.
  - This script does not alter the locked fair-odds model.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date as dt_date
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BACKTEST_DIR = ROOT / "data" / "backtest"
DEFAULT_SACKMANN_DIR = ROOT / "data" / "sackmann"
DEFAULT_TML_DIR = ROOT / "tml-data"

REQUIRED_BACKTEST_COLUMNS = {
    "date",
    "tournament",
    "surface",
    "round",
    "series",
    "player1",
    "player2",
    "our_prob",
    "pinnacle_odds",
    "pinnacle_odds_loser",
    "model_favorite",
}

REQUIRED_SACKMANN_COLUMNS = {
    "tourney_name",
    "draw_size",
    "round",
    "winner_seed",
    "winner_entry",
    "winner_name",
    "loser_seed",
    "loser_entry",
    "loser_name",
}

ROUND_ORDER = {
    "RR": 1,
    "BR": 1,
    "R256": 2,
    "R128": 3,
    "R64": 4,
    "R32": 5,
    "R16": 6,
    "QF": 7,
    "SF": 8,
    "F": 9,
}

ROUND_ORDER_TO_LABEL = {v: k for k, v in ROUND_ORDER.items()}
JOIN_NAME_METHODS = ("full", "first_last", "initial_last", "first_last_compact")
JOIN_MAX_DATE_DIFF_DAYS = 21
JOIN_MIN_DATE_GAP_DAYS = 3
_NAME_SUFFIX_RE = re.compile(
    r"(?:,\s*|\s+)(?:jr|sr|junior|senior|ii|iii|iv|v|vi|vii|viii|ix|x|2nd|3rd|4th|5th)\.?$",
    re.IGNORECASE,
)


def _join_method_trust(method: str) -> str:
    m = str(method or "")
    if not m:
        return "low"
    if "cross_year_" in m:
        return "low"
    if "_date_" in m:
        return "low"
    if "_full" in m:
        return "high"
    if "_first_last" in m or "_initial_last" in m or "_first_last_compact" in m:
        return "medium"
    return "low"


@dataclass
class FavDogAgg:
    matches: int = 0
    fav_bets: int = 0
    fav_wins: int = 0
    fav_pl: float = 0.0
    dog_bets: int = 0
    dog_wins: int = 0
    dog_pl: float = 0.0


@dataclass
class SegmentAgg:
    matches: int = 0
    wins: int = 0
    r1_matches: int = 0
    r1_wins: int = 0
    max_round_order: int = 0


def _float(v: Any, default: float | None = None) -> float | None:
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _int(v: Any, default: int | None = None) -> int | None:
    if v is None or v == "":
        return default
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _normalize_for_alias(text: str) -> str:
    s = unicodedata.normalize("NFKD", str(text or ""))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def _ascii_letters(text: str) -> str:
    s = unicodedata.normalize("NFKD", str(text or ""))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z]", "", s.lower())


def _strip_name_suffixes(name: str) -> str:
    s = str(name or "").strip()
    if not s:
        return ""
    prev = None
    while s and s != prev:
        prev = s
        s = _NAME_SUFFIX_RE.sub("", s).strip(" ,.")
    return s


def _normalize_name_for_join(name: str) -> str:
    s = _strip_name_suffixes(name)
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().replace("\u2019", "'").replace("`", "'")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def _name_key_variants(name: str) -> dict[str, str]:
    norm = _normalize_name_for_join(name)
    if not norm:
        return {}
    toks = norm.split()
    first = toks[0]
    last = toks[-1]
    first_last = f"{first} {last}" if first and last else ""
    initial_last = f"{first[:1]} {last}" if first and last else ""
    first_last_compact = first_last
    if len(toks) >= 2 and toks[-2] in {"o", "mc", "mac"}:
        first_last_compact = f"{first} {toks[-2]}{toks[-1]}"
    return {
        "full": norm,
        "first_last": first_last,
        "initial_last": initial_last,
        "first_last_compact": first_last_compact,
    }


def _parse_date_any(value: Any) -> dt_date | None:
    s = str(value or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def _tour_key(name: str) -> str:
    raw = (name or "").strip().lower()
    if not raw:
        return ""
    parts = [p.strip() for p in re.split(r"\s*-\s*", raw) if p.strip()]
    core = parts[-1] if len(parts) >= 2 and len(parts[-1]) >= 4 else raw
    core = re.sub(r"\b\d{4}\b", " ", core)
    core = re.sub(r"\b(challenger|qualifiers?|qualifying|qualification|atp|wta)\b", " ", core)
    core = re.sub(r"[^a-z0-9]+", " ", core)
    return " ".join(core.split())


def _round_code_sackmann(round_text: str) -> str:
    u = (round_text or "").strip().upper()
    if u in ROUND_ORDER:
        return u
    if "QUARTER" in u:
        return "QF"
    if "SEMI" in u:
        return "SF"
    if "FINAL" in u and "QUAL" not in u:
        return "F"
    m = re.search(r"R\s*(\d+)", u)
    if m:
        return f"R{m.group(1)}"
    return u or "UNK"


def _first_round_code(draw_size: int | None) -> str:
    d = draw_size or 32
    if d > 64:
        return "R128"
    if d > 32:
        return "R64"
    return "R32"


def _seed_bucket(seed_raw: str | int | None) -> str:
    seed = _int(seed_raw)
    if seed is None or seed <= 0:
        return "seed_unseeded"
    if seed <= 2:
        return "seed_1_2"
    if seed <= 4:
        return "seed_3_4"
    if seed <= 8:
        return "seed_5_8"
    if seed <= 16:
        return "seed_9_16"
    if seed <= 32:
        return "seed_17_32"
    return "seed_33_plus"


def _entry_bucket(entry_raw: str | None) -> str:
    e = (entry_raw or "").strip().upper()
    if not e:
        return "entry_MD"
    if e in {"Q", "WC", "LL", "PR", "SE", "ALT", "ITF", "JR"}:
        return f"entry_{e}"
    return f"entry_{e}"


def _load_aliases(path: Path) -> dict[tuple[str, str], str]:
    aliases: dict[tuple[str, str], str] = {}
    if not path.exists():
        return aliases
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            src = (row.get("source") or "*").strip().lower() or "*"
            name = _normalize_for_alias(row.get("name") or "")
            key = _tour_key((row.get("tournament_key") or "").strip())
            if not name or not key:
                continue
            aliases[(src, name)] = key
    return aliases


def _resolve_tournament_key(
    source: str,
    name: str,
    aliases: dict[tuple[str, str], str],
) -> tuple[str, bool]:
    src = source.strip().lower()
    norm = _normalize_for_alias(name)
    for k in ((src, norm), ("*", norm), ("all", norm)):
        if k in aliases:
            return aliases[k], True
    return _tour_key(name), False


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _validate_columns(path: Path, rows: list[dict[str, str]], required: set[str]) -> None:
    if not rows:
        return
    missing = sorted(required - set(rows[0].keys()))
    if missing:
        raise RuntimeError(f"{path} missing columns: {missing}")


def _parse_years(raw_years: list[str]) -> list[int]:
    years: list[int] = []
    for y in raw_years:
        yi = _int(y)
        if yi is None:
            continue
        years.append(int(yi))
    if not years:
        raise RuntimeError("No valid years provided.")
    return sorted(set(years))


def _build_windows(years: list[int], rolling: int, previous_editions_only: bool) -> list[dict[str, Any]]:
    years = sorted(set(years))
    out: list[dict[str, Any]] = []
    for y in years:
        out.append(
            {
                "window_type": "year",
                "years": [y],
                "start_year": y,
                "end_year": y,
                "years_label": str(y),
            }
        )
    if rolling >= 2:
        for end in years:
            start = end - rolling + 1
            window_years = [y for y in years if start <= y <= end]
            if len(window_years) == rolling:
                out.append(
                    {
                        "window_type": f"rolling_{rolling}",
                        "years": window_years,
                        "start_year": window_years[0],
                        "end_year": window_years[-1],
                        "years_label": f"{window_years[0]}-{window_years[-1]}",
                    }
                )
    if len(years) >= 2:
        out.append(
            {
                "window_type": "full",
                "years": years,
                "start_year": years[0],
                "end_year": years[-1],
                "years_label": f"{years[0]}-{years[-1]}",
            }
        )
    if previous_editions_only:
        for target in years:
            prior = [y for y in years if y < target]
            if not prior:
                continue
            out.append(
                {
                    "window_type": "prior_editions",
                    "years": prior,
                    "start_year": prior[0],
                    "end_year": prior[-1],
                    "years_label": f"prior_to_{target}",
                    "target_season_year": target,
                }
            )
    # Remove duplicates by (window_type, years_label).
    dedup: dict[tuple[str, str], dict[str, Any]] = {}
    for w in out:
        dedup[(w["window_type"], w["years_label"])] = w
    return list(dedup.values())


def _pick_display_name(counter: Counter[str]) -> str:
    if not counter:
        return ""
    return counter.most_common(1)[0][0]


def _fav_info(row: dict[str, Any]) -> tuple[bool, bool, float, float]:
    player1 = str(row.get("player1") or "")
    player2 = str(row.get("player2") or "")
    model_favorite = str(row.get("model_favorite") or "")
    psw = _float(row.get("pinnacle_odds"), 0.0) or 0.0
    psl = _float(row.get("pinnacle_odds_loser"), 0.0) or 0.0
    p1_prob = _float(row.get("our_prob"), 0.5) or 0.5

    if model_favorite and model_favorite == player1:
        fav_is_player1 = True
    elif model_favorite and model_favorite == player2:
        fav_is_player1 = False
    else:
        fav_is_player1 = p1_prob >= 0.5

    if fav_is_player1:
        fav_win = True  # player1 in backtest rows is actual winner
        fav_odds = psw
        dog_odds = psl
    else:
        fav_win = False
        fav_odds = psl
        dog_odds = psw
    return fav_is_player1, fav_win, fav_odds, dog_odds


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("")
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _build_phase1(
    backtest_rows: list[dict[str, Any]],
    windows: list[dict[str, Any]],
    display_names: dict[str, Counter[str]],
    shrink_k: float,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    for w in windows:
        years_set = set(w["years"])
        sample = [r for r in backtest_rows if int(r["season_year"]) in years_set and r.get("tournament_key")]
        if not sample:
            continue

        by_tournament: dict[str, FavDogAgg] = defaultdict(FavDogAgg)
        global_agg = FavDogAgg()

        for r in sample:
            tkey = r["tournament_key"]
            _fav_is_player1, fav_win, fav_odds, dog_odds = _fav_info(r)
            if fav_odds <= 1.0 or dog_odds <= 1.0:
                continue

            fav_pl = (fav_odds - 1.0) if fav_win else -1.0
            dog_pl = (dog_odds - 1.0) if not fav_win else -1.0

            agg = by_tournament[tkey]
            agg.matches += 1
            agg.fav_bets += 1
            agg.fav_wins += 1 if fav_win else 0
            agg.fav_pl += fav_pl
            agg.dog_bets += 1
            agg.dog_wins += 0 if fav_win else 1
            agg.dog_pl += dog_pl

            global_agg.matches += 1
            global_agg.fav_bets += 1
            global_agg.fav_wins += 1 if fav_win else 0
            global_agg.fav_pl += fav_pl
            global_agg.dog_bets += 1
            global_agg.dog_wins += 0 if fav_win else 1
            global_agg.dog_pl += dog_pl

        global_fav_roi = (global_agg.fav_pl / global_agg.fav_bets) if global_agg.fav_bets else 0.0
        global_dog_roi = (global_agg.dog_pl / global_agg.dog_bets) if global_agg.dog_bets else 0.0

        for tkey, agg in sorted(by_tournament.items(), key=lambda kv: (-kv[1].matches, kv[0])):
            if agg.matches <= 0:
                continue
            fav_roi = (agg.fav_pl / agg.fav_bets) if agg.fav_bets else 0.0
            dog_roi = (agg.dog_pl / agg.dog_bets) if agg.dog_bets else 0.0

            fav_roi_shrunk = ((agg.fav_pl + shrink_k * global_fav_roi) / (agg.fav_bets + shrink_k)) if agg.fav_bets else global_fav_roi
            dog_roi_shrunk = ((agg.dog_pl + shrink_k * global_dog_roi) / (agg.dog_bets + shrink_k)) if agg.dog_bets else global_dog_roi

            out.append(
                {
                    "tournament_key": tkey,
                    "tournament_display": _pick_display_name(display_names.get(tkey, Counter())),
                    "window_type": w["window_type"],
                    "years": w["years_label"],
                    "start_year": w["start_year"],
                    "end_year": w["end_year"],
                    "target_season_year": w.get("target_season_year", ""),
                    "n_matches": agg.matches,
                    "fav_bets": agg.fav_bets,
                    "fav_wins": agg.fav_wins,
                    "fav_pl": round(agg.fav_pl, 6),
                    "fav_roi_pct_raw": round(fav_roi * 100.0, 4),
                    "fav_roi_pct_shrunk": round(fav_roi_shrunk * 100.0, 4),
                    "dog_bets": agg.dog_bets,
                    "dog_wins": agg.dog_wins,
                    "dog_pl": round(agg.dog_pl, 6),
                    "dog_roi_pct_raw": round(dog_roi * 100.0, 4),
                    "dog_roi_pct_shrunk": round(dog_roi_shrunk * 100.0, 4),
                    "n": agg.matches,
                }
            )
    return out


def _build_phase2(
    sackmann_rows: list[dict[str, Any]],
    windows: list[dict[str, Any]],
    display_names: dict[str, Counter[str]],
    shrink_k: float,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    for w in windows:
        years_set = set(w["years"])
        sample = [r for r in sackmann_rows if int(r["season_year"]) in years_set and r.get("tournament_key")]
        if not sample:
            continue

        # By tournament and segment.
        by_tournament: dict[tuple[str, str, str], SegmentAgg] = defaultdict(SegmentAgg)
        # Global priors by segment type.
        global_by_segment: dict[tuple[str, str], SegmentAgg] = defaultdict(SegmentAgg)

        for r in sample:
            tkey = r["tournament_key"]
            round_code = _round_code_sackmann(r.get("round") or "")
            round_order = ROUND_ORDER.get(round_code, 0)
            draw_size = _int(r.get("draw_size"), 32) or 32
            is_r1 = round_code == _first_round_code(draw_size)

            winner_seed_bucket = _seed_bucket(r.get("winner_seed"))
            loser_seed_bucket = _seed_bucket(r.get("loser_seed"))
            winner_entry_bucket = _entry_bucket(r.get("winner_entry"))
            loser_entry_bucket = _entry_bucket(r.get("loser_entry"))

            participants = [
                ("seed", winner_seed_bucket, 1),
                ("seed", loser_seed_bucket, 0),
                ("entry", winner_entry_bucket, 1),
                ("entry", loser_entry_bucket, 0),
            ]

            for family, segment_type, won in participants:
                key_t = (tkey, family, segment_type)
                key_g = (family, segment_type)

                agg_t = by_tournament[key_t]
                agg_t.matches += 1
                agg_t.wins += won
                if is_r1:
                    agg_t.r1_matches += 1
                    agg_t.r1_wins += won
                if round_order > agg_t.max_round_order:
                    agg_t.max_round_order = round_order

                agg_g = global_by_segment[key_g]
                agg_g.matches += 1
                agg_g.wins += won
                if is_r1:
                    agg_g.r1_matches += 1
                    agg_g.r1_wins += won
                if round_order > agg_g.max_round_order:
                    agg_g.max_round_order = round_order

        for (tkey, family, segment_type), agg in sorted(
            by_tournament.items(),
            key=lambda kv: (-kv[1].matches, kv[0][0], kv[0][1], kv[0][2]),
        ):
            if agg.matches <= 0:
                continue
            prior = global_by_segment[(family, segment_type)]
            prior_wr = (prior.wins / prior.matches) if prior.matches else 0.5
            wr_raw = agg.wins / agg.matches
            wr_shrunk = (agg.wins + shrink_k * prior_wr) / (agg.matches + shrink_k)
            r1_wr = (agg.r1_wins / agg.r1_matches) if agg.r1_matches else None

            out.append(
                {
                    "tournament_key": tkey,
                    "tournament_display": _pick_display_name(display_names.get(tkey, Counter())),
                    "window_type": w["window_type"],
                    "years": w["years_label"],
                    "start_year": w["start_year"],
                    "end_year": w["end_year"],
                    "target_season_year": w.get("target_season_year", ""),
                    "segment_family": family,
                    "segment_type": segment_type,
                    "n_matches": agg.matches,
                    "wins": agg.wins,
                    "losses": agg.matches - agg.wins,
                    "win_rate_pct_raw": round(wr_raw * 100.0, 4),
                    "win_rate_pct_shrunk": round(wr_shrunk * 100.0, 4),
                    "r1_matches": agg.r1_matches,
                    "r1_wins": agg.r1_wins,
                    "r1_win_rate_pct_raw": "" if r1_wr is None else round(r1_wr * 100.0, 4),
                    "max_round": ROUND_ORDER_TO_LABEL.get(agg.max_round_order, ""),
                    "max_round_order": agg.max_round_order,
                    "n": agg.matches,
                }
            )
    return out


def _round_stage_backtest(round_text: str) -> str:
    r = (round_text or "").strip().lower()
    if not r:
        return "UNK"
    if "round robin" in r or r == "rr":
        return "RR"
    if "quarter" in r or r == "qf":
        return "QF"
    if "semi" in r or r == "sf":
        return "SF"
    if "final" in r:
        return "F"
    m = re.search(r"(\d+)(st|nd|rd|th)\s+round", r)
    if m:
        return f"R{m.group(1)}"
    # fallback for Rxx style
    m2 = re.search(r"\br\s*(\d+)\b", r)
    if m2:
        return f"R{m2.group(1)}"
    return "UNK"


def _round_stage_sackmann(round_code: str, draw_size: int | None) -> str:
    rc = _round_code_sackmann(round_code)
    if rc in {"QF", "SF", "F", "RR", "BR"}:
        return rc
    if not rc.startswith("R"):
        return "UNK"
    num = _int(rc[1:], None)
    first = _int(_first_round_code(draw_size or 32)[1:], None)
    if num is None or first is None or num <= 0 or first <= 0 or num > first:
        return "UNK"
    ratio = first / float(num)
    # stage = 1 for opening round, 2 for next, etc.
    # only accept power-of-two steps.
    if ratio <= 0:
        return "UNK"
    # robust power-of-two check using log2 tolerance
    import math

    log2v = math.log2(ratio)
    if abs(log2v - round(log2v)) > 1e-9:
        return "UNK"
    stage = int(round(log2v)) + 1
    return f"R{stage}"


def _pick_single_by_date(candidates: list[dict[str, Any]], backtest_date: dt_date | None) -> tuple[dict[str, Any] | None, str]:
    if len(candidates) == 1:
        return candidates[0], "unique"
    if not candidates or backtest_date is None:
        return None, "no_date"

    ranked: list[tuple[int, dict[str, Any]]] = []
    for c in candidates:
        cdate = _parse_date_any(c.get("tourney_date"))
        if cdate is None:
            ranked.append((10**9, c))
        else:
            ranked.append((abs((backtest_date - cdate).days), c))
    ranked.sort(key=lambda x: x[0])
    if not ranked:
        return None, "empty"
    best_diff = ranked[0][0]
    if best_diff > JOIN_MAX_DATE_DIFF_DAYS:
        return None, "too_far"
    if len(ranked) == 1:
        return ranked[0][1], "date_single"
    second_diff = ranked[1][0]
    if best_diff + JOIN_MIN_DATE_GAP_DAYS <= second_diff:
        return ranked[0][1], "date_gap"
    return None, "ambiguous_date"


def _join_backtest_to_sackmann(
    backtest_rows: list[dict[str, Any]],
    sackmann_rows: list[dict[str, Any]],
    season_years_with_sackmann: set[int],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    # Build indexes at multiple strictness levels.
    idx_tkey_stage: dict[str, dict[tuple[str, int, str, str, str], list[dict[str, Any]]]] = {
        m: defaultdict(list) for m in JOIN_NAME_METHODS
    }
    idx_tkey: dict[str, dict[tuple[str, int, str, str], list[dict[str, Any]]]] = {
        m: defaultdict(list) for m in JOIN_NAME_METHODS
    }
    idx_stage: dict[str, dict[tuple[int, str, str, str], list[dict[str, Any]]]] = {
        m: defaultdict(list) for m in JOIN_NAME_METHODS
    }
    idx_year: dict[str, dict[tuple[int, str, str], list[dict[str, Any]]]] = {
        m: defaultdict(list) for m in JOIN_NAME_METHODS
    }

    for s in sackmann_rows:
        tkey = str(s.get("tournament_key") or "")
        if not tkey:
            continue
        season = int(s["season_year"])
        stage = _round_stage_sackmann(str(s.get("round") or ""), _int(s.get("draw_size"), 32))
        wkeys = _name_key_variants(str(s.get("winner_name") or ""))
        lkeys = _name_key_variants(str(s.get("loser_name") or ""))
        if not wkeys or not lkeys:
            continue
        for method in JOIN_NAME_METHODS:
            wk = wkeys.get(method, "")
            lk = lkeys.get(method, "")
            if not wk or not lk:
                continue
            idx_tkey_stage[method][(tkey, season, stage, wk, lk)].append(s)
            idx_tkey[method][(tkey, season, wk, lk)].append(s)
            idx_stage[method][(season, stage, wk, lk)].append(s)
            idx_year[method][(season, wk, lk)].append(s)

    counters = Counter()
    joined: list[dict[str, Any]] = []

    for b in backtest_rows:
        season = int(b["season_year"])
        if season not in season_years_with_sackmann:
            counters["skipped_no_sackmann_year"] += 1
            continue
        tkey = str(b.get("tournament_key") or "")
        if not tkey:
            counters["skipped_no_tkey"] += 1
            continue
        stage = _round_stage_backtest(str(b.get("round") or ""))
        bdate = _parse_date_any(b.get("date"))
        wkeys = _name_key_variants(str(b.get("player1") or ""))
        lkeys = _name_key_variants(str(b.get("player2") or ""))
        if not wkeys or not lkeys:
            counters["skipped_no_name"] += 1
            continue

        counters["eligible"] += 1
        matched_row: dict[str, Any] | None = None
        matched_method = ""

        # 1) Tournament + stage + name key.
        for method in JOIN_NAME_METHODS:
            wk = wkeys.get(method, "")
            lk = lkeys.get(method, "")
            if not wk or not lk:
                continue
            cands = idx_tkey_stage[method].get((tkey, season, stage, wk, lk), [])
            if len(cands) == 1:
                matched_row = cands[0]
                matched_method = f"tkey_stage_{method}"
                break
            if len(cands) > 1:
                pick, reason = _pick_single_by_date(cands, bdate)
                if pick is not None:
                    matched_row = pick
                    matched_method = f"tkey_stage_{method}_date_{reason}"
                    break
        if matched_row is not None:
            row = dict(b)
            row["_joined_sackmann"] = matched_row
            row["_join_method"] = matched_method
            row["_join_trust"] = _join_method_trust(matched_method)
            joined.append(row)
            counters["joined_total"] += 1
            counters[f"join_{matched_method}"] += 1
            counters[f"join_trust_{row['_join_trust']}"] += 1
            continue

        # 2) Tournament + name key.
        for method in JOIN_NAME_METHODS:
            wk = wkeys.get(method, "")
            lk = lkeys.get(method, "")
            if not wk or not lk:
                continue
            cands = idx_tkey[method].get((tkey, season, wk, lk), [])
            pick, reason = _pick_single_by_date(cands, bdate)
            if pick is not None:
                matched_row = pick
                matched_method = f"tkey_{method}_{reason}"
                break
        if matched_row is not None:
            row = dict(b)
            row["_joined_sackmann"] = matched_row
            row["_join_method"] = matched_method
            row["_join_trust"] = _join_method_trust(matched_method)
            joined.append(row)
            counters["joined_total"] += 1
            counters[f"join_{matched_method}"] += 1
            counters[f"join_trust_{row['_join_trust']}"] += 1
            continue

        # 3) Cross-tournament stage + name key.
        for method in JOIN_NAME_METHODS:
            wk = wkeys.get(method, "")
            lk = lkeys.get(method, "")
            if not wk or not lk:
                continue
            cands = idx_stage[method].get((season, stage, wk, lk), [])
            pick, reason = _pick_single_by_date(cands, bdate)
            if pick is not None:
                matched_row = pick
                matched_method = f"cross_stage_{method}_{reason}"
                break
        if matched_row is not None:
            row = dict(b)
            row["_joined_sackmann"] = matched_row
            row["_join_method"] = matched_method
            row["_join_trust"] = _join_method_trust(matched_method)
            joined.append(row)
            counters["joined_total"] += 1
            counters[f"join_{matched_method}"] += 1
            counters[f"join_trust_{row['_join_trust']}"] += 1
            continue

        # 4) Cross-tournament year + name key, date-disambiguated only.
        for method in JOIN_NAME_METHODS:
            wk = wkeys.get(method, "")
            lk = lkeys.get(method, "")
            if not wk or not lk:
                continue
            cands = idx_year[method].get((season, wk, lk), [])
            pick, reason = _pick_single_by_date(cands, bdate)
            if pick is not None:
                matched_row = pick
                matched_method = f"cross_year_{method}_{reason}"
                break
        if matched_row is not None:
            row = dict(b)
            row["_joined_sackmann"] = matched_row
            row["_join_method"] = matched_method
            row["_join_trust"] = _join_method_trust(matched_method)
            joined.append(row)
            counters["joined_total"] += 1
            counters[f"join_{matched_method}"] += 1
            counters[f"join_trust_{row['_join_trust']}"] += 1
            continue

        counters["unmatched"] += 1

    return joined, dict(counters)


def _build_phase3_segment_roi(
    joined_rows: list[dict[str, Any]],
    windows: list[dict[str, Any]],
    display_names: dict[str, Counter[str]],
    shrink_k: float,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for w in windows:
        years_set = set(w["years"])
        sample = [r for r in joined_rows if int(r["season_year"]) in years_set and r.get("tournament_key")]
        if not sample:
            continue

        by_tournament: dict[tuple[str, str, str, str], FavDogAgg] = defaultdict(FavDogAgg)
        global_segment: dict[tuple[str, str, str], FavDogAgg] = defaultdict(FavDogAgg)

        for r in sample:
            tkey = str(r["tournament_key"])
            s = r["_joined_sackmann"]
            fav_is_player1, fav_win, fav_odds, dog_odds = _fav_info(r)
            if fav_odds <= 1.0 or dog_odds <= 1.0:
                continue

            fav_seed = _seed_bucket(s.get("winner_seed") if fav_is_player1 else s.get("loser_seed"))
            dog_seed = _seed_bucket(s.get("loser_seed") if fav_is_player1 else s.get("winner_seed"))
            fav_entry = _entry_bucket(s.get("winner_entry") if fav_is_player1 else s.get("loser_entry"))
            dog_entry = _entry_bucket(s.get("loser_entry") if fav_is_player1 else s.get("winner_entry"))

            fav_pl = (fav_odds - 1.0) if fav_win else -1.0
            dog_pl = (dog_odds - 1.0) if not fav_win else -1.0

            segments = [
                ("fav", "seed", fav_seed, fav_win, fav_pl),
                ("fav", "entry", fav_entry, fav_win, fav_pl),
                ("dog", "seed", dog_seed, not fav_win, dog_pl),
                ("dog", "entry", dog_entry, not fav_win, dog_pl),
            ]
            for side, family, seg_type, won, pl in segments:
                kt = (tkey, side, family, seg_type)
                kg = (side, family, seg_type)
                at = by_tournament[kt]
                at.matches += 1
                at.fav_bets += 1
                at.fav_wins += 1 if won else 0
                at.fav_pl += pl

                ag = global_segment[kg]
                ag.matches += 1
                ag.fav_bets += 1
                ag.fav_wins += 1 if won else 0
                ag.fav_pl += pl

        for (tkey, side, family, seg_type), agg in sorted(
            by_tournament.items(),
            key=lambda kv: (-kv[1].matches, kv[0][0], kv[0][1], kv[0][2], kv[0][3]),
        ):
            if agg.matches <= 0:
                continue
            roi_raw = agg.fav_pl / agg.fav_bets
            prior = global_segment[(side, family, seg_type)]
            prior_roi = (prior.fav_pl / prior.fav_bets) if prior.fav_bets else 0.0
            roi_shrunk = (agg.fav_pl + shrink_k * prior_roi) / (agg.fav_bets + shrink_k)
            wr_raw = agg.fav_wins / agg.fav_bets if agg.fav_bets else 0.0

            out.append(
                {
                    "tournament_key": tkey,
                    "tournament_display": _pick_display_name(display_names.get(tkey, Counter())),
                    "window_type": w["window_type"],
                    "years": w["years_label"],
                    "start_year": w["start_year"],
                    "end_year": w["end_year"],
                    "target_season_year": w.get("target_season_year", ""),
                    "bet_side": side,
                    "segment_family": family,
                    "segment_type": seg_type,
                    "n_bets": agg.fav_bets,
                    "wins": agg.fav_wins,
                    "losses": agg.fav_bets - agg.fav_wins,
                    "pl_units": round(agg.fav_pl, 6),
                    "roi_pct_raw": round(roi_raw * 100.0, 4),
                    "roi_pct_shrunk": round(roi_shrunk * 100.0, 4),
                    "win_rate_pct_raw": round(wr_raw * 100.0, 4),
                    "n": agg.fav_bets,
                }
            )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Build tournament historical stats from backtest and Sackmann data.")
    parser.add_argument("--years", nargs="+", default=["2022", "2023", "2024", "2025"], help="Seasons to include.")
    parser.add_argument("--rolling", type=int, default=4, help="Rolling window size in years.")
    parser.add_argument("--output-dir", default=str(DEFAULT_BACKTEST_DIR), help="Output directory.")
    parser.add_argument("--backtest-dir", default=str(DEFAULT_BACKTEST_DIR), help="Directory with backtest-results-YYYY.csv files.")
    parser.add_argument("--sackmann-dir", default=str(DEFAULT_SACKMANN_DIR), help="Directory with atp_matches_YYYY.csv files.")
    parser.add_argument("--tml-dir", default=str(DEFAULT_TML_DIR), help="Directory with TML YYYY.csv files.")
    parser.add_argument(
        "--aliases",
        default=str(DEFAULT_BACKTEST_DIR / "tournament-aliases.csv"),
        help="Alias CSV path with columns: source,name,tournament_key",
    )
    parser.add_argument("--shrinkage-k-roi", type=float, default=30.0, help="Shrinkage strength for ROI metrics.")
    parser.add_argument("--shrinkage-k-win", type=float, default=20.0, help="Shrinkage strength for win-rate metrics.")
    parser.add_argument("--enable-phase3", action="store_true", help="Attempt Phase 3 join + segment ROI output.")
    parser.add_argument("--phase3-min-join-rate", type=float, default=0.90, help="Minimum join rate required to write Phase 3 output.")
    parser.add_argument(
        "--phase3-join-trust-mode",
        choices=["all", "high", "high_medium"],
        default="all",
        help="Subset of joined rows used for Phase 3 output: all, high, or high_medium.",
    )
    parser.add_argument(
        "--previous-editions-only",
        action="store_true",
        help="Also emit prior-editions windows (`prior_to_<season>`).",
    )
    args = parser.parse_args()

    years = _parse_years(list(args.years))
    output_dir = Path(args.output_dir) if Path(args.output_dir).is_absolute() else (ROOT / args.output_dir)
    backtest_dir = Path(args.backtest_dir) if Path(args.backtest_dir).is_absolute() else (ROOT / args.backtest_dir)
    sackmann_dir = Path(args.sackmann_dir) if Path(args.sackmann_dir).is_absolute() else (ROOT / args.sackmann_dir)
    tml_dir = Path(args.tml_dir) if Path(args.tml_dir).is_absolute() else (ROOT / args.tml_dir)
    aliases_path = Path(args.aliases) if Path(args.aliases).is_absolute() else (ROOT / args.aliases)

    aliases = _load_aliases(aliases_path)
    windows = _build_windows(years, rolling=max(1, int(args.rolling)), previous_editions_only=bool(args.previous_editions_only))

    qa_lines: list[str] = []
    qa_lines.append(f"Run UTC: {datetime.now(timezone.utc).isoformat()}")
    qa_lines.append(f"Years requested: {years}")
    qa_lines.append(f"Rolling window: {args.rolling}")
    qa_lines.append(f"Previous editions windows: {bool(args.previous_editions_only)}")
    qa_lines.append(f"Phase 3 trust mode: {args.phase3_join_trust_mode}")
    qa_lines.append(f"Alias file: {aliases_path} (rows={len(aliases)})")

    # Load backtest rows.
    backtest_rows: list[dict[str, Any]] = []
    missing_backtest: list[str] = []
    for y in years:
        p = backtest_dir / f"backtest-results-{y}.csv"
        if not p.exists():
            missing_backtest.append(str(p))
            continue
        rows = _read_csv_rows(p)
        if not rows:
            continue
        _validate_columns(p, rows, REQUIRED_BACKTEST_COLUMNS)
        for r in rows:
            tkey, alias_used = _resolve_tournament_key("backtest", str(r.get("tournament") or ""), aliases)
            r2 = dict(r)
            r2["season_year"] = y
            r2["tournament_key"] = tkey
            r2["alias_used"] = alias_used
            backtest_rows.append(r2)

    # Load seed/entry rows by year: prefer Sackmann, fallback to TML.
    seed_rows: list[dict[str, Any]] = []
    seed_source_year: dict[int, str] = {}
    missing_sackmann: list[str] = []
    missing_tml: list[str] = []
    missing_seed_data_years: list[int] = []
    for y in years:
        sackmann_path = sackmann_dir / f"atp_matches_{y}.csv"
        tml_path = tml_dir / f"{y}.csv"
        if not sackmann_path.exists():
            missing_sackmann.append(str(sackmann_path))
        if not tml_path.exists():
            missing_tml.append(str(tml_path))

        source = ""
        p: Path | None = None
        if sackmann_path.exists():
            source = "sackmann"
            p = sackmann_path
        elif tml_path.exists():
            source = "tml"
            p = tml_path
        else:
            missing_seed_data_years.append(y)
            continue

        rows = _read_csv_rows(p)
        if not rows:
            continue
        _validate_columns(p, rows, REQUIRED_SACKMANN_COLUMNS)
        seed_source_year[y] = source
        for r in rows:
            tkey, alias_used = _resolve_tournament_key(source, str(r.get("tourney_name") or ""), aliases)
            r2 = dict(r)
            r2["season_year"] = y
            r2["tournament_key"] = tkey
            r2["alias_used"] = alias_used
            r2["seed_source"] = source
            seed_rows.append(r2)

    qa_lines.append(f"Backtest rows loaded: {len(backtest_rows):,}")
    qa_lines.append(f"Seed/entry rows loaded: {len(seed_rows):,}")
    if seed_rows:
        src_counts = Counter(str(r.get("seed_source") or "unknown") for r in seed_rows)
        src_count_parts = ", ".join(f"{k}={v:,}" for k, v in sorted(src_counts.items()))
        qa_lines.append(f"Seed/entry rows by source: {src_count_parts}")
    if seed_source_year:
        years_by_source: dict[str, list[int]] = defaultdict(list)
        for yy, src in sorted(seed_source_year.items()):
            years_by_source[src].append(yy)
        qa_lines.append("Seed/entry source by season year:")
        for src, ys in sorted(years_by_source.items()):
            qa_lines.append(f"  {src}: {ys}")
    if missing_backtest:
        qa_lines.append(f"Missing backtest files ({len(missing_backtest)}):")
        qa_lines.extend(f"  - {x}" for x in missing_backtest)
    if missing_sackmann:
        qa_lines.append(f"Missing Sackmann files ({len(missing_sackmann)}):")
        qa_lines.extend(f"  - {x}" for x in missing_sackmann)
    if missing_tml:
        qa_lines.append(f"Missing TML files ({len(missing_tml)}):")
        qa_lines.extend(f"  - {x}" for x in missing_tml)
    if missing_seed_data_years:
        qa_lines.append(f"Missing seed/entry source for years: {missing_seed_data_years}")

    # Phase 0: tournament key map + coverage.
    map_rows: list[dict[str, Any]] = []
    display_names: dict[str, Counter[str]] = defaultdict(Counter)

    source_name_counter: dict[tuple[str, str], int] = defaultdict(int)
    source_name_years: dict[tuple[str, str], set[int]] = defaultdict(set)
    source_name_key: dict[tuple[str, str], str] = {}
    source_name_norm: dict[tuple[str, str], str] = {}
    source_name_alias: dict[tuple[str, str], bool] = {}

    for r in backtest_rows:
        src = "backtest"
        name = str(r.get("tournament") or "").strip()
        key_tuple = (src, name)
        source_name_counter[key_tuple] += 1
        source_name_years[key_tuple].add(int(r["season_year"]))
        source_name_key[key_tuple] = str(r.get("tournament_key") or "")
        source_name_norm[key_tuple] = _normalize_for_alias(name)
        source_name_alias[key_tuple] = bool(r.get("alias_used"))
        if r.get("tournament_key"):
            display_names[str(r["tournament_key"])][name] += 1

    for r in seed_rows:
        src = str(r.get("seed_source") or "sackmann")
        name = str(r.get("tourney_name") or "").strip()
        key_tuple = (src, name)
        source_name_counter[key_tuple] += 1
        source_name_years[key_tuple].add(int(r["season_year"]))
        source_name_key[key_tuple] = str(r.get("tournament_key") or "")
        source_name_norm[key_tuple] = _normalize_for_alias(name)
        source_name_alias[key_tuple] = bool(r.get("alias_used"))
        if r.get("tournament_key"):
            display_names[str(r["tournament_key"])][name] += 1

    unique_counts: dict[str, int] = defaultdict(int)
    mapped_unique_counts: dict[str, int] = defaultdict(int)
    row_counts: dict[str, int] = defaultdict(int)
    mapped_row_counts: dict[str, int] = defaultdict(int)

    for (src, name), cnt in sorted(source_name_counter.items(), key=lambda kv: (kv[0][0], -kv[1], kv[0][1])):
        tkey = source_name_key[(src, name)]
        years_label = ",".join(str(x) for x in sorted(source_name_years[(src, name)]))
        mapped = bool(tkey)
        unique_counts[src] += 1
        row_counts[src] += cnt
        if mapped:
            mapped_unique_counts[src] += 1
            mapped_row_counts[src] += cnt
        map_rows.append(
            {
                "source": src,
                "name": name,
                "name_normalized": source_name_norm[(src, name)],
                "tournament_key": tkey,
                "mapped": mapped,
                "alias_used": source_name_alias[(src, name)],
                "rows_count": cnt,
                "season_years": years_label,
            }
        )

    qa_lines.append("Phase 0 coverage:")
    for src in sorted(unique_counts):
        uc = unique_counts[src]
        mc = mapped_unique_counts[src]
        rc = row_counts[src]
        mrc = mapped_row_counts[src]
        unique_cov = (mc / uc * 100.0) if uc else 0.0
        row_cov = (mrc / rc * 100.0) if rc else 0.0
        qa_lines.append(f"  {src} unique: {mc}/{uc} ({unique_cov:.2f}%)")
        qa_lines.append(f"  {src} rows:   {mrc}/{rc} ({row_cov:.2f}%)")

    # Phase 1.
    phase1_rows = _build_phase1(
        backtest_rows=backtest_rows,
        windows=windows,
        display_names=display_names,
        shrink_k=float(args.shrinkage_k_roi),
    )
    qa_lines.append(f"Phase 1 rows written: {len(phase1_rows):,}")

    # Phase 2.
    phase2_rows = _build_phase2(
        sackmann_rows=seed_rows,
        windows=windows,
        display_names=display_names,
        shrink_k=float(args.shrinkage_k_win),
    )
    qa_lines.append(f"Phase 2 rows written: {len(phase2_rows):,}")

    # Phase 3: optional join + segment ROI.
    phase3_rows: list[dict[str, Any]] = []
    phase3_join_stats: dict[str, int] = {}
    season_years_with_seed_data = {int(r["season_year"]) for r in seed_rows}
    if args.enable_phase3:
        joined_rows, phase3_join_stats = _join_backtest_to_sackmann(
            backtest_rows=backtest_rows,
            sackmann_rows=seed_rows,
            season_years_with_sackmann=season_years_with_seed_data,
        )
        eligible = int(phase3_join_stats.get("eligible", 0))
        joined_total_all = int(phase3_join_stats.get("joined_total", 0))
        join_rate_all = (joined_total_all / eligible) if eligible else 0.0

        if args.phase3_join_trust_mode == "high":
            joined_rows = [r for r in joined_rows if r.get("_join_trust") == "high"]
        elif args.phase3_join_trust_mode == "high_medium":
            joined_rows = [r for r in joined_rows if r.get("_join_trust") in {"high", "medium"}]

        joined_total = len(joined_rows)
        join_rate = (joined_total / eligible) if eligible else 0.0
        qa_lines.append("Phase 3 join stats:")
        qa_lines.append(f"  eligible: {eligible}")
        qa_lines.append(f"  joined_total_all: {joined_total_all}")
        qa_lines.append(f"  join_rate_all: {join_rate_all:.4f}")
        qa_lines.append(f"  joined_total: {joined_total}")
        qa_lines.append(f"  skipped_no_sackmann_year: {int(phase3_join_stats.get('skipped_no_sackmann_year', 0))}")
        qa_lines.append(f"  skipped_no_tkey: {int(phase3_join_stats.get('skipped_no_tkey', 0))}")
        qa_lines.append(f"  skipped_no_name: {int(phase3_join_stats.get('skipped_no_name', 0))}")
        qa_lines.append(f"  unmatched: {int(phase3_join_stats.get('unmatched', 0))}")
        qa_lines.append(f"  join_rate: {join_rate:.4f}")
        qa_lines.append(f"  trust_high: {int(phase3_join_stats.get('join_trust_high', 0))}")
        qa_lines.append(f"  trust_medium: {int(phase3_join_stats.get('join_trust_medium', 0))}")
        qa_lines.append(f"  trust_low: {int(phase3_join_stats.get('join_trust_low', 0))}")
        join_method_counts = sorted(
            (
                (k.replace("join_", "", 1), int(v))
                for k, v in phase3_join_stats.items()
                if str(k).startswith("join_") and not str(k).startswith("join_trust_") and int(v) > 0
            ),
            key=lambda kv: (-kv[1], kv[0]),
        )
        if join_method_counts:
            qa_lines.append("  join_methods:")
            for method, count in join_method_counts:
                qa_lines.append(f"    {method}: {count}")
        if join_rate >= float(args.phase3_min_join_rate):
            phase3_rows = _build_phase3_segment_roi(
                joined_rows=joined_rows,
                windows=windows,
                display_names=display_names,
                shrink_k=float(args.shrinkage_k_roi),
            )
            qa_lines.append(f"Phase 3 gate: PASS (min_join_rate={args.phase3_min_join_rate:.2f})")
            qa_lines.append(f"Phase 3 rows written: {len(phase3_rows):,}")
        else:
            qa_lines.append(f"Phase 3 gate: FAIL (min_join_rate={args.phase3_min_join_rate:.2f})")
            qa_lines.append("Phase 3 output skipped due to low join rate.")
    else:
        qa_lines.append("Phase 3 status: disabled (use --enable-phase3 to run join + segment ROI).")

    output_dir.mkdir(parents=True, exist_ok=True)
    key_map_path = output_dir / "tournament-key-map.csv"
    phase1_path = output_dir / "tournament-fav-dog-roi.csv"
    phase2_path = output_dir / "tournament-seed-entry-stats.csv"
    phase3_path = output_dir / "tournament-segment-roi.csv"
    qa_path = output_dir / "tournament-stats-qa-report.txt"

    _write_csv(key_map_path, map_rows)
    _write_csv(phase1_path, phase1_rows)
    _write_csv(phase2_path, phase2_rows)
    if args.enable_phase3 and phase3_rows:
        _write_csv(phase3_path, phase3_rows)
    qa_path.write_text("\n".join(qa_lines).strip() + "\n", encoding="utf-8")

    print(f"Wrote: {key_map_path}")
    print(f"Wrote: {phase1_path}")
    print(f"Wrote: {phase2_path}")
    if args.enable_phase3 and phase3_rows:
        print(f"Wrote: {phase3_path}")
    print(f"Wrote: {qa_path}")

    # Non-zero exit only if both sources fully missing.
    if not backtest_rows and not seed_rows:
        print("No usable input rows loaded from backtest or seed/entry sources (Sackmann/TML).", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
