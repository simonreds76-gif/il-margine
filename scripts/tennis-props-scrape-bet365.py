#!/usr/bin/env python3
"""Scrape Bet365 tennis props/side-market lines from odds-api.io.

This is intentionally narrow and credit-conscious:
  - tennis only
  - Bet365 by default
  - optional --max-events cap
  - outputs the same inbox format consumed by tennis-props-compare-bet365.py

The odds-api.io tennis market naming is not guaranteed, so the parser accepts
several common shapes and writes a market-audit CSV when requested. Aces,
double faults and service breaks are priced by the comparison layer; other
side markets are retained as evidence where supported.
"""

from __future__ import annotations

import argparse
import csv
import html
import os
import re
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "https://api.odds-api.io/v3"
OUT_DIR = ROOT / "data" / "tennis-props" / "inbox"
DEFAULT_BOOKMAKERS = "Bet365"
BREAK_MARKETS = {"player_breaks", "match_breaks"}
BREAK_POINT_MARKETS = {"player_break_points", "match_break_points"}
SUPPORTED_TOURNAMENT_KEYWORDS = (
    ("Roland Garros", ("roland garros", "french open")),
    ("Wimbledon", ("wimbledon",)),
    ("Australian Open", ("australian open",)),
    ("US Open", ("us open", "u.s. open")),
    ("Hertogenbosch", ("hertogenbosch", "s hertogenbosch", "'s hertogenbosch", "rosmalen", "libema open")),
    ("Queen's Club", ("queen s", "queens", "queen's", "queen's club", "hsbc championships", "lta london championships", "cinch championships")),
    ("Stuttgart", ("stuttgart", "boss open", "porsche tennis grand prix")),
    ("Halle", ("halle", "terra wortmann", "gerry weber")),
    ("Nottingham", ("nottingham",)),
    ("Berlin", ("berlin", "bett1open", "bett1 open")),
    ("Eastbourne", ("eastbourne",)),
    ("Bad Homburg", ("bad homburg",)),
    ("Bastad", ("bastad", "båstad", "nordea open")),
    ("Gstaad", ("gstaad", "swiss open")),
    ("Umag", ("umag", "croatia open")),
    ("Estoril", ("estoril",)),
    ("Kitzbuhel", ("kitzbuhel", "kitzbühel")),
)
LOWER_TIER_KEYWORDS = (
    "challenger",
    "itf",
    "utr",
    "junior",
    "juniors",
    "boys",
    "girls",
    "wta 125",
    "wta 125k",
    "doubles",
)
ZERO_ROW_PROBE_PARAMS: tuple[tuple[str, dict[str, str]], ...] = (
    ("baseline", {}),
    ("markets=Player Props", {"markets": "Player Props"}),
    ("markets=player_props", {"markets": "player_props"}),
    ("market=player_props", {"market": "player_props"}),
    ("markets=Player Aces", {"markets": "Player Aces"}),
    ("markets=Aces", {"markets": "Aces"}),
    ("markets=Player Double Faults", {"markets": "Player Double Faults"}),
    ("markets=Double Faults", {"markets": "Double Faults"}),
    ("markets=Tie Break in Match", {"markets": "Tie Break in Match"}),
    ("markets=Tie-Break in Match", {"markets": "Tie-Break in Match"}),
    ("markets=Match Tie Break", {"markets": "Match Tie Break"}),
    ("markets=Match Tie-Break", {"markets": "Match Tie-Break"}),
    ("markets=Tie Break in 1st Set", {"markets": "Tie Break in 1st Set"}),
    ("markets=Tie-Break in 1st Set", {"markets": "Tie-Break in 1st Set"}),
    ("markets=1st Set Tie Break", {"markets": "1st Set Tie Break"}),
    ("markets=1st Set Tie-Break", {"markets": "1st Set Tie-Break"}),
    ("markets=First Set Tie Break", {"markets": "First Set Tie Break"}),
    ("markets=Set 1 Tie Break", {"markets": "Set 1 Tie Break"}),
    ("markets=1st Set Total Games", {"markets": "1st Set Total Games"}),
    ("markets=First Set Total Games", {"markets": "First Set Total Games"}),
    ("markets=Set 1 Total Games", {"markets": "Set 1 Total Games"}),
    ("markets=Total Games 1st Set", {"markets": "Total Games 1st Set"}),
    ("markets=Total Tie Breaks", {"markets": "Total Tie Breaks"}),
    ("include=all", {"include": "all"}),
    ("include=all;markets=player_props", {"include": "all", "markets": "player_props"}),
    ("include=all;markets=Tie Break in Match", {"include": "all", "markets": "Tie Break in Match"}),
    ("include=all;markets=1st Set Total Games", {"include": "all", "markets": "1st Set Total Games"}),
    ("hide_main_liner=false;markets=player_props", {"hide_main_liner": "false", "markets": "player_props"}),
    ("source=bet365", {"source": "bet365"}),
)
OUTPUT_FIELDS = [
    "event_id",
    "date",
    "tour",
    "tournament",
    "bookmaker",
    "player",
    "opponent",
    "market",
    "line",
    "over_odds",
    "under_odds",
    "capture_ts",
    "match_start_utc",
    "raw_market_name",
    "raw_outcome_count",
    "raw_label_sample",
]
AUDIT_FIELDS = [
    "captured_at",
    "event_id",
    "kickoff_at",
    "bookmaker",
    "league",
    "home",
    "away",
    "market_name",
    "odds_count",
    "sample_labels",
]


def load_env() -> None:
    for name in (".env.local", "env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip('"').strip("'")


def norm(value: object) -> str:
    text = html.unescape(str(value or "")).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def contains_keyword(text: str, keyword: str) -> bool:
    key = norm(keyword)
    if not key:
        return False
    return bool(re.search(rf"(?:^| ){re.escape(key)}(?: |$)", text))


def clean_player(value: object) -> str:
    text = html.unescape(str(value or "")).strip()
    if "," in text:
        last, first = text.split(",", 1)
        if last.strip() and first.strip():
            text = f"{first.strip()} {last.strip()}"
    text = re.sub(r"\s*\(\d+\)\s*", " ", text)
    text = re.sub(
        r"\b(over|under|aces?|double faults?|dfs?|df|break points?|service breaks?|breaks?)\b",
        " ",
        text,
        flags=re.I,
    )
    text = re.sub(r"\d+\.?\d*", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -:|")


def parse_decimal(value: object) -> float | None:
    if value is None:
        return None
    try:
        val = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return val if val > 1.0 else None


def parse_line(*values: object) -> float | None:
    for value in values:
        text = str(value or "")
        m = re.search(r"(\d+\.5|\d+)", text)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                continue
    return None


def identify_market(name: str) -> str | None:
    text = norm(name)
    has_first_set = any(token in text for token in ("1st set", "first set", "set 1"))
    if "tie break" in text or "tiebreak" in text:
        if "total" in text:
            return "total_tiebreaks"
        return "first_set_tiebreak" if has_first_set else "match_tiebreak"
    if "break point" in text:
        if has_first_set:
            return None
        if "team total" in text or "player total" in text:
            return "player_break_points"
        if "total" in text:
            return "match_break_points"
        return "player_break_points"
    if "break" in text:
        if "team total" in text or "player total" in text:
            return "player_breaks"
        if "total" in text:
            return "match_breaks"
        return "player_breaks"
    if has_first_set and "total" in text and "game" in text:
        return "first_set_total_games"
    if "double fault" in text or re.search(r"\bdfs?\b", text):
        return "double_faults"
    if "ace" in text and "race" not in text:
        return "aces"
    return None


def is_yes_no_market(market_key: str) -> bool:
    return market_key in {"match_tiebreak", "first_set_tiebreak"}


def side_from_label(label: object, *, yes_no: bool) -> str | None:
    text = norm(label)
    tokens = set(text.split())
    if yes_no:
        if "yes" in tokens or text in {"y", "true"}:
            return "over_odds"
        if "no" in tokens or text in {"n", "false"}:
            return "under_odds"
    if "over" in tokens:
        return "over_odds"
    if "under" in tokens:
        return "under_odds"
    return None


BAD_PLAYER_NAMES = {"total", "totals", "player total", "player totals", "totals player", "totals players"}


def is_bad_player_name(value: str) -> bool:
    cleaned = norm(value)
    return (not cleaned) or cleaned in BAD_PLAYER_NAMES or cleaned.startswith("totals")


def real_event_players(home: str, away: str) -> list[str]:
    players: list[str] = []
    for raw in (home, away):
        cleaned = clean_player(raw)
        if cleaned and not is_bad_player_name(cleaned):
            players.append(cleaned)
    return players


def opponent_for(player: str, home: str, away: str) -> str:
    p = norm(player)
    home_clean = clean_player(home)
    away_clean = clean_player(away)
    home_norm = norm(home_clean)
    away_norm = norm(away_clean)
    if p and (p == home_norm or p in home_norm or home_norm in p):
        return "" if is_bad_player_name(away_clean) else away_clean
    if p and (p == away_norm or p in away_norm or away_norm in p):
        return "" if is_bad_player_name(home_clean) else home_clean
    real_players = [name for name in real_event_players(home, away) if norm(name) != p]
    return real_players[0] if len(real_players) == 1 else ""


def player_from_text(text: object, home: str, away: str) -> str:
    haystack = norm(text)
    if not haystack:
        return ""
    hay_tokens = set(haystack.split())
    matches: list[str] = []
    for raw_name in (home, away):
        name = clean_player(raw_name)
        if is_bad_player_name(name):
            continue
        name_norm = norm(name)
        if not name_norm:
            continue
        tokens = name_norm.split()
        last = tokens[-1] if tokens else ""
        first = tokens[0] if tokens else ""
        exact = name_norm in haystack or haystack in name_norm
        token_match = bool(last and last in hay_tokens and (first in hay_tokens or len(last) >= 6))
        if exact or token_match:
            matches.append(name)
    unique = []
    for match in matches:
        if norm(match) not in {norm(item) for item in unique}:
            unique.append(match)
    return unique[0] if len(unique) == 1 else ""


def resolve_prop_player(prop: dict[str, Any], label: str, market_name: str, home: str, away: str, *, match_level_market: bool) -> str:
    real_players = real_event_players(home, away)
    if match_level_market:
        return real_players[0] if real_players else ""
    if len(real_players) == 1:
        # odds-api.io exposes some Bet365 player props as "Totals ( ) v Player".
        # In that shape the only real participant is the prop player.
        return real_players[0]
    raw_candidates = [
        prop.get("player"),
        prop.get("participant"),
        prop.get("competitor"),
        prop.get("runner"),
        prop.get("team"),
        label,
        market_name,
        f"{market_name} {label}",
    ]
    for raw in raw_candidates:
        inferred = player_from_text(raw, home, away)
        if inferred:
            return inferred
        cleaned = clean_player(raw)
        if is_bad_player_name(cleaned):
            continue
        cleaned_norm = norm(cleaned)
        if cleaned_norm in {norm(clean_player(home)), norm(clean_player(away))}:
            return cleaned
    return ""


def tour_from_event(event: dict[str, Any]) -> str:
    league = norm((event.get("league") or {}).get("name") or event.get("league") or "")
    haystack = " ".join(
        [
            league,
            norm(event.get("home")),
            norm(event.get("away")),
            norm(event.get("name")),
        ]
    )
    if "wta" in haystack or "women" in haystack:
        return "WTA"
    return "ATP"


def tournament_from_event(event: dict[str, Any]) -> str:
    league = str((event.get("league") or {}).get("name") or event.get("league") or "").strip()
    haystack = norm(f"{league} {event.get('name') or ''} {event.get('home') or ''} {event.get('away') or ''}")
    for tournament, keywords in SUPPORTED_TOURNAMENT_KEYWORDS:
        if any(contains_keyword(haystack, keyword) for keyword in keywords):
            return tournament
    main_tour_match = re.match(r"^(?:ATP|WTA)\s*-\s*([^,]+)", league, flags=re.I)
    if main_tour_match:
        return main_tour_match.group(1).strip()
    return league or "Tennis"


def event_text(event: dict[str, Any]) -> str:
    league = str((event.get("league") or {}).get("name") or event.get("league") or "")
    return " ".join(
        [
            league,
            str(event.get("name") or ""),
            str(event.get("home") or ""),
            str(event.get("away") or ""),
        ]
    ).lower()


def is_supported_tournament_event(event: dict[str, Any]) -> bool:
    """Keep ATP/WTA tour events and reject lower-tier feeds.

    The previous seasonal tournament whitelist silently discarded every event
    after the grass swing and also admitted Challenger events whose city name
    matched a main-tour tournament. The provider league is the durable tier
    signal; the keyword table is now only for canonical tournament naming.
    """
    league = str((event.get("league") or {}).get("name") or event.get("league") or "")
    league_text = norm(league)
    full_text = norm(event_text(event))
    if any(contains_keyword(full_text, keyword) for keyword in LOWER_TIER_KEYWORDS):
        return False
    return contains_keyword(league_text, "atp") or contains_keyword(league_text, "wta")


def is_singles_event(event: dict[str, Any]) -> bool:
    home = str(event.get("home") or event.get("home_team") or "")
    away = str(event.get("away") or event.get("away_team") or "")
    return "/" not in home and "/" not in away


def extract_rows(event: dict[str, Any], bookmaker: str, market: dict[str, Any], captured_at: str = "") -> list[dict[str, str]]:
    market_name = str(market.get("name") or "")
    market_key = identify_market(market_name)
    if not market_key and "player prop" in norm(market_name):
        # The normalized odds-api.io feed now combines every statistic under
        # one Player Props market. Split its mixed outcomes back into the
        # count-market shapes consumed by the existing comparison layer.
        rows: list[dict[str, str]] = []
        synthetic_names = {
            "aces": "Player Aces",
            "double_faults": "Player Double Faults",
            "player_breaks": "Player Service Breaks",
            "player_break_points": "Player Break Points",
        }
        for prop in market.get("odds") or market.get("outcomes") or []:
            prop_text = " ".join(
                str(prop.get(key) or "")
                for key in ("label", "name", "stat", "market", "description")
            )
            prop_key = identify_market(prop_text)
            synthetic_name = synthetic_names.get(prop_key or "")
            if synthetic_name:
                rows.extend(
                    extract_rows(
                        event,
                        bookmaker,
                        {"name": synthetic_name, "odds": [prop]},
                        captured_at=captured_at,
                    )
                )
        return rows
    if not market_key:
        return []

    kickoff = str(event.get("date") or "")
    event_id = str(event.get("id") or "")
    event_date = kickoff[:10]
    home = str(event.get("home") or event.get("home_team") or "")
    away = str(event.get("away") or event.get("away_team") or "")
    tour = tour_from_event(event)
    tournament = tournament_from_event(event)
    grouped: dict[tuple[str, str, str], dict[str, float]] = defaultdict(dict)
    raw_labels: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    yes_no_market = is_yes_no_market(market_key)
    real_players = real_event_players(home, away)
    market_text = norm(market_name)
    is_team_count_total = (
        market_key in {"aces", "double_faults", "player_breaks", "player_break_points"}
        and "team total" in market_text
    )
    is_match_count_total = (
        (
            market_key in {"aces", "double_faults"}
            and "total" in market_text
            and not is_team_count_total
        )
        or market_key in {"match_breaks", "match_break_points"}
    ) and len(real_players) == 2
    output_market = (
        "match_aces"
        if is_match_count_total and market_key == "aces"
        else "match_double_faults"
        if is_match_count_total and market_key == "double_faults"
        else "match_breaks"
        if is_match_count_total and market_key == "match_breaks"
        else "match_break_points"
        if is_match_count_total and market_key == "match_break_points"
        else market_key
    )
    match_level_market = (
        yes_no_market
        or market_key in {"first_set_total_games", "total_tiebreaks"}
        or is_match_count_total
    )
    match_player = clean_player(home)
    match_opponent = clean_player(away)

    for prop in market.get("odds") or market.get("outcomes") or []:
        label = str(prop.get("label") or prop.get("name") or "").strip()
        line = None if yes_no_market else parse_line(prop.get("hdp"), prop.get("point"), label, market_name)
        line_text = "" if line is None else f"{line:.1f}"
        if line is None and not yes_no_market:
            continue

        # Shape A: one prop carries both sides. odds-api.io uses home/away
        # for Bet365 tennis totals, where home == Over/Yes and away == Under/No.
        home_side_price = parse_decimal(prop.get("home"))
        away_side_price = parse_decimal(prop.get("away"))
        over_price = parse_decimal(prop.get("over")) or (None if yes_no_market else home_side_price)
        under_price = parse_decimal(prop.get("under")) or (None if yes_no_market else away_side_price)
        yes_price = parse_decimal(prop.get("yes") or prop.get("Yes")) or (home_side_price if yes_no_market else None)
        no_price = parse_decimal(prop.get("no") or prop.get("No")) or (away_side_price if yes_no_market else None)
        if is_team_count_total and market_text.endswith(" away"):
            player_name = clean_player(away)
        elif is_team_count_total and market_text.endswith(" home"):
            player_name = clean_player(home)
        else:
            player_name = resolve_prop_player(
                prop,
                label,
                market_name,
                home,
                away,
                match_level_market=match_level_market,
            )
        if over_price or under_price:
            if not player_name:
                continue
            opponent = match_opponent if match_level_market else opponent_for(player_name, home, away)
            key = (player_name, opponent, line_text)
            raw_labels[key].append(label or str(prop)[:90])
            if over_price:
                grouped[key]["over_odds"] = over_price
            if under_price:
                grouped[key]["under_odds"] = under_price
            continue
        if yes_price or no_price:
            if not player_name:
                continue
            key = (player_name, match_opponent, line_text)
            raw_labels[key].append(label or str(prop)[:90])
            if yes_price:
                grouped[key]["over_odds"] = yes_price
            if no_price:
                grouped[key]["under_odds"] = no_price
            continue

        # Shape B: one prop per side.
        price = None
        for price_key in ("odds", "value", "price", "decimal", "back"):
            price = parse_decimal(prop.get(price_key))
            if price is not None:
                break
        if price is None:
            continue

        side = side_from_label(label, yes_no=yes_no_market)
        if side is None:
            continue
        player_name = resolve_prop_player(prop, label, market_name, home, away, match_level_market=match_level_market)
        if not player_name:
            continue
        opponent = match_opponent if match_level_market else opponent_for(player_name, home, away)
        key = (player_name, opponent, line_text)
        raw_labels[key].append(label or str(prop)[:90])
        grouped[key][side] = price

    rows: list[dict[str, str]] = []
    for (player, opponent, line_text), prices in grouped.items():
        if not prices.get("over_odds") and not prices.get("under_odds"):
            continue
        rows.append(
            {
                "event_id": event_id,
                "date": event_date,
                "tour": tour,
                "tournament": tournament,
                "bookmaker": bookmaker,
                "player": player,
                "opponent": clean_player(opponent),
                "market": output_market,
                "line": line_text,
                "over_odds": f"{prices['over_odds']:.4f}" if prices.get("over_odds") else "",
                "under_odds": f"{prices['under_odds']:.4f}" if prices.get("under_odds") else "",
                "capture_ts": captured_at,
                "match_start_utc": kickoff,
                "raw_market_name": market_name,
                "raw_outcome_count": str(len(market.get("odds") or market.get("outcomes") or [])),
                "raw_label_sample": " | ".join(raw_labels.get((player, opponent, line_text), [])[:4]),
            }
        )
    return rows


def fetch_json(path: str, params: dict[str, Any]) -> Any:
    response = requests.get(f"{BASE_URL}/{path.lstrip('/')}", params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_multi(
    api_key: str,
    event_ids: list[str],
    bookmakers: str,
    *,
    markets: str = "",
) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for i in range(0, len(event_ids), 10):
        chunk = event_ids[i : i + 10]
        params = {"apiKey": api_key, "eventIds": ",".join(chunk), "bookmakers": bookmakers}
        if markets:
            params["markets"] = markets
        data = fetch_json(
            "odds/multi",
            params,
        )
        if isinstance(data, list):
            payload.extend(data)
        time.sleep(0.35)
    return payload


def has_supported_count_rows(event: dict[str, Any]) -> bool:
    return event_has_market_rows(event)


def event_has_market_rows(
    event: dict[str, Any],
    requested_markets: set[str] | None = None,
) -> bool:
    for bookmaker, market_payloads in (event.get("bookmakers") or {}).items():
        for market_payload in market_payloads or []:
            rows = extract_rows(event, bookmaker, market_payload)
            if rows and (
                requested_markets is None
                or any(str(row.get("market") or "").lower() in requested_markets for row in rows)
            ):
                return True
    return False


def dedupe_snapshot_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Collapse default and explicit Player Props responses to one priced line."""
    by_key: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        key = tuple(
            str(row.get(field) or "").strip().lower()
            for field in ("event_id", "bookmaker", "player", "opponent", "market", "line")
        )
        current = by_key.get(key)
        if current is None:
            by_key[key] = dict(row)
            continue
        current_sides = int(bool(current.get("over_odds"))) + int(bool(current.get("under_odds")))
        new_sides = int(bool(row.get("over_odds"))) + int(bool(row.get("under_odds")))
        if new_sides > current_sides:
            by_key[key] = dict(row)
            continue
        for field in ("over_odds", "under_odds", "raw_label_sample"):
            if not current.get(field) and row.get(field):
                current[field] = row[field]
    return list(by_key.values())


def summarize_market_names(data: Any) -> str:
    if isinstance(data, dict):
        events = [data]
    elif isinstance(data, list):
        events = data
    else:
        return f"unexpected:{type(data).__name__}"

    counts: dict[str, int] = defaultdict(int)
    for event in events:
        for markets in (event.get("bookmakers") or {}).values():
            for market in markets or []:
                counts[str(market.get("name") or "<blank>")] += 1
    if not counts:
        return "none"
    return ", ".join(f"{name}:{count}" for name, count in sorted(counts.items()))


def probe_request(path: str, params: dict[str, Any]) -> tuple[int | str, str]:
    try:
        response = requests.get(f"{BASE_URL}/{path.lstrip('/')}", params=params, timeout=30)
    except requests.RequestException as exc:
        return "request_error", repr(exc)
    try:
        data: Any = response.json()
    except ValueError:
        data = response.text[:220]
    if response.status_code >= 400:
        if isinstance(data, dict):
            message = data.get("message") or data.get("error") or str(data)[:220]
        else:
            message = str(data)[:220]
        return response.status_code, message
    return response.status_code, summarize_market_names(data)


def run_zero_row_market_probe(api_key: str, events: list[dict[str, Any]], bookmakers: str) -> None:
    if not events:
        return
    primary_bookmaker = bookmakers.split(",")[0].strip()
    print("odds-api.io zero-row market probe:")

    populated_events = [
        candidate
        for candidate in events
        if (candidate.get("bookmakers") or {}).get(primary_bookmaker)
    ] or events[:1]
    probe_events: list[dict[str, Any]] = []
    for tour_marker in ("ATP", "WTA"):
        match = next(
            (
                candidate
                for candidate in populated_events
                if tour_marker in str((candidate.get("league") or {}).get("name") or candidate.get("league") or "")
            ),
            None,
        )
        if match and match not in probe_events:
            probe_events.append(match)
    if not probe_events:
        probe_events = populated_events[:1]

    bookmaker_variants = []
    for value in [primary_bookmaker, "Bet365", "bet365"]:
        if value and value not in bookmaker_variants:
            bookmaker_variants.append(value)

    for event in probe_events:
        event_id = str(event.get("id") or "")
        if not event_id:
            continue
        league = str((event.get("league") or {}).get("name") or event.get("league") or "")
        print(f"  event={event_id} | {league} | {event.get('home')} vs {event.get('away')}")

        for bookmaker in bookmaker_variants:
            labels = ZERO_ROW_PROBE_PARAMS if bookmaker == bookmaker_variants[0] else ZERO_ROW_PROBE_PARAMS[:3]
            print(f"  bookmaker_probe={bookmaker}")
            for label, extra in labels:
                params = {"apiKey": api_key, "eventId": event_id, "bookmakers": bookmaker}
                params.update(extra)
                status, summary = probe_request("odds", params)
                print(f"    /odds {label}: status={status}; markets={summary}")
                time.sleep(0.2)

        status, summary = probe_request(
            "odds/multi",
            {"apiKey": api_key, "eventIds": event_id, "bookmakers": bookmakers, "markets": "player_props"},
        )
        print(f"    /odds/multi markets=player_props: status={status}; markets={summary}")

    status, summary = probe_request(
        "value-bets",
        {
            "apiKey": api_key,
            "bookmaker": primary_bookmaker,
            "sport": "tennis",
            "includeEventDetails": "true",
            "limit": "20",
        },
    )
    print(f"    /value-bets tennis Bet365 sample: status={status}; markets={summary}")


def write_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def history_row_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(str(row.get(field) or "").strip() for field in OUTPUT_FIELDS)


def append_history_rows(path: Path, rows: list[dict[str, str]]) -> int:
    existing: list[dict[str, str]] = []
    if path.exists():
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            existing = [dict(row) for row in csv.DictReader(f)]
    seen = {history_row_key(row) for row in existing}
    added = 0
    for row in rows:
        key = history_row_key(row)
        if key in seen:
            continue
        seen.add(key)
        existing.append(row)
        added += 1
    write_rows(path, existing, OUTPUT_FIELDS)
    return added


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Bet365 tennis props/side-market lines from odds-api.io")
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--days-ahead", type=int, default=2)
    parser.add_argument("--bookmakers", default=DEFAULT_BOOKMAKERS)
    parser.add_argument("--max-events", type=int, default=64)
    parser.add_argument("--out", default="")
    parser.add_argument("--audit-out", default="")
    parser.add_argument("--history-out", default="")
    parser.add_argument("--probe-markets", action="store_true", help="Force endpoint/tier probes for hidden tennis markets")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_env()
    api_key = os.environ.get("ODDS_API_KEY") or os.environ.get("ODDS_API_IO_KEY")
    if not api_key:
        raise SystemExit("Set ODDS_API_KEY or ODDS_API_IO_KEY in .env.local to use odds-api.io.")

    now = datetime.now(timezone.utc)
    from_iso = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    to_iso = (now + timedelta(days=args.days_ahead)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    events = fetch_json(
        "events",
        {"apiKey": api_key, "sport": "tennis", "status": "pending", "from": from_iso, "to": to_iso},
    )
    if not isinstance(events, list):
        events = []

    raw_event_count = len(events)
    events = [event for event in events if is_supported_tournament_event(event) and is_singles_event(event)]
    events = events[: max(0, args.max_events)] if args.max_events else events
    print(f"odds-api.io tennis events returned: {raw_event_count}; supported singles selected: {len(events)}")
    selected_tournaments: dict[str, int] = defaultdict(int)
    for event in events:
        selected_tournaments[tournament_from_event(event)] += 1
    if selected_tournaments:
        print(
            "selected main-tour events: "
            + ", ".join(f"{name}={count}" for name, count in sorted(selected_tournaments.items()))
        )
    if not events:
        return

    event_ids = [str(event.get("id")) for event in events if event.get("id")]
    payload = fetch_multi(api_key, event_ids, args.bookmakers)
    break_event_ids = {
        str(event.get("id") or "")
        for event in payload
        if event_has_market_rows(event, BREAK_MARKETS)
    }
    missing_break_event_ids = [event_id for event_id in event_ids if event_id not in break_event_ids]
    if missing_break_event_ids:
        print(
            "service-break props absent from default payload; "
            f"requesting consolidated Player Props for {len(missing_break_event_ids)} event(s)"
        )
        payload.extend(
            fetch_multi(
                api_key,
                missing_break_event_ids,
                args.bookmakers,
                markets="Player Props",
            )
        )
    rows: list[dict[str, str]] = []
    audit_rows: list[dict[str, str]] = []
    captured_at = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    audited_event_ids: set[str] = set()
    for event in payload:
        for bookmaker, markets in (event.get("bookmakers") or {}).items():
            for market in markets or []:
                audited_event_ids.add(str(event.get("id") or ""))
                market_name = str(market.get("name") or "")
                odds_list = market.get("odds") or market.get("outcomes") or []
                labels = []
                for prop in odds_list[:6]:
                    bits = []
                    for key in ("label", "name", "player", "participant", "competitor", "runner", "team", "hdp", "point"):
                        value = prop.get(key)
                        if value not in (None, ""):
                            bits.append(f"{key}={value}")
                    labels.append(";".join(bits) or str(prop)[:120])
                audit_rows.append(
                    {
                        "captured_at": captured_at,
                        "event_id": str(event.get("id") or ""),
                        "kickoff_at": str(event.get("date") or ""),
                        "bookmaker": bookmaker,
                        "league": str((event.get("league") or {}).get("name") or event.get("league") or ""),
                        "home": str(event.get("home") or ""),
                        "away": str(event.get("away") or ""),
                        "market_name": market_name,
                        "odds_count": str(len(odds_list)),
                        "sample_labels": " | ".join(labels),
                    }
                )
                rows.extend(extract_rows(event, bookmaker, market, captured_at=captured_at))

    # A header-only audit hid whether discovery failed or the provider returned
    # no Bet365 payload. Preserve one explicit row per selected empty event.
    for event in events:
        event_id = str(event.get("id") or "")
        if event_id in audited_event_ids:
            continue
        audit_rows.append(
            {
                "captured_at": captured_at,
                "event_id": event_id,
                "kickoff_at": str(event.get("date") or ""),
                "bookmaker": args.bookmakers,
                "league": str((event.get("league") or {}).get("name") or event.get("league") or ""),
                "home": str(event.get("home") or ""),
                "away": str(event.get("away") or ""),
                "market_name": "<NO_BET365_MARKETS_RETURNED>",
                "odds_count": "0",
                "sample_labels": "",
            }
        )

    rows = dedupe_snapshot_rows(rows)
    out = Path(args.out) if args.out else OUT_DIR / f"bet365-lines-{args.date}.csv"
    audit_out = Path(args.audit_out) if args.audit_out else OUT_DIR / f"bet365-tennis-market-audit-{args.date}.csv"
    month = args.date[:7] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date) else now.strftime("%Y-%m")
    # Keep this under the workflow's existing bet365-lines-* commit pattern so
    # the golden data branch remains the only runtime branch dependency.
    history_out = Path(args.history_out) if args.history_out else OUT_DIR / f"bet365-lines-history-{month}.csv"
    print(f"parsed supported tennis market rows: {len(rows)}")
    # Diagnostic endpoint probes are intentionally manual. A normal zero-row
    # capture must remain inside the registered eight-request workflow ceiling.
    if args.probe_markets:
        run_zero_row_market_probe(api_key, payload or events, args.bookmakers)
    if args.dry_run:
        for row in rows[:20]:
            print(row)
        print(f"dry-run only; would write {out}")
        return
    write_rows(audit_out, audit_rows, AUDIT_FIELDS)
    if rows:
        write_rows(out, rows, OUTPUT_FIELDS)
        print(f"Saved lines: {out}")
        history_added = append_history_rows(history_out, rows)
        print(f"Price history: added {history_added}, file={history_out}")
    else:
        print("No supported tennis market rows parsed; skipped writing lines file.")
    print(f"Saved audit: {audit_out}")


if __name__ == "__main__":
    main()
