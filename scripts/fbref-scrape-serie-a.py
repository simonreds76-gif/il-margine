"""
FBref Serie A player match-log scraper.

This is the first data-collection step for the goalscorer model. It pulls
per-player, per-match Serie A logs plus team match-level xG/xGA context.

Output:
  data/goalscorer/serie-a-player-match-logs-{season}.csv
"""

from __future__ import annotations

import argparse
import atexit
import csv
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

try:
    import requests
    from bs4 import BeautifulSoup, Comment
except ImportError:
    print("Install required packages:")
    print("  pip install requests beautifulsoup4")
    sys.exit(1)

try:
    from curl_cffi import requests as curl_requests

    HAS_CURL_CFFI = True
except ImportError:
    curl_requests = None
    HAS_CURL_CFFI = False

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    HAS_PLAYWRIGHT = True
except ImportError:
    PlaywrightTimeoutError = Exception
    sync_playwright = None
    HAS_PLAYWRIGHT = False


FBREF_BASE = "https://fbref.com"
SERIE_A_COMP_ID = 11
REQUEST_DELAY = 4.0
OUTPUT_DIR = "data/goalscorer"
MIN_SEASON_MINUTES = 90

AVAILABLE_SEASONS = [
    "2017-2018",
    "2018-2019",
    "2019-2020",
    "2020-2021",
    "2021-2022",
    "2022-2023",
    "2023-2024",
    "2024-2025",
    "2025-2026",
]

DEFAULT_SEASONS = ["2023-2024", "2024-2025", "2025-2026"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    )
}

TEAM_ALIASES = {
    "ac milan": "milan",
    "milan": "milan",
    "inter": "inter",
    "inter milan": "inter",
    "internazionale": "inter",
    "hellas verona": "verona",
    "verona": "verona",
    "juventus": "juventus",
    "juventus fc": "juventus",
    "as roma": "roma",
    "roma": "roma",
    "ss lazio": "lazio",
    "lazio": "lazio",
    "atalanta": "atalanta",
    "atalanta bc": "atalanta",
    "acf fiorentina": "fiorentina",
    "fiorentina": "fiorentina",
    "bologna": "bologna",
    "bologna fc 1909": "bologna",
    "cagliari": "cagliari",
    "cagliari calcio": "cagliari",
    "como": "como",
    "como 1907": "como",
    "empoli": "empoli",
    "empoli fc": "empoli",
    "genoa": "genoa",
    "genoa cfc": "genoa",
    "lecce": "lecce",
    "us lecce": "lecce",
    "monza": "monza",
    "ac monza": "monza",
    "napoli": "napoli",
    "ssc napoli": "napoli",
    "parma": "parma",
    "parma calcio 1913": "parma",
    "torino": "torino",
    "torino fc": "torino",
    "udinese": "udinese",
    "udinese calcio": "udinese",
    "venezia": "venezia",
    "venezia fc": "venezia",
}

_last_request_time = 0.0
FETCH_ENGINE = "auto"
_playwright_runtime = None
_playwright_browser = None
_playwright_context = None
_playwright_page = None


@dataclass
class Squad:
    squad_id: str
    squad_name: str
    squad_key: str


def _team_key(name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", (name or "").strip().lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return TEAM_ALIASES.get(cleaned, cleaned)


def _clean_text(el) -> str:
    if el is None:
        return ""
    return el.get_text(strip=True)


def _safe_float(value: str, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    text = str(value).replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _safe_int(value: str, default: Optional[int] = None) -> Optional[int]:
    if value is None:
        return default
    text = str(value).replace(",", "").strip()
    if not text:
        return default
    try:
        return int(float(text))
    except ValueError:
        return default


def _extract_fbref_id(href: str) -> str:
    parts = href.strip("/").split("/")
    for i, part in enumerate(parts):
        if part in {"squads", "players", "comps"} and i + 1 < len(parts):
            return parts[i + 1]
    return ""


def _unwrap_comment_tables(soup: BeautifulSoup) -> BeautifulSoup:
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        text = str(comment)
        if "<table" not in text:
            continue
        fragment = BeautifulSoup(text, "html.parser")
        tables = fragment.find_all("table")
        if not tables:
            continue
        insert_after = comment
        for table in tables:
            insert_after.insert_after(table)
            insert_after = table
        comment.extract()
    return soup


def _wait_for_rate_limit() -> None:
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)
    _last_request_time = time.time()


def _fetch_requests(url: str, timeout: int = 30):
    return requests.get(url, headers=HEADERS, timeout=timeout)


def _fetch_curl(url: str, timeout: int = 30):
    if not HAS_CURL_CFFI:
        raise RuntimeError("curl_cffi is not installed")
    return curl_requests.get(url, headers=HEADERS, timeout=timeout, impersonate="chrome124")


def _close_playwright() -> None:
    global _playwright_page, _playwright_context, _playwright_browser, _playwright_runtime
    try:
        if _playwright_page is not None:
            _playwright_page.close()
    except Exception:
        pass
    try:
        if _playwright_context is not None:
            _playwright_context.close()
    except Exception:
        pass
    try:
        if _playwright_browser is not None:
            _playwright_browser.close()
    except Exception:
        pass
    try:
        if _playwright_runtime is not None:
            _playwright_runtime.stop()
    except Exception:
        pass
    _playwright_page = None
    _playwright_context = None
    _playwright_browser = None
    _playwright_runtime = None


atexit.register(_close_playwright)


def _ensure_playwright_page():
    global _playwright_runtime, _playwright_browser, _playwright_context, _playwright_page
    if _playwright_page is not None:
        return _playwright_page

    if not HAS_PLAYWRIGHT:
        raise RuntimeError("playwright is not installed")

    _playwright_runtime = sync_playwright().start()
    browser_type = _playwright_runtime.chromium
    launch_errors = []
    for launch_kwargs in (
        {
            "channel": "chrome",
            "headless": False,
            "args": ["--disable-blink-features=AutomationControlled"],
        },
        {
            "channel": "chrome",
            "headless": True,
            "args": ["--disable-blink-features=AutomationControlled"],
        },
        {
            "headless": True,
            "args": ["--disable-blink-features=AutomationControlled"],
        },
    ):
        try:
            _playwright_browser = browser_type.launch(**launch_kwargs)
            break
        except Exception as exc:
            launch_errors.append(str(exc))
            _playwright_browser = None

    if _playwright_browser is None:
        raise RuntimeError(f"failed to launch browser: {' | '.join(launch_errors)}")

    _playwright_context = _playwright_browser.new_context(
        user_agent=HEADERS["User-Agent"],
        locale="en-GB",
        viewport={"width": 1440, "height": 900},
        extra_http_headers={
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
            "Upgrade-Insecure-Requests": "1",
        },
    )
    _playwright_page = _playwright_context.new_page()
    _playwright_page.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-GB', 'en-US', 'en'] });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
        window.chrome = window.chrome || { runtime: {} };
        """
    )
    return _playwright_page


def _fetch_playwright(url: str, timeout: int = 30):
    page = _ensure_playwright_page()
    timeout_ms = timeout * 1000
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        response = None
    page.wait_for_timeout(4000)
    title = ""
    try:
        title = page.title()
    except Exception:
        title = ""
    if "just a moment" in title.lower() or "attention required" in title.lower():
        page.wait_for_timeout(8000)
    html = page.content()

    status_code = response.status if response is not None else 200
    if "Access denied" in html or "Sorry, you have been blocked" in html:
        status_code = 403

    class SimpleResponse:
        def __init__(self, status_code: int, text: str):
            self.status_code = status_code
            self.text = text

    return SimpleResponse(status_code, html)


def fetch_page(url: str, retries: int = 3, engine: str = "auto") -> Optional[BeautifulSoup]:
    global _last_request_time

    fetchers = []
    if engine == "requests":
        fetchers = [("requests", _fetch_requests)]
    elif engine == "curl":
        fetchers = [("curl", _fetch_curl)]
    elif engine == "playwright":
        fetchers = [("playwright", _fetch_playwright)]
    else:
        fetchers = [("requests", _fetch_requests)]
        if HAS_CURL_CFFI:
            fetchers.append(("curl", _fetch_curl))
        if HAS_PLAYWRIGHT:
            fetchers.append(("playwright", _fetch_playwright))

    for attempt in range(retries):
        last_status = None
        had_retryable_error = False
        for fetcher_name, fetcher in fetchers:
            try:
                _wait_for_rate_limit()
                response = fetcher(url, timeout=30)

                if response.status_code == 429:
                    wait_seconds = 60 * (attempt + 1)
                    print(f"    Rate limited via {fetcher_name}. Waiting {wait_seconds}s...")
                    time.sleep(wait_seconds)
                    had_retryable_error = True
                    break

                if response.status_code == 403 and fetcher_name in {"requests", "curl"} and engine == "auto":
                    next_engine = "curl impersonation" if fetcher_name == "requests" and HAS_CURL_CFFI else "playwright"
                    print(f"    HTTP 403 via {fetcher_name} for {url} - retrying with {next_engine}")
                    continue

                if response.status_code != 200:
                    last_status = response.status_code
                    print(f"    HTTP {response.status_code} via {fetcher_name} for {url}")
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                return _unwrap_comment_tables(soup)
            except Exception as exc:
                print(f"    {fetcher_name} error: {exc}")
                continue

        if had_retryable_error:
            continue
        if attempt < retries - 1:
            time.sleep(10)
            continue

        if last_status == 403 and not HAS_CURL_CFFI and engine in {"auto", "curl"}:
            print("    Tip: install curl_cffi for browser-grade requests: pip install curl_cffi")
        if last_status == 403 and not HAS_PLAYWRIGHT and engine in {"auto", "playwright"}:
            print("    Tip: install Playwright for browser fetches: pip install playwright")

    return None


def _find_table(soup: BeautifulSoup, preferred_ids: Iterable[str], required_data_stat: str) -> Optional[BeautifulSoup]:
    for pattern in preferred_ids:
        table = soup.find("table", {"id": re.compile(pattern)})
        if table is not None:
            return table

    for table in soup.find_all("table"):
        if table.find(attrs={"data-stat": required_data_stat}):
            return table
    return None


def get_season_squads(season: str) -> List[Squad]:
    url = f"{FBREF_BASE}/en/comps/{SERIE_A_COMP_ID}/{season}/Serie-A-Stats"
    print(f"  Fetching season page: {season}")
    soup = fetch_page(url, engine=FETCH_ENGINE)
    if soup is None:
        return []

    seen_ids = set()
    seen_keys = set()
    squads: List[Squad] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if "/squads/" not in href or season not in href:
            continue
        squad_id = _extract_fbref_id(href)
        squad_name = anchor.get_text(strip=True)
        squad_key = _team_key(squad_name)
        if not squad_id or not squad_name:
            continue
        if squad_id in seen_ids or squad_key in seen_keys:
            continue
        seen_ids.add(squad_id)
        seen_keys.add(squad_key)
        squads.append(Squad(squad_id=squad_id, squad_name=squad_name, squad_key=squad_key))

    print(f"    Found {len(squads)} squads")
    return squads


def get_team_match_log(squad: Squad, season: str) -> List[dict]:
    urls = [
        f"{FBREF_BASE}/en/squads/{squad.squad_id}/{season}/matchlogs/c{SERIE_A_COMP_ID}/schedule/{squad.squad_id}-Scores-and-Fixtures-Serie-A",
        f"{FBREF_BASE}/en/squads/{squad.squad_id}/{season}/matchlogs/c{SERIE_A_COMP_ID}/summary/",
    ]

    soup = None
    for url in urls:
        soup = fetch_page(url, engine=FETCH_ENGINE)
        if soup is not None:
            break
    if soup is None:
        return []

    table = _find_table(soup, ("matchlogs_for",), "date")
    if table is None:
        return []

    tbody = table.find("tbody")
    if tbody is None:
        return []

    matches = []
    for row in tbody.find_all("tr"):
        classes = row.get("class", [])
        if any(cls in classes for cls in ("thead", "spacer", "partial_table")):
            continue

        cells = {cell.get("data-stat", ""): _clean_text(cell) for cell in row.find_all(["th", "td"])}
        match_date = cells.get("date", "")
        if len(match_date) < 8:
            continue

        comp = cells.get("comp", "")
        if comp and "Serie A" not in comp:
            continue

        opponent = cells.get("opponent", "")
        matches.append(
            {
                "date": match_date,
                "opponent": opponent,
                "opponent_key": _team_key(opponent),
                "is_home": cells.get("venue", "").lower() == "home",
                "team_xg": _safe_float(cells.get("xg")),
                "team_xga": _safe_float(cells.get("xg_against", cells.get("xga"))),
            }
        )

    return matches


def get_squad_player_list(squad: Squad, season: str) -> List[dict]:
    urls = [
        f"{FBREF_BASE}/en/squads/{squad.squad_id}/{season}/stats/c{SERIE_A_COMP_ID}/summary/{squad.squad_id}-Stats-Serie-A",
        f"{FBREF_BASE}/en/squads/{squad.squad_id}/{season}/c{SERIE_A_COMP_ID}/Serie-A-Stats",
    ]

    soup = None
    for url in urls:
        soup = fetch_page(url, engine=FETCH_ENGINE)
        if soup is not None:
            break
    if soup is None:
        return []

    table = _find_table(soup, ("stats_standard",), "player")
    if table is None:
        return []

    tbody = table.find("tbody")
    if tbody is None:
        return []

    players = []
    for row in tbody.find_all("tr"):
        classes = row.get("class", [])
        if any(cls in classes for cls in ("thead", "spacer")):
            continue

        player_cell = row.find("td", {"data-stat": "player"}) or row.find("th", {"data-stat": "player"})
        if player_cell is None:
            continue
        anchor = player_cell.find("a", href=True)
        if anchor is None:
            continue

        cells = {cell.get("data-stat", ""): _clean_text(cell) for cell in row.find_all(["th", "td"])}
        minutes = _safe_int(cells.get("minutes"), 0) or 0
        position = cells.get("position", "")
        if minutes < MIN_SEASON_MINUTES:
            continue
        if position.upper().startswith("GK"):
            continue

        players.append(
            {
                "player_id": _extract_fbref_id(anchor["href"]),
                "player_name": anchor.get_text(strip=True),
                "position": position,
                "season_minutes": minutes,
            }
        )

    return players


def _parse_started(value: str) -> Optional[bool]:
    text = (value or "").strip()
    if not text:
        return None
    return text.upper() in {"Y", "YES", "*", "TRUE", "1"}


def get_player_match_log(player_id: str, season: str) -> List[dict]:
    url = f"{FBREF_BASE}/en/players/{player_id}/matchlogs/{season}/summary/{player_id}-Match-Logs"
    soup = fetch_page(url, engine=FETCH_ENGINE)
    if soup is None:
        return []

    table = _find_table(soup, ("matchlogs_all",), "date")
    if table is None:
        return []

    tbody = table.find("tbody")
    if tbody is None:
        return []

    matches = []
    for row in tbody.find_all("tr"):
        classes = row.get("class", [])
        if any(cls in classes for cls in ("thead", "spacer", "partial_table")):
            continue

        cells = {cell.get("data-stat", ""): _clean_text(cell) for cell in row.find_all(["th", "td"])}
        match_date = cells.get("date", "")
        if len(match_date) < 8:
            continue

        comp = cells.get("comp", "")
        if comp and "Serie A" not in comp:
            continue

        team = cells.get("team", cells.get("squad", ""))
        opponent = cells.get("opponent", "")
        matches.append(
            {
                "date": match_date,
                "competition": "Serie A",
                "team": team,
                "team_key": _team_key(team),
                "opponent": opponent,
                "opponent_key": _team_key(opponent),
                "is_home": cells.get("venue", "").lower() == "home",
                "started": _parse_started(cells.get("game_started", cells.get("started", ""))),
                "position": cells.get("position", ""),
                "minutes": _safe_int(cells.get("minutes"), 0) or 0,
                "goals": _safe_int(cells.get("goals"), 0) or 0,
                "assists": _safe_int(cells.get("assists"), 0) or 0,
                "shots": _safe_int(cells.get("shots", cells.get("shots_total")), 0) or 0,
                "shots_on_target": _safe_int(cells.get("shots_on_target"), 0) or 0,
                "xg": _safe_float(cells.get("xg"), 0.0) or 0.0,
                "npxg": _safe_float(cells.get("npxg"), 0.0) or 0.0,
                "xa": _safe_float(cells.get("xg_assist", cells.get("xa")), 0.0) or 0.0,
                "penalties_scored": _safe_int(cells.get("pens_made"), 0) or 0,
                "penalties_attempted": _safe_int(cells.get("pens_att"), 0) or 0,
            }
        )

    return matches


def scrape_season(season: str, output_dir: str, resume: bool = False) -> str:
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"serie-a-player-match-logs-{season}.csv")
    progress_path = os.path.join(output_dir, f".progress-{season}.json")

    done_players = set()
    existing_rows: List[dict] = []
    if resume and os.path.exists(progress_path):
        with open(progress_path, "r", encoding="utf-8") as handle:
            progress = json.load(handle)
            done_players = set(progress.get("done_players", []))
        if os.path.exists(output_path):
            with open(output_path, "r", encoding="utf-8-sig") as handle:
                existing_rows = list(csv.DictReader(handle))
        print(f"  Resuming: {len(done_players)} players already done, {len(existing_rows)} rows loaded")

    print(f"\n{'=' * 64}")
    print(f"  Scraping Serie A {season}")
    print(f"{'=' * 64}")

    squads = get_season_squads(season)
    if not squads:
        print("  No squads found.")
        return ""

    print("\n  Fetching team match logs...")
    team_matches: Dict[str, List[dict]] = {}
    for squad in squads:
        print(f"    {squad.squad_name}...")
        matches = get_team_match_log(squad, season)
        team_matches[squad.squad_key] = matches
        print(f"      {len(matches)} matches")

    all_rows = list(existing_rows)
    team_match_join_hits = 0
    team_match_join_misses = 0
    started_unknown_rows = 0
    total_players = 0
    processed_players = 0

    print("\n  Fetching player match logs...")
    for squad in squads:
        print(f"\n  {squad.squad_name}:")
        players = get_squad_player_list(squad, season)
        print(f"    {len(players)} outfield players with >= {MIN_SEASON_MINUTES} minutes")
        total_players += len(players)

        for player in players:
            if player["player_id"] in done_players:
                continue

            print(
                f"      {player['player_name']} ({player['position']}, {player['season_minutes']}min)...",
                end="",
                flush=True,
            )
            match_log = [match for match in get_player_match_log(player["player_id"], season) if match["minutes"] > 0]
            print(f" {len(match_log)} matches")

            team_log = team_matches.get(squad.squad_key, [])
            for match in match_log:
                team_match = next(
                    (
                        team_row
                        for team_row in team_log
                        if team_row["date"] == match["date"] and team_row["opponent_key"] == match["opponent_key"]
                    ),
                    None,
                )

                if team_match is None:
                    team_match_join_misses += 1
                else:
                    team_match_join_hits += 1

                if match["started"] is None:
                    started_unknown_rows += 1

                all_rows.append(
                    {
                        "season": season,
                        "match_date": match["date"],
                        "competition": match["competition"],
                        "team": squad.squad_name,
                        "opponent": match["opponent"],
                        "is_home": 1 if match["is_home"] else 0,
                        "player_id": player["player_id"],
                        "player_name": player["player_name"],
                        "position": match["position"] or player["position"],
                        "started": "" if match["started"] is None else int(match["started"]),
                        "minutes": match["minutes"],
                        "goals": match["goals"],
                        "assists": match["assists"],
                        "shots": match["shots"],
                        "shots_on_target": match["shots_on_target"],
                        "xg": match["xg"],
                        "npxg": match["npxg"],
                        "xa": match["xa"],
                        "penalties_scored": match["penalties_scored"],
                        "penalties_attempted": match["penalties_attempted"],
                        "team_xg": "" if team_match is None or team_match["team_xg"] is None else team_match["team_xg"],
                        "team_xga": "" if team_match is None or team_match["team_xga"] is None else team_match["team_xga"],
                    }
                )

            done_players.add(player["player_id"])
            processed_players += 1
            if processed_players % 5 == 0:
                with open(progress_path, "w", encoding="utf-8") as handle:
                    json.dump({"done_players": sorted(done_players)}, handle)

    fieldnames = [
        "season",
        "match_date",
        "competition",
        "team",
        "opponent",
        "is_home",
        "player_id",
        "player_name",
        "position",
        "started",
        "minutes",
        "goals",
        "assists",
        "shots",
        "shots_on_target",
        "xg",
        "npxg",
        "xa",
        "penalties_scored",
        "penalties_attempted",
        "team_xg",
        "team_xga",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    if os.path.exists(progress_path):
        os.remove(progress_path)

    total_joins = team_match_join_hits + team_match_join_misses
    join_rate = (team_match_join_hits / total_joins * 100.0) if total_joins else 0.0

    print(f"\n  Saved: {output_path} ({len(all_rows):,} rows)")
    print("  QA")
    print(f"    Players scraped: {total_players:,}")
    print(f"    Team-match joins: {team_match_join_hits:,} hit / {team_match_join_misses:,} miss ({join_rate:.1f}% match rate)")
    print(f"    Unknown starter rows: {started_unknown_rows:,}")

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="FBref Serie A player match-log scraper")
    parser.add_argument("--season", nargs="+", help="Season(s) to scrape, for example 2024-2025")
    parser.add_argument("--all", action="store_true", help="Scrape all supported seasons")
    parser.add_argument("--out-dir", default=OUTPUT_DIR)
    parser.add_argument("--resume", action="store_true", help="Resume interrupted scrape")
    parser.add_argument(
        "--engine",
        choices=["auto", "requests", "curl", "playwright"],
        default="auto",
        help="HTTP engine: auto tries requests first, then curl_cffi and Playwright fallbacks if installed",
    )
    args = parser.parse_args()

    global FETCH_ENGINE
    FETCH_ENGINE = args.engine

    if args.all:
        seasons = AVAILABLE_SEASONS
    elif args.season:
        seasons = args.season
    else:
        seasons = DEFAULT_SEASONS

    print("\n" + "=" * 64)
    print("  IL MARGINE - FBref Serie A Scraper")
    print("=" * 64)
    print(f"  Seasons: {seasons}")
    print(f"  Output:  {args.out_dir}")
    print(f"  Delay:   {REQUEST_DELAY:.1f}s between requests")
    print(f"  Engine:  {FETCH_ENGINE}")
    if FETCH_ENGINE in {"auto", "curl"} and not HAS_CURL_CFFI:
        print("  Note: curl_cffi not installed. Auto mode will use raw requests only.")
    if FETCH_ENGINE in {"auto", "playwright"} and not HAS_PLAYWRIGHT:
        print("  Note: Playwright not installed. Browser fetch fallback is unavailable.")

    for season in seasons:
        if season not in AVAILABLE_SEASONS:
            print(f"\n  Warning: {season} may not be available on FBref with xG data")
        output_path = scrape_season(season, args.out_dir, resume=args.resume)
        if not output_path:
            continue

        with open(output_path, "r", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))

        unique_players = len({row["player_id"] for row in rows})
        unique_matches = len({(row["match_date"], row["team"], row["opponent"]) for row in rows})
        total_goals = sum(int(row.get("goals", 0) or 0) for row in rows)

        print(f"\n  Season {season} summary:")
        print(f"    Players:           {unique_players:,}")
        print(f"    Team-match rows:   {unique_matches:,}")
        print(f"    Player-match rows: {len(rows):,}")
        print(f"    Goals:             {total_goals:,}")

    print("\n  Done.\n")


if __name__ == "__main__":
    main()
