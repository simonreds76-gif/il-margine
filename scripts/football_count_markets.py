from __future__ import annotations

import csv
import html
import re
import unicodedata
from pathlib import Path
from typing import Iterable


INVENTORY_FIELDS = [
    "captured_at",
    "event_id",
    "kickoff_at",
    "bookmaker",
    "competition",
    "home_team",
    "away_team",
    "market_name",
    "market_category",
    "odds_count",
    "line_count",
    "paired_line_count",
    "sample_labels",
]


def normalize_market_name(value: object) -> str:
    text = html.unescape(str(value or "").strip().lower())
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def classify_market(name: object) -> str:
    """Classify provider labels conservatively; unknown settlement scopes stay separate."""
    text = normalize_market_name(name)
    is_player = "player" in text
    is_team = "team" in text or " home" in f" {text}" or " away" in f" {text}"
    is_non_total = any(token in text for token in ("spread", "handicap", "most "))

    if "foul" in text:
        if is_player and "to be fouled" in text:
            return "player_fouled"
        if is_player:
            return "player_fouls_committed"
        if is_team and not is_non_total:
            return "team_fouls_total"
        if any(token in text for token in ("total", "number", "in match")) and not is_non_total:
            return "match_fouls_total"
        return "fouls_other"

    if "card" in text or "booking" in text:
        if is_player:
            return "player_cards"
        if is_team and not is_non_total:
            return "team_cards_total"
        if any(token in text for token in ("total", "number", "in match")) and not is_non_total:
            return "match_cards_total"
        return "cards_other"

    if "save" in text or "saves" in text:
        if "goalkeeper" in text or is_player:
            return "player_saves"
        if is_team and not is_non_total:
            return "team_saves_total"
        return "saves_other"

    if "corner" in text:
        return "corners_control"
    if "shot" in text:
        return "shots_control"
    return "other"


def _decimal_price(prop: dict) -> float | None:
    for key in ("odds", "value", "price", "decimal", "back"):
        try:
            value = float(prop.get(key))
        except (TypeError, ValueError):
            continue
        if value > 1.0:
            return value
    return None


def market_line_sides(market: dict) -> dict[float, set[str]]:
    """Return observed over/under sides by line for the two Odds-API.io shapes."""
    sides_by_line: dict[float, set[str]] = {}
    market_name = str(market.get("name") or "")
    market_line_match = re.search(r"(\d+(?:\.\d+)?)", market_name)

    for prop in market.get("odds") or []:
        try:
            hdp = float(prop.get("hdp"))
        except (TypeError, ValueError):
            hdp = None
        if hdp is not None:
            for side in ("over", "under"):
                try:
                    price = float(prop.get(side))
                except (TypeError, ValueError):
                    continue
                if price > 1.0:
                    sides_by_line.setdefault(hdp, set()).add(side)
            if hdp in sides_by_line:
                continue

        label = str(prop.get("label") or prop.get("name") or "").strip()
        if _decimal_price(prop) is None:
            continue
        label_line_match = re.search(r"(\d+(?:\.\d+)?)", label)
        line_match = label_line_match or market_line_match
        if not line_match:
            continue
        lower = label.lower()
        side = "over" if "over" in lower else "under" if "under" in lower else ""
        if side:
            sides_by_line.setdefault(float(line_match.group(1)), set()).add(side)
    return sides_by_line


def _sample_labels(market: dict) -> str:
    labels: list[str] = []
    for prop in (market.get("odds") or [])[:8]:
        label = str(prop.get("label") or prop.get("name") or "").strip()
        if label:
            labels.append(label)
            continue
        if prop.get("hdp") is not None:
            sides = [side.title() for side in ("over", "under") if prop.get(side) is not None]
            if sides:
                labels.append(f"{'/'.join(sides)} {prop.get('hdp')}")
    return " | ".join(labels)


def build_market_inventory_rows(
    payload: Iterable[dict],
    competition: str,
    captured_at: str,
) -> list[dict]:
    rows: list[dict] = []
    for event in payload:
        for bookmaker, markets in (event.get("bookmakers") or {}).items():
            for market in markets or []:
                market_name = str(market.get("name") or "").strip()
                line_sides = market_line_sides(market)
                rows.append(
                    {
                        "captured_at": captured_at,
                        "event_id": str(event.get("id") or ""),
                        "kickoff_at": str(event.get("date") or ""),
                        "bookmaker": str(bookmaker or ""),
                        "competition": competition,
                        "home_team": str(event.get("home") or ""),
                        "away_team": str(event.get("away") or ""),
                        "market_name": market_name,
                        "market_category": classify_market(market_name),
                        "odds_count": len(market.get("odds") or []),
                        "line_count": len(line_sides),
                        "paired_line_count": sum(
                            1 for sides in line_sides.values() if {"over", "under"}.issubset(sides)
                        ),
                        "sample_labels": _sample_labels(market),
                    }
                )
    return rows


def append_market_inventory(path: Path, rows: Iterable[dict]) -> int:
    incoming = list(rows)
    if not incoming:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_keys: set[tuple[str, ...]] = set()
    if path.exists():
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                existing_keys.add(
                    tuple(str(row.get(field) or "") for field in ("captured_at", "event_id", "bookmaker", "market_name"))
                )

    mode = "a" if path.exists() and path.stat().st_size else "w"
    added = 0
    with path.open(mode, newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=INVENTORY_FIELDS, extrasaction="ignore")
        if mode == "w":
            writer.writeheader()
        for row in incoming:
            key = tuple(str(row.get(field) or "") for field in ("captured_at", "event_id", "bookmaker", "market_name"))
            if key in existing_keys:
                continue
            writer.writerow(row)
            existing_keys.add(key)
            added += 1
    return added
