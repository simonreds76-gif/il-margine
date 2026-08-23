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

CONTROL_ODDS_FIELDS = [
    "captured_at",
    "match_date",
    "event_id",
    "kickoff_at",
    "snapshot_kind",
    "bookmaker",
    "competition",
    "home_team",
    "away_team",
    "market",
    "line",
    "side",
    "odds_decimal",
    "source",
    "notes",
]

THREE_WAY_MARKET_TOKENS = (
    "fulltime result",
    "full time result",
    "match result",
    "match odds",
    "match winner",
    "1x2",
    "3way",
    "three way",
    "moneyline",
    "money line",
    "to win match",
    "90 minutes",
    "win draw win",
)


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

    if text == "ml" or any(token in text for token in THREE_WAY_MARKET_TOKENS):
        return "match_odds"
    if "corner" in text:
        return "corners_control"
    if "shot" in text:
        return "shots_control"
    return "other"


def _float_price(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 1.0 else None


def _decimal_price(prop: dict) -> float | None:
    for key in ("odds", "value", "price", "decimal", "back"):
        try:
            value = float(prop.get(key))
        except (TypeError, ValueError):
            continue
        if value > 1.0:
            return value
    return None


def _direct_three_way_prices(container: dict) -> dict[str, float]:
    aliases = {
        "home": ("home", "1"),
        "draw": ("draw", "tie", "x"),
        "away": ("away", "2"),
    }
    prices: dict[str, float] = {}
    for side, keys in aliases.items():
        for key in keys:
            value = container.get(key)
            price = _decimal_price(value) if isinstance(value, dict) else _float_price(value)
            if price is not None:
                prices[side] = price
                break
    return prices


def _three_way_prices(market: dict, home_team: str, away_team: str) -> dict[str, float]:
    prices = _direct_three_way_prices(market)
    home_key = normalize_market_name(home_team)
    away_key = normalize_market_name(away_team)
    for prop in market.get("odds") or []:
        prices.update(_direct_three_way_prices(prop))
        price = _decimal_price(prop)
        if price is None:
            continue
        label = normalize_market_name(prop.get("label") or prop.get("name"))
        if label in {"1", "home", home_key} or (home_key and home_key in label):
            prices["home"] = price
        elif label in {"x", "draw", "tie"}:
            prices["draw"] = price
        elif label in {"2", "away", away_key} or (away_key and away_key in label):
            prices["away"] = price
    return prices


def _line_price_rows(market: dict) -> list[tuple[float, str, float]]:
    rows: list[tuple[float, str, float]] = []
    market_name = str(market.get("name") or "")
    market_line_match = re.search(r"(\d+(?:\.\d+)?)", market_name)
    for prop in market.get("odds") or []:
        try:
            hdp = float(prop.get("hdp"))
        except (TypeError, ValueError):
            hdp = None
        if hdp is not None:
            found = False
            for side in ("over", "under"):
                price = _float_price(prop.get(side))
                if price is not None:
                    rows.append((hdp, side, price))
                    found = True
            if found:
                continue

        label = str(prop.get("label") or prop.get("name") or "").strip()
        price = _decimal_price(prop)
        if price is None:
            continue
        line_match = re.search(r"(\d+(?:\.\d+)?)", label) or market_line_match
        if not line_match:
            continue
        lower = label.lower()
        side = "over" if "over" in lower else "under" if "under" in lower else ""
        if side:
            rows.append((float(line_match.group(1)), side, price))
    return rows


def build_control_odds_rows(
    payload: Iterable[dict],
    competition: str,
    captured_at: str,
) -> list[dict]:
    """Extract reusable count-market controls from an already-fetched payload."""
    rows: list[dict] = []
    for event in payload:
        event_id = str(event.get("id") or "")
        kickoff = str(event.get("date") or "")
        home_team = str(event.get("home") or "")
        away_team = str(event.get("away") or "")
        for bookmaker, markets in (event.get("bookmakers") or {}).items():
            for market in markets or []:
                market_name = str(market.get("name") or "").strip()
                normalized = normalize_market_name(market_name)
                category = classify_market(market_name)
                base = {
                    "captured_at": captured_at,
                    "match_date": kickoff[:10],
                    "event_id": event_id,
                    "kickoff_at": kickoff,
                    "snapshot_kind": "live_capture",
                    "bookmaker": str(bookmaker or ""),
                    "competition": competition,
                    "home_team": home_team,
                    "away_team": away_team,
                    "source": "odds_api_io",
                    "notes": f"market={market_name}",
                }
                if category == "match_odds" and normalized != "ml ht":
                    prices = _three_way_prices(market, home_team, away_team)
                    for side in ("home", "draw", "away"):
                        if side in prices:
                            rows.append(
                                {
                                    **base,
                                    "market": "MATCH_ODDS",
                                    "line": "",
                                    "side": side,
                                    "odds_decimal": f"{prices[side]:.4f}",
                                }
                            )
                    continue

                # Odds-API.io serves the legacy label through 2026-09-05.
                # Keep both names so match-total shot history remains continuous.
                if normalized in {"match shots", "total shots"}:
                    output_market = "MATCH_SHOTS"
                elif normalized == "corners totals":
                    output_market = "MATCH_CORNERS"
                elif normalized == "alternative corners":
                    output_market = "MATCH_CORNERS_ALT"
                else:
                    continue
                for line, side, price in _line_price_rows(market):
                    rows.append(
                        {
                            **base,
                            "market": output_market,
                            "line": f"{line:g}",
                            "side": side,
                            "odds_decimal": f"{price:.4f}",
                        }
                    )
    return rows


def append_control_odds_rows(path: Path, rows: Iterable[dict]) -> int:
    incoming = list(rows)
    if not incoming:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    key_fields = ("captured_at", "event_id", "bookmaker", "market", "line", "side")
    existing_keys: set[tuple[str, ...]] = set()
    if path.exists():
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                existing_keys.add(tuple(str(row.get(field) or "") for field in key_fields))
    mode = "a" if path.exists() and path.stat().st_size else "w"
    added = 0
    with path.open(mode, newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CONTROL_ODDS_FIELDS, extrasaction="ignore", lineterminator="\n")
        if mode == "w":
            writer.writeheader()
        for row in incoming:
            key = tuple(str(row.get(field) or "") for field in key_fields)
            if key in existing_keys:
                continue
            writer.writerow(row)
            existing_keys.add(key)
            added += 1
    return added


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
