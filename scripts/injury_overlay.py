from __future__ import annotations

import csv
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable


_TRUE_VALUES = {"1", "true", "yes", "on"}
_TRAILING_SLUG_NOISE_RE = re.compile(r"-(?:[0-9a-f]{5,}|\d{3,})$")


def env_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in _TRUE_VALUES


def _strip_accents(text: str) -> str:
    nkfd = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in nkfd if not unicodedata.combining(ch))


def _tokenize_name(text: str) -> list[str]:
    raw = _strip_accents(text).lower()
    raw = raw.replace("-", " ").replace("'", " ").replace(".", " ").replace(",", " ")
    raw = re.sub(r"[^a-z0-9 ]+", " ", raw)
    toks = [t for t in raw.split() if t]
    return toks


def _tokenize_slug(slug: str) -> list[str]:
    s = _strip_accents(slug).lower()
    s = re.sub(r"[^a-z0-9_-]+", "-", s)
    s = s.replace("_", "-")
    s = re.sub(r"-+", "-", s).strip("-")
    s = _TRAILING_SLUG_NOISE_RE.sub("", s)
    if not s:
        return []
    return [x for x in s.split("-") if x]


def _surname_variants(tokens: list[str]) -> set[str]:
    t = [x for x in tokens if x and len(x) >= 2]
    if not t:
        return set()
    out: set[str] = set()
    out.add(t[-1])  # last token
    if len(t) >= 2:
        out.add(" ".join(t[-2:]))  # last two
        out.add("".join(t[-2:]))  # compact last two
    out.add(" ".join(t))  # full surname phrase
    out.add("".join(t))  # compact phrase
    return {x for x in out if len(x.replace(" ", "")) >= 2}


def _parse_te_player_name(player_name: str) -> tuple[list[str], str | None]:
    """TennisExplorer format is 'Last F.' or 'Last F'. Return (surname_tokens, first_initial)."""
    toks = _tokenize_name(player_name)
    if not toks:
        return [], None
    # "Kecmanovic M." / "Altmaier D." -> last token is initial
    if len(toks) >= 2 and len(toks[-1]) == 1:
        return toks[:-1], toks[-1]
    # "M. Kecmanovic" style
    if len(toks) >= 2 and len(toks[0]) == 1:
        return toks[1:], toks[0]
    if len(toks) >= 2:
        return toks[1:], toks[0][0]  # surname = rest, initial = first letter of first
    return toks, toks[0][0] if toks and toks[0] else None


def _parse_oncourt_name(player_name: str) -> tuple[list[str], str | None]:
    """OnCourt format is usually 'First Last'. Return (surname_tokens, first_initial). Same (surname, initial) rule as TE so 'First Last' matches TE 'Last F.'."""
    raw = player_name or ""
    if "," in raw:
        left, right = raw.split(",", 1)
        surname = _tokenize_name(left)
        given = _tokenize_name(right)
        initial = given[0][0] if given else (surname[0][0] if surname else None)
        return (surname if surname else _tokenize_name(raw)), initial

    toks = _tokenize_name(raw)
    if not toks:
        return [], None
    # "Last F." style (same as TE)
    if len(toks) >= 2 and len(toks[-1]) == 1:
        return toks[:-1], toks[-1]
    if len(toks) >= 2 and len(toks[0]) == 1:
        return toks[1:], toks[0]
    # "First Last" -> surname = last token(s), initial = first letter of first name
    if len(toks) >= 2:
        return toks[1:], toks[0][0]  # Miomir Kecmanovic -> (['kecmanovic'], 'm')
    if len(toks) == 1:
        return toks, toks[0][0]
    return toks[1:], toks[0][0]


def _normalize_initial(initial: str | None) -> str:
    """Single letter, lowercase; strip periods so 'M.' and 'M' match."""
    i = (initial or "").strip().lower().rstrip(".")
    return i[0] if i else ""


def _make_strong_keys(surnames: Iterable[str], initial: str | None) -> set[str]:
    i = _normalize_initial(initial)
    if not i:
        return set()
    return {f"{s}|{i}" for s in surnames if s}


def _te_row_keys(player_name: str, player_slug: str) -> tuple[set[str], set[str]]:
    surname_tokens, initial = _parse_te_player_name(player_name)
    soft = _surname_variants(surname_tokens)
    soft.update(_surname_variants(_tokenize_slug(player_slug)))
    strong = _make_strong_keys(soft, initial)
    return strong, soft


def _oncourt_player_keys(player_name: str) -> tuple[set[str], set[str]]:
    surname_tokens, initial = _parse_oncourt_name(player_name)
    soft = _surname_variants(surname_tokens)
    strong = _make_strong_keys(soft, initial)
    return strong, soft


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _coerce_today(today: str | date | None) -> date:
    if isinstance(today, date):
        return today
    if isinstance(today, str):
        parsed = _parse_iso_date(today)
        if parsed is not None:
            return parsed
    return datetime.now(timezone.utc).date()


@dataclass
class RecentInjuryIndex:
    csv_path: Path
    lookback_days: int
    rows_loaded: int = 0
    rows_recent: int = 0
    strong_keys: set[str] = field(default_factory=set)
    soft_counts: Counter[str] = field(default_factory=Counter)

    def match_name(self, player_name: str) -> tuple[bool, str]:
        strong, soft = _oncourt_player_keys(player_name)
        for key in strong:
            if key in self.strong_keys:
                return True, "strong"
        for key in soft:
            if self.soft_counts.get(key, 0) == 1:
                return True, "soft_unique"
        return False, "none"


def load_recent_injury_index(
    csv_path: str | Path,
    *,
    lookback_days: int = 14,
    today: str | date | None = None,
    include_sources: tuple[str, ...] = ("injured",),
) -> RecentInjuryIndex:
    idx = RecentInjuryIndex(csv_path=Path(csv_path), lookback_days=max(0, int(lookback_days or 0)))
    if not idx.csv_path.exists():
        return idx

    include = {s.strip().lower() for s in include_sources if s}
    today_d = _coerce_today(today)

    with idx.csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            idx.rows_loaded += 1
            src = (row.get("source") or "").strip().lower()
            if include and src not in include:
                continue
            rd = _parse_iso_date(row.get("date"))
            if rd is None:
                continue
            delta = (today_d - rd).days
            if delta < 0 or delta > idx.lookback_days:
                continue
            strong_keys, soft_keys = _te_row_keys(row.get("player_name") or "", row.get("player_slug") or "")
            if not strong_keys and not soft_keys:
                continue
            idx.rows_recent += 1
            idx.strong_keys.update(strong_keys)
            for sk in soft_keys:
                idx.soft_counts[sk] += 1
    return idx

