#!/usr/bin/env python3
"""Capture Bet365 service-break totals from its public UK event boards.

Odds-API does not expose Bet365's service-break markets. This bounded local
fallback uses the installed Edge/Chrome browser and merges only break rows into
the existing Odds-API snapshot. It is intentionally Windows-local: Bet365
blocks hosted datacenter browsers.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "data" / "tennis-props" / "inbox"
PROJECTION_BOARD = ROOT / "data" / "tennis-props" / "player-props-board.csv"
DEFAULT_SIGNALS = ROOT / "data" / "tennis-props" / "shadow" / "aces-dfs-shadow-signals.csv"
COMMON_PATH = ROOT / "scripts" / "tennis-props-scrape-bet365.py"
BET365_URL = "https://www.bet365.com/"
DEFAULT_COMPETITIONS = ("US Open", "US Open Women")
BREAK_PROSPECTIVE_MODES = {"breaks_prospective_shadow", "breaks_single_source_shadow"}
AUDIT_FIELDS = (
    "captured_at",
    "competition",
    "match",
    "event_id",
    "status",
    "rows",
    "detail",
)


def load_common() -> Any:
    spec = importlib.util.spec_from_file_location("tennis_props_bet365_common", COMMON_PATH)
    if not spec or not spec.loader:
        raise RuntimeError(f"Cannot load {COMMON_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def norm_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def pair_key(player1: object, player2: object) -> tuple[str, str]:
    return tuple(sorted((norm_name(player1), norm_name(player2))))


def decimal_odds(value: str) -> float | None:
    text = str(value or "").strip()
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        try:
            return 1.0 + float(numerator) / float(denominator)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
    try:
        parsed = float(text)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 1.0 else None


def price_text(value: float) -> str:
    return f"{value:.4f}"


def numeric_pairs(text: str) -> list[tuple[str, float]]:
    pairs: list[tuple[str, float]] = []
    for line, raw_price in re.findall(
        r"(?<![\d/])(\d+(?:\.\d+)?)\s+(\d+/\d+|\d+(?:\.\d+)?)(?![\d/])",
        text,
    ):
        price = decimal_odds(raw_price)
        if price is not None:
            pairs.append((line, price))
    return pairs


def parse_break_board(body_text: str) -> list[tuple[str, float, float]]:
    """Return match, player-one and player-two line/price triples in display order."""
    normalized = " ".join(str(body_text or "").split())
    section = re.search(
        r"Total Breaks of Serve(?: in Match)?\s+(?:BB\s+)?Match\s+.*?\s+Over\s+"
        r"(?P<over>.*?)\s+Under\s+(?P<under>.*?)\s+"
        r"(?=(?:Ace Totals|Double Fault Totals|Total Tie Breaks|Go The Distance\?|"
        r"Match Result &|Five Setter\?|Information and transmission delays)\b)",
        normalized,
        flags=re.I,
    )
    if not section:
        return []
    overs = numeric_pairs(section.group("over"))
    unders = numeric_pairs(section.group("under"))
    if len(overs) < 3 or len(unders) < 3:
        return []
    output: list[tuple[str, float, float]] = []
    for index in range(3):
        over_line, over_price = overs[index]
        under_line, under_price = unders[index]
        if over_line != under_line:
            return []
        output.append((over_line, over_price, under_price))
    return output


def browser_executable() -> Path | None:
    candidates = (
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
    )
    return next((path for path in candidates if path.is_file()), None)


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def seed_events(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    events: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        player = str(row.get("player") or "").strip()
        opponent = str(row.get("opponent") or "").strip()
        if not player or not opponent or norm_name(player) == norm_name(opponent):
            continue
        key = pair_key(player, opponent)
        event_date = str(row.get("date") or row.get("scheduled_date") or "")
        event_id = str(row.get("event_id") or "")
        if not event_id:
            digest = hashlib.sha1(
                "|".join((event_date, *key)).encode("utf-8")
            ).hexdigest()[:16]
            event_id = f"bet365-direct-{digest}"
        events.setdefault(
            key,
            {
                "event_id": event_id,
                "date": event_date,
                "tour": str(row.get("tour") or ""),
                "tournament": str(row.get("tournament") or ""),
                "match_start_utc": str(
                    row.get("match_start_utc") or row.get("scheduled_start_utc") or ""
                ),
            },
        )
    return events


def tracked_seed_events(
    seeds: dict[tuple[str, str], dict[str, str]],
    signal_rows: list[dict[str, str]],
) -> dict[tuple[str, str], dict[str, str]]:
    """Keep fixtures with an open prospective service-break decision."""
    tracked_pairs = {
        pair_key(row.get("player"), row.get("opponent"))
        for row in signal_rows
        if str(row.get("market") or "").strip().lower() in {"player_breaks", "match_breaks"}
        and str(row.get("decision_mode") or "").strip() in BREAK_PROSPECTIVE_MODES
        and str(row.get("settlement_status") or "pending").strip().lower() in {"", "pending", "open"}
        and norm_name(row.get("player"))
        and norm_name(row.get("opponent"))
    }
    return {key: seed for key, seed in seeds.items() if key in tracked_pairs}


def parse_event_start(
    body_text: str,
    player1: str,
    player2: str,
    seed_date: str,
) -> str:
    """Extract Bet365's London-local fixture time and return a UTC timestamp."""
    normalized = " ".join(str(body_text or "").split())
    match = re.search(
        rf"(?P<day>\d{{1,2}})\s+"
        rf"(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
        rf"(?P<time>\d{{1,2}}:\d{{2}})\s+"
        rf"{re.escape(player1)}\s+vs\s+{re.escape(player2)}\b",
        normalized,
        flags=re.I,
    )
    if not match:
        return ""
    try:
        expected = datetime.strptime(seed_date, "%Y-%m-%d").date()
        month = datetime.strptime(match.group("month").title(), "%b").month
        hour, minute = (int(part) for part in match.group("time").split(":"))
        candidates = [
            datetime(
                year,
                month,
                int(match.group("day")),
                hour,
                minute,
                tzinfo=ZoneInfo("Europe/London"),
            )
            for year in (expected.year - 1, expected.year, expected.year + 1)
        ]
        local_start = min(
            candidates,
            key=lambda value: abs((value.date() - expected).days),
        )
        if abs((local_start.date() - expected).days) > 7:
            return ""
    except (TypeError, ValueError):
        return ""
    return (
        local_start.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def competition_labels(
    seeds: dict[tuple[str, str], dict[str, str]], requested: list[str] | None
) -> tuple[str, ...]:
    if requested:
        return tuple(dict.fromkeys(label.strip() for label in requested if label.strip()))
    labels: list[str] = []
    for seed in seeds.values():
        tournament = str(seed.get("tournament") or "").strip()
        tour = str(seed.get("tour") or "").strip().upper()
        if not tournament:
            continue
        if norm_name(tournament) == "us open":
            candidates = ("US Open Women", "US Open") if tour == "WTA" else ("US Open",)
        elif tour == "WTA":
            candidates = (f"{tournament} Women", f"WTA {tournament}", tournament)
        elif tour == "ATP":
            candidates = (f"ATP {tournament}", tournament)
        else:
            candidates = (tournament,)
        for candidate in candidates:
            if candidate not in labels:
                labels.append(candidate)
    return tuple(labels or DEFAULT_COMPETITIONS)


def click_visible_exact(page: Any, label: str) -> bool:
    nodes = page.get_by_text(label, exact=True)
    for index in range(nodes.count()):
        node = nodes.nth(index)
        if not node.is_visible():
            continue
        try:
            node.click(timeout=5000)
            return True
        except Exception:
            continue
    return False


def accept_cookies(page: Any) -> None:
    for label in ("Accept All", "Essential Only"):
        if click_visible_exact(page, label):
            page.wait_for_timeout(300)
            return


def open_competition(page: Any, competition: str, timeout_ms: int) -> bool:
    """Open a competition from Trending/Most Used, then fall back to Tennis A-Z."""
    try:
        if click_visible_exact(page, competition):
            page.locator(".rcl-ParticipantFixtureDetails_TeamNames").first.wait_for(
                state="attached", timeout=timeout_ms
            )
            return True
    except Exception:
        pass
    page.goto(BET365_URL, wait_until="domcontentloaded", timeout=timeout_ms)
    page.wait_for_timeout(3000)
    accept_cookies(page)
    if not click_visible_exact(page, "Tennis"):
        return False
    page.wait_for_timeout(3000)
    if not click_visible_exact(page, competition):
        return False
    try:
        page.locator(".rcl-ParticipantFixtureDetails_TeamNames").first.wait_for(
            state="attached", timeout=timeout_ms
        )
        return True
    except Exception:
        return False


def fixture_pairs(page: Any) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    fixtures = page.locator(".rcl-ParticipantFixtureDetails_TeamNames")
    for index in range(fixtures.count()):
        names = [part.strip() for part in fixtures.nth(index).inner_text().splitlines() if part.strip()]
        if len(names) != 2:
            continue
        pair = (names[0], names[1])
        key = pair_key(*pair)
        if key in seen:
            continue
        seen.add(key)
        pairs.append(pair)
    return pairs


def open_fixture(page: Any, player1: str, player2: str) -> bool:
    fixtures = page.locator(".rcl-ParticipantFixtureDetails_TeamNames")
    target = pair_key(player1, player2)
    for index in range(fixtures.count()):
        fixture = fixtures.nth(index)
        names = [part.strip() for part in fixture.inner_text().splitlines() if part.strip()]
        if len(names) != 2 or pair_key(*names) != target:
            continue
        fixture.get_by_text(names[0], exact=True).click(timeout=5000)
        return True
    return False


def set_hash(page: Any, url: str) -> None:
    fragment = urlparse(url).fragment
    page.evaluate("fragment => { window.location.hash = fragment; }", fragment)


def build_rows(
    *,
    player1: str,
    player2: str,
    seed: dict[str, str],
    prices: list[tuple[str, float, float]],
    captured_at: str,
) -> list[dict[str, str]]:
    if len(prices) != 3:
        return []
    labels = (
        ("match_breaks", player1, player2),
        ("player_breaks", player1, player2),
        ("player_breaks", player2, player1),
    )
    rows: list[dict[str, str]] = []
    for (market, player, opponent), (line, over, under) in zip(labels, prices):
        rows.append(
            {
                "event_id": seed["event_id"],
                "date": seed["date"],
                "tour": seed["tour"],
                "tournament": seed["tournament"],
                "bookmaker": "Bet365",
                "player": player,
                "opponent": opponent,
                "market": market,
                "line": line,
                "over_odds": price_text(over),
                "under_odds": price_text(under),
                "capture_ts": captured_at,
                "match_start_utc": seed["match_start_utc"],
                "raw_market_name": "Total Breaks of Serve [direct]",
                "raw_outcome_count": "6",
                "raw_label_sample": f"{player1} vs {player2}",
            }
        )
    return rows


def capture(
    seeds: dict[tuple[str, str], dict[str, str]],
    *,
    competitions: tuple[str, ...],
    max_events: int,
    timeout_seconds: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]], set[str]]:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is not installed for this Python interpreter") from exc

    executable = browser_executable()
    if executable is None:
        raise RuntimeError("Microsoft Edge or Google Chrome was not found")

    captured_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    output: list[dict[str, str]] = []
    audit: list[dict[str, str]] = []
    scanned_event_ids: set[str] = set()
    timeout_ms = max(5, timeout_seconds) * 1000
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=str(executable),
            args=["--disable-blink-features=AutomationControlled"],
        )
        version = browser.version
        context = browser.new_context(
            locale="en-GB",
            timezone_id="Europe/London",
            viewport={"width": 1440, "height": 1000},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version} "
                f"Safari/537.36 Edg/{version}"
            ),
        )
        page = context.new_page()
        page.goto(BET365_URL, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(6000)
        accept_cookies(page)
        processed = 0
        for competition in competitions:
            competition_processed = 0
            if not open_competition(page, competition, timeout_ms):
                audit.append(
                    {
                        "captured_at": captured_at,
                        "competition": competition,
                        "match": "",
                        "event_id": "",
                        "status": "COMPETITION_NOT_FOUND",
                        "rows": "0",
                        "detail": "No visible competition link",
                    }
                )
                continue
            competition_url = page.url
            available_pairs = fixture_pairs(page)
            pairs = [pair for pair in available_pairs if pair_key(*pair) in seeds]
            print(
                f"{competition}: fixtures={len(available_pairs)} seeded_matches={len(pairs)} route={competition_url}",
                flush=True,
            )
            for player1, player2 in pairs:
                if competition_processed >= max_events:
                    break
                seed = seeds[pair_key(player1, player2)]
                scanned_event_ids.add(seed["event_id"])
                processed += 1
                competition_processed += 1
                status = "NO_BREAK_MARKET"
                detail = ""
                event_rows: list[dict[str, str]] = []
                try:
                    if not open_fixture(page, player1, player2):
                        raise LookupError("Fixture row disappeared before navigation")
                    page.wait_for_url(re.compile(r"/D8/E\d+/"), timeout=timeout_ms)
                    page.wait_for_timeout(1200)
                    body = " ".join(page.locator("body").inner_text(timeout=timeout_ms).split())
                    if not re.search(r"Total Breaks of Serve(?: in Match)?", body, re.I):
                        page.wait_for_timeout(1800)
                        body = " ".join(page.locator("body").inner_text(timeout=timeout_ms).split())
                    prices = parse_break_board(body)
                    if prices:
                        event_seed = dict(seed)
                        if not event_seed.get("match_start_utc"):
                            event_seed["match_start_utc"] = parse_event_start(
                                body,
                                player1,
                                player2,
                                event_seed.get("date", ""),
                            )
                        event_rows = build_rows(
                            player1=player1,
                            player2=player2,
                            seed=event_seed,
                            prices=prices,
                            captured_at=captured_at,
                        )
                        status = "CAPTURED" if event_seed["match_start_utc"] else "CAPTURED_NO_START"
                        detail = re.search(r"/E(\d+)/", page.url).group(1) if re.search(r"/E(\d+)/", page.url) else page.url
                    else:
                        detail = "Break heading loaded but six prices were not parseable"
                except PlaywrightTimeoutError:
                    detail = "Break market not offered or event board timed out"
                except Exception as exc:
                    status = "PAGE_ERROR"
                    detail = f"{type(exc).__name__}: {exc}"[:300]
                output.extend(event_rows)
                audit.append(
                    {
                        "captured_at": captured_at,
                        "competition": competition,
                        "match": f"{player1} vs {player2}",
                        "event_id": seed["event_id"],
                        "status": status,
                        "rows": str(len(event_rows)),
                        "detail": detail,
                    }
                )
                print(
                    f"[{competition_processed}/{min(len(pairs), max_events)}] "
                    f"{competition} {status}: {player1} vs {player2}",
                    flush=True,
                )
                set_hash(page, competition_url)
                try:
                    page.locator(".rcl-ParticipantFixtureDetails_TeamNames").first.wait_for(
                        state="attached", timeout=timeout_ms
                    )
                except PlaywrightTimeoutError:
                    page.goto(BET365_URL, wait_until="domcontentloaded", timeout=timeout_ms)
                    page.wait_for_timeout(3000)
                    accept_cookies(page)
                    if not click_visible_exact(page, competition):
                        break
                    try:
                        page.locator(".rcl-ParticipantFixtureDetails_TeamNames").first.wait_for(
                            state="attached", timeout=timeout_ms
                        )
                        competition_url = page.url
                    except PlaywrightTimeoutError:
                        break
        context.close()
        browser.close()
    return output, audit, scanned_event_ids


def merge_snapshot(
    existing: list[dict[str, str]],
    fresh: list[dict[str, str]],
    scanned_event_ids: set[str],
) -> list[dict[str, str]]:
    kept = [
        row
        for row in existing
        if not (
            str(row.get("event_id") or "") in scanned_event_ids
            and str(row.get("market") or "") in {"player_breaks", "match_breaks"}
            and "[direct]" in str(row.get("raw_market_name") or "")
        )
    ]
    by_key: dict[tuple[str, ...], dict[str, str]] = {}
    for row in [*kept, *fresh]:
        key = tuple(
            str(row.get(field) or "").strip().casefold()
            for field in ("event_id", "bookmaker", "player", "opponent", "market", "line")
        )
        by_key[key] = row
    return list(by_key.values())


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture public Bet365 service-break totals locally")
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--max-events", type=int, default=40)
    parser.add_argument("--timeout-seconds", type=int, default=10)
    parser.add_argument("--competition", action="append", dest="competitions")
    parser.add_argument("--seed", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--history-out", default="")
    parser.add_argument("--audit-out", default="")
    parser.add_argument("--tracked-only", action="store_true")
    parser.add_argument("--signals", default=str(DEFAULT_SIGNALS))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    common = load_common()
    default_snapshot = INBOX / f"bet365-lines-{args.date}.csv"
    seed_path = Path(args.seed) if args.seed else default_snapshot
    out_path = Path(args.out) if args.out else default_snapshot
    history_path = Path(args.history_out) if args.history_out else INBOX / f"bet365-lines-history-{args.date[:7]}.csv"
    audit_path = Path(args.audit_out) if args.audit_out else INBOX / f"bet365-direct-market-audit-{args.date}.csv"
    existing = read_rows(out_path)
    seeds = seed_events(read_rows(seed_path))
    if not seeds and seed_path.resolve() != PROJECTION_BOARD.resolve():
        seeds = seed_events(read_rows(PROJECTION_BOARD))
        if seeds:
            print(
                f"No Odds-API seed events available in {seed_path}; "
                f"using {len(seeds)} projection-board fixtures from {PROJECTION_BOARD}."
            )
    if not seeds:
        print(
            f"No fixture seeds available in {seed_path} or {PROJECTION_BOARD}; "
            "direct break capture skipped."
        )
        return 0
    if args.tracked_only:
        seeds = tracked_seed_events(seeds, read_rows(Path(args.signals)))
        if not seeds:
            print("No open prospective service-break fixtures; close capture skipped.")
            return 0
        print(f"Tracked-only service-break close capture: {len(seeds)} fixture(s).")

    try:
        rows, audit, scanned_ids = capture(
            seeds,
            competitions=competition_labels(seeds, args.competitions),
            max_events=max(0, args.max_events),
            timeout_seconds=args.timeout_seconds,
        )
    except Exception as exc:
        print(f"Direct Bet365 break capture unavailable: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print(f"Direct Bet365 break rows: {len(rows)} across {len(scanned_ids)} seeded events")
    if args.dry_run:
        print(json.dumps(audit, ensure_ascii=True, indent=2))
        print(json.dumps(rows[:12], ensure_ascii=True, indent=2))
        return 0
    merged = merge_snapshot(existing, rows, scanned_ids)
    common.write_rows(out_path, merged, common.OUTPUT_FIELDS)
    common.write_rows(audit_path, audit, list(AUDIT_FIELDS))
    added = common.append_history_rows(history_path, rows)
    print(f"Merged snapshot: {out_path}")
    print(f"Price history: added {added}, file={history_path}")
    print(f"Audit: {audit_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
