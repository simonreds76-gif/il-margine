"""Safe shared player-name resolution for tennis props pipelines."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class NameResolution:
    name: str
    method: str

    @property
    def resolved(self) -> bool:
        return self.method != "unresolved"


def norm_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def baseline_names_by_tour(
    baseline: Mapping[tuple[str, str, str], object],
) -> dict[str, set[str]]:
    names: dict[str, set[str]] = {}
    for tour, player_name, _surface in baseline:
        if tour and player_name:
            names.setdefault(tour.upper(), set()).add(player_name)
    return names


def resolve_baseline_name(
    *,
    tour: str,
    value: object,
    available_names: Mapping[str, set[str]],
    aliases: Mapping[tuple[str, str], str] | None = None,
) -> NameResolution:
    """Resolve a schedule name without accepting ambiguous fuzzy matches.

    OnCourt sometimes includes middle names while the historical baseline does
    not (for example, ``Taylor Harry Fritz`` vs ``Taylor Fritz``). Exact and
    explicit aliases remain preferred. The only automatic fallback requires a
    unique baseline player with the same first and last token.
    """
    tour_key = tour.upper()
    normalized = norm_name(value)
    candidates = available_names.get(tour_key, set())
    alias = (aliases or {}).get((tour_key, normalized))
    if alias:
        return NameResolution(alias, "explicit_alias" if alias in candidates else "unresolved")
    if normalized in candidates:
        return NameResolution(normalized, "exact")

    tokens = normalized.split()
    if len(tokens) >= 2:
        first_last = [
            candidate
            for candidate in candidates
            if len(candidate.split()) >= 2
            and candidate.split()[0] == tokens[0]
            and candidate.split()[-1] == tokens[-1]
        ]
        if len(first_last) == 1:
            return NameResolution(first_last[0], "unique_first_last")

    return NameResolution(normalized, "unresolved")
