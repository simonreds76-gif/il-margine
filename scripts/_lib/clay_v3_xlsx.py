"""Tennis-data XLSX rank joins for Clay ML v3 Phase A."""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .clay_v3_tournament_map import canonical_tournament_key


FIELDNAMES = [
    "date",
    "tournament",
    "winner_id",
    "loser_id",
    "winner_name",
    "loser_name",
    "winner_rank",
    "loser_rank",
    "winner_points",
    "loser_points",
    "join_method",
]


@dataclass(frozen=True)
class RankJoinResult:
    rows: list[dict[str, Any]]
    coverage_count: int
    total_count: int
    join_methods: dict[str, int]
    retirement_count: int
    misses: list[dict[str, Any]]

    @property
    def coverage(self) -> float:
        return self.coverage_count / self.total_count if self.total_count else 1.0


def _norm_name(s: str | None) -> str:
    t = (s or "").strip().lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return t.replace("-", "").replace("'", "")


def _tokenise_name(name: str | None) -> list[str]:
    cleaned = (name or "").replace(",", " ").replace("-", " ")
    cleaned = re.sub(r"\s*\([^)]*\)", " ", cleaned)
    cleaned = re.sub(r"\s*\[[^\]]*\]", " ", cleaned)
    return [
        _norm_name(tok)
        for tok in cleaned.split()
        if tok and not re.match(r"^[a-z]$", _norm_name(tok))
    ]


def _surname_keys(name: str | None) -> list[str]:
    tokens = _tokenise_name(name)
    if not tokens:
        return []
    out = {tokens[-1]}
    if len(tokens) >= 2:
        out.add(tokens[-2])
        out.add(f"{tokens[-2]} {tokens[-1]}")
        out.add(f"{tokens[-2]}{tokens[-1]}")
    return sorted(out)


def _full_key(name: str | None) -> str:
    return " ".join(_tokenise_name(name))


def _float_or_blank(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return ""
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.3f}".rstrip("0").rstrip(".")


def _date_iso(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ""
    return ts.strftime("%Y-%m-%d")


def load_xlsx_rank_index(paths: list[Path]) -> tuple[dict[tuple[str, str, str, str], dict[str, Any]], dict[tuple[str, str, str, str], dict[str, Any]], int]:
    full_index: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    surname_buckets: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    retirement_count = 0
    for path in paths:
        df = pd.read_excel(path)
        if "Surface" in df.columns:
            df = df[df["Surface"].astype(str).str.lower().eq("clay")]
        for record in df.to_dict("records"):
            date_iso = _date_iso(record.get("Date"))
            canonical = canonical_tournament_key(str(record.get("Tournament") or ""))
            if not date_iso or not canonical:
                continue
            if str(record.get("Comment") or "").strip().lower() == "retired":
                retirement_count += 1
            winner = str(record.get("Winner") or "")
            loser = str(record.get("Loser") or "")
            row = {
                "date": date_iso,
                "tournament_canonical_key": canonical,
                "winner_short": winner,
                "loser_short": loser,
                "winner_rank": _float_or_blank(record.get("WRank")),
                "loser_rank": _float_or_blank(record.get("LRank")),
                "winner_points": _float_or_blank(record.get("WPts")),
                "loser_points": _float_or_blank(record.get("LPts")),
                "comment": str(record.get("Comment") or ""),
            }
            full_index[(date_iso, canonical, _full_key(winner), _full_key(loser))] = row
            for wk in _surname_keys(winner):
                for lk in _surname_keys(loser):
                    surname_buckets[(date_iso, canonical, wk, lk)].append(row)
    surname_index: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for key, rows in surname_buckets.items():
        if len(rows) == 1:
            surname_index[key] = rows[0]
    return full_index, surname_index, retirement_count


def join_fixture_ranks(fixtures: list[dict[str, Any]], xlsx_paths: list[Path]) -> RankJoinResult:
    full_index, surname_index, retirement_count = load_xlsx_rank_index(xlsx_paths)
    out: list[dict[str, Any]] = []
    methods = Counter()
    misses: list[dict[str, Any]] = []
    for fixture in fixtures:
        date_iso = str(fixture["date"])
        canonical = canonical_tournament_key(str(fixture.get("tournament") or ""))
        winner_name = str(fixture.get("player1") or "")
        loser_name = str(fixture.get("player2") or "")
        match = None
        method = "miss"
        if canonical:
            full_key = (date_iso, canonical, _full_key(winner_name), _full_key(loser_name))
            match = full_index.get(full_key)
            if match is not None:
                method = "full_name"
            else:
                for wk in _surname_keys(winner_name):
                    for lk in _surname_keys(loser_name):
                        candidate = surname_index.get((date_iso, canonical, wk, lk))
                        if candidate is not None:
                            match = candidate
                            method = "surname"
                            break
                    if match is not None:
                        break
        row = {
            "date": date_iso,
            "tournament": fixture.get("tournament", ""),
            "winner_id": fixture.get("player1_id", ""),
            "loser_id": fixture.get("player2_id", ""),
            "winner_name": winner_name,
            "loser_name": loser_name,
            "winner_rank": match["winner_rank"] if match else "",
            "loser_rank": match["loser_rank"] if match else "",
            "winner_points": match["winner_points"] if match else "",
            "loser_points": match["loser_points"] if match else "",
            "join_method": method,
        }
        out.append(row)
        methods[method] += 1
        if method == "miss":
            misses.append(row)
    coverage = sum(1 for row in out if row["winner_rank"] and row["loser_rank"])
    return RankJoinResult(
        rows=out,
        coverage_count=coverage,
        total_count=len(out),
        join_methods=dict(methods),
        retirement_count=retirement_count,
        misses=misses,
    )


def write_rank_cache(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
