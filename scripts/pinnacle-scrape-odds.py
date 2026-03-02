#!/usr/bin/env python3
"""
Pinnacle tennis odds scraper.
Scrapes match-winner + Over/Under total games.
Upserts to bookmaker_odds_snapshot in Supabase.

Usage:
  python scripts/pinnacle-scrape-odds.py
  python scripts/pinnacle-scrape-odds.py --dry-run
  python scripts/pinnacle-scrape-odds.py --save-html
  python scripts/pinnacle-scrape-odds.py --verbose
"""

import asyncio
import csv
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from time import sleep as _sleep

import requests
from playwright.async_api import async_playwright

# ─── Environment ────────────────────────────────────────────────────

def load_env():
    """Load .env.local / env.local from project root."""
    base = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(base)
    for name in ["env.local", ".env.local"]:
        path = os.path.join(root, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip().replace("\r", "")
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        v = v.strip().strip('"').strip("'")
                        os.environ[k.strip()] = v

load_env()

# ─── Constants ──────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

PINNACLE_TENNIS_URL = "https://www.pinnacle.com/en/tennis/matchups/"
DRY_RUN = "--dry-run" in sys.argv
SAVE_HTML = "--save-html" in sys.argv
VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv
HTML_DIR = Path("data/pinnacle-html")


# ─── Helpers ────────────────────────────────────────────────────────

def parse_decimal_odds(text: str) -> float | None:
    """Parse odds text like '1.72' to decimal."""
    text = (text or "").strip()
    if not text or text == "-":
        return None
    try:
        val = float(text)
        if val >= 1.01:
            return round(val, 3)
        return None
    except ValueError:
        return None


def compute_margin(odds1: float, odds2: float) -> float:
    """Pinnacle margin = sum of implied probs - 1 (as percentage)."""
    if not odds1 or not odds2:
        return 0.0
    return round((1 / odds1 + 1 / odds2 - 1) * 100, 2)


def is_doubles(name: str) -> bool:
    return "/" in (name or "") or "&" in (name or "")


def _text_from_html(html: str) -> str:
    """Extract visible text from HTML (content between > and <)."""
    parts = re.findall(r">([^<]*)<", html)
    return " ".join(p.strip() for p in parts if p.strip())


def _clean_name(n: str) -> str:
    """Clean player name: strip parenthetical, trailing day names, etc."""
    n = re.sub(r"\s*\([^)]*\)", "", n)  # strip (8), (WC), (Sets), etc.
    n = re.sub(r"\s+(Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday),.*$", "", n, flags=re.I)
    n = re.sub(r"\s+(Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday)\s*$", "", n, flags=re.I)
    n = re.sub(r"\s+vs\s+at\s*$", "", n, flags=re.I)
    n = re.sub(r"\s+at\s*$", "", n, flags=re.I)
    return n.strip()


def _norm_name(n: str) -> str:
    """Normalise name for O/U merge: lowercase, strip accents/parens/hyphens."""
    n = (n or "").strip().lower()
    n = unicodedata.normalize("NFD", n)
    n = re.sub(r'[\u0300-\u036f]', '', n)
    n = re.sub(r'\s*\(.*?\)', '', n)
    n = re.sub(r"[-']", '', n)
    return " ".join(n.split())


# ─── O/U structured parser ─────────────────────────────────────────

def _parse_ou_from_html(row_html: str) -> tuple:
    """
    Extract O/U line + odds from data-test-id="over-under" HTML section.
    Returns (ou_line, ou_over, ou_under) or (None, None, None).
    """
    ou_start = row_html.find('data-test-id="over-under"')
    if ou_start == -1:
        return None, None, None

    # Isolate the over-under section (stop at next data-test-id)
    ou_section = row_html[ou_start:]
    next_section = re.search(r'data-test-id="(?!over-under)', ou_section[30:])
    if next_section:
        ou_section = ou_section[:next_section.start() + 30]

    # ── Line ──
    line_val = None
    # Method 1: button title="22.5"
    title_m = re.search(r'title="((?:1[5-9]|2[0-9]|3[0-5])\.5)"', ou_section)
    if title_m:
        line_val = float(title_m.group(1))
    # Method 2: span text like "22.5", "O 22.5", "U 22.5"
    if line_val is None:
        label_m = re.search(r'>\s*[OU]?\s*((?:1[5-9]|2[0-9]|3[0-5])\.5)\s*<', ou_section)
        if label_m:
            line_val = float(label_m.group(1))
    if line_val is None:
        return None, None, None

    # ── Prices ──
    prices = re.findall(r'class="price[^"]*"[^>]*>\s*(\d+\.\d{2,3})\s*<', ou_section)
    if len(prices) < 2:
        all_decimals = re.findall(r'>\s*(\d+\.\d{2,3})\s*<', ou_section)
        prices = [p for p in all_decimals if 1.01 < float(p) < 20]
    valid = [round(float(p), 3) for p in prices if 1.01 < float(p) < 20]
    if len(valid) >= 2:
        return line_val, valid[0], valid[1]
    return None, None, None


def _parse_moneyline_from_html(row_html: str) -> tuple:
    """
    Extract match-winner odds from data-test-id="moneyline" HTML section.
    Returns (odds1, odds2) or (None, None).
    """
    ml_start = row_html.find('data-test-id="moneyline"')
    if ml_start == -1:
        return None, None

    ml_section = row_html[ml_start:]
    next_section = re.search(r'data-test-id="(?!moneyline)', ml_section[30:])
    if next_section:
        ml_section = ml_section[:next_section.start() + 30]

    prices = re.findall(r'class="price[^"]*"[^>]*>\s*(\d+\.\d{2,3})\s*<', ml_section)
    if len(prices) < 2:
        prices = re.findall(r'>\s*(\d+\.\d{2,3})\s*<', ml_section)
        prices = [p for p in prices if 1.01 < float(p) < 100]
    if len(prices) >= 2:
        return round(float(prices[0]), 3), round(float(prices[1]), 3)
    return None, None


# ─── Flat-text row parser (fallback) ───────────────────────────────

def _parse_row_from_html(row_html: str) -> dict | None:
    """
    Parse a single row HTML string into match_data or None.
    Pure string/regex — used as fallback when data-test-id selectors aren't present.
    """
    text = _text_from_html(row_html)
    if not text or len(text) < 10:
        return None
    # Skip date headers
    if re.search(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),.*\d{4}\s+at\s+\d{1,2}:\d{2}", text[:80], re.I):
        return None
    # Doubles
    if "/" in text or " & " in text:
        return None
    # Decimal odds: 1.01–100
    odds_candidates = re.findall(r"\b(\d+\.\d{2,3})\b", text)
    odds = []
    for s in odds_candidates:
        try:
            v = float(s)
            if 1.01 < v < 100:
                odds.append(round(v, 3))
        except ValueError:
            pass
    if len(odds) < 2:
        return None
    odds1, odds2 = odds[0], odds[1]

    skip = {
        "ML", "OU", "Total", "Spread", "Over", "Under", "Singles", "Doubles", "Games",
        "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
        "January", "February", "March", "April", "May", "June", "July", "August",
        "September", "October", "November", "December", "at", "Match Winner", "Winner",
    }

    def _bad_name(n: str) -> bool:
        if not n or "Match Winner" in n or re.search(r"\d+\.\d+", n):
            return True
        return False

    p1_name, p2_name = None, None
    # Pinnacle tennis: "Emerson Jones (Sets) Nikola Bartunkova (Sets)"
    if " (Sets)" in text or " (sets)" in text:
        parts = re.split(r"\s*\([Ss]ets\)\s*", text)
        names = [re.sub(r"\s+", " ", p).strip() for p in parts if p.strip() and not re.match(r"^\d{1,2}:\d{2}$", p.strip())]
        if len(names) >= 2 and 2 <= len(names[0]) <= 60 and 2 <= len(names[1]) <= 60:
            if names[0] not in skip and names[1] not in skip and not re.match(r"^[\d.+-]+$", names[0]) and not re.match(r"^[\d.+-]+$", names[1]):
                p1_name, p2_name = names[0], names[1]
    if not p1_name or not p2_name:
        for sep in (" - ", " vs ", " v ", " / "):
            if sep in text:
                parts = text.split(sep, 1)
                if len(parts) == 2:
                    a = re.sub(r"\s+", " ", parts[0]).strip()
                    b = re.sub(r"\s+", " ", parts[1]).strip()
                    if _bad_name(b) and (sep == " - " or " vs " in b):
                        b = re.split(r"\s+vs\s+|\s+Match\s+", b, maxsplit=1)[0].strip()
                    if _bad_name(a) or _bad_name(b):
                        continue
                    if 2 <= len(a) <= 60 and 2 <= len(b) <= 60 and a not in skip and b not in skip:
                        if not re.match(r"^[\d.+-]+$", a) and not re.match(r"^[\d.+-]+$", b):
                            p1_name, p2_name = a, b
                            break
    if not p1_name or not p2_name:
        tokens = re.findall(r"[A-Za-z\u00C0-\u00FF][A-Za-z0-9\s\-'.]{1,58}[A-Za-z\u00C0-\u00FF]|[A-Za-z\u00C0-\u00FF]{2,60}", text)
        candidates = [
            t.strip() for t in tokens
            if 2 <= len(t.strip()) <= 60 and t.strip() not in skip and not re.match(r"^[\d.+-]+$", t.strip())
            and not _bad_name(t.strip())
        ]
        seen = set()
        unique = [x for x in candidates if x not in seen and not seen.add(x)]
        if len(unique) >= 2:
            p1_name, p2_name = unique[0], unique[1]

    p1_name = _clean_name(p1_name or "")
    p2_name = _clean_name(p2_name or "")
    if not p1_name or not p2_name or is_doubles(p1_name) or is_doubles(p2_name):
        return None

    # O/U from text (fallback — structured parser is preferred)
    ou_line = None
    ou_over = None
    ou_under = None
    line_m = re.search(r"\b(1[5-9]|2[0-9]|3[0-5])\.5\b", text)
    if line_m:
        line_val = float(line_m.group(0))
        rest = text[line_m.end():line_m.end() + 200]
        ou_nums = re.findall(r"\b(\d+\.\d{2,3})\b", rest)
        ou_odds = [float(x) for x in ou_nums if 1.01 < float(x) < 20]
        if len(ou_odds) >= 2:
            ou_line = line_val
            ou_over, ou_under = ou_odds[0], ou_odds[1]

    return {
        "player1_name": p1_name,
        "player2_name": p2_name,
        "odds1": odds1,
        "odds2": odds2,
        "pinnacle_margin": compute_margin(odds1, odds2),
        "ou_line": ou_line,
        "ou_over": ou_over,
        "ou_under": ou_under,
    }


# ─── O/U merge helper ──────────────────────────────────────────────

def _merge_ou_into_results(results: list, ou_rows: list) -> int:
    """Merge O/U data from totals-tab scrape into match-winner results by player name."""
    results_by_names = {}
    for r in results:
        key = (_norm_name(r["player1_name"]), _norm_name(r["player2_name"]))
        results_by_names[key] = r
        results_by_names[(key[1], key[0])] = r  # reversed

    matched = 0
    for ou in ou_rows:
        key = (_norm_name(ou["p1"]), _norm_name(ou["p2"]))
        r = results_by_names.get(key)
        if r and r.get("ou_line") is None:
            r["ou_line"] = ou["line"]
            r["ou_over"] = ou["over"]
            r["ou_under"] = ou["under"]
            matched += 1
    return matched


# ─── Main scraper ───────────────────────────────────────────────────

async def scrape_pinnacle():
    """
    1. Load the matchups page, wait for odds to render.
    2. Use JS to find row containers with data-test-id="moneyline" / "over-under".
    3. Parse match-winner + O/U with structured parsers, fallback to flat-text.
    4. Phase 2: try Total Games tab for additional O/U data.
    5. If 0 matches or 0 O/U, save HTML for debugging.
    """
    results = []
    now = datetime.now(timezone.utc)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        page = await context.new_page()

        print(f"[{now.strftime('%H:%M:%S')}] Loading Pinnacle tennis...")
        try:
            await page.goto(PINNACLE_TENNIS_URL, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_selector(
                    '[data-test-id="event-row"], [class*="eventRow"], [class*="matchup"], div[class*="row"] button[class*="market"]',
                    timeout=20000,
                )
            except Exception:
                pass
            await page.wait_for_timeout(2000)
        except Exception as e:
            print(f"ERROR: Failed to load Pinnacle: {e}")
            if SAVE_HTML:
                HTML_DIR.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(HTML_DIR / f"error-{now.strftime('%Y%m%d-%H%M%S')}.png"))
            await browser.close()
            return []

        page_html = await page.content()
        if SAVE_HTML:
            HTML_DIR.mkdir(parents=True, exist_ok=True)
            html_path = HTML_DIR / f"pinnacle-{now.strftime('%Y%m%d-%H%M%S')}.html"
            html_path.write_text(page_html, encoding="utf-8")
            print(f"  Saved HTML to {html_path}")

        # ── Phase 1: Row selection via JS ──
        row_data = await page.evaluate("""
            () => {
                const rows = new Set();

                // Rows with over-under buttons (have O/U data)
                for (const ou of document.querySelectorAll('[data-test-id="over-under"]')) {
                    if (!ou.querySelector('button')) continue;
                    let el = ou.parentElement;
                    for (let i = 0; i < 10 && el; i++) {
                        if (el.querySelector('[data-test-id="moneyline"]') &&
                            el.querySelector('[data-test-id="over-under"]')) {
                            rows.add(el);
                            break;
                        }
                        el = el.parentElement;
                    }
                }
                // Rows with moneyline buttons (catches rows without O/U)
                for (const ml of document.querySelectorAll('[data-test-id="moneyline"]')) {
                    if (!ml.querySelector('button')) continue;
                    let el = ml.parentElement;
                    for (let i = 0; i < 5 && el; i++) {
                        if (el.querySelector('[data-test-id="moneyline"]')) {
                            rows.add(el);
                            break;
                        }
                        el = el.parentElement;
                    }
                }

                // For each row: outerHTML + league detection
                return [...rows].map(row => {
                    let p = row, bestLeague = null, bestLen = Infinity;
                    for (let i = 0; i < 20 && p; i++) {
                        const t = (p.textContent || '');
                        const upper = t.toUpperCase();
                        const hasWta = upper.includes('WTA') || upper.includes('WOMEN');
                        const hasAtp = upper.includes('ATP') || upper.includes("MEN'S") || upper.includes("MENS ");
                        if (hasWta && !hasAtp && t.length < bestLen) { bestLeague = 'WTA'; bestLen = t.length; }
                        if (hasAtp && !hasWta && t.length < bestLen) { bestLeague = 'ATP'; bestLen = t.length; }
                        const tag = p.tagName?.toUpperCase();
                        if (bestLeague && (tag === 'SECTION' || tag === 'H1' || tag === 'H2' || tag === 'H3')) break;
                        p = p.parentElement;
                    }
                    return { html: row.outerHTML, league: bestLeague || 'ATP' };
                });
            }
        """)

        if not row_data:
            # Fallback to old selectors
            old_rows = await page.query_selector_all(
                '[data-test-id="event-row"], [class*="eventRow"], [class*="matchup"], div[class*="gameInfo"]'
            )
            if not old_rows:
                old_rows = await page.query_selector_all('div[class*="row"]:has(button[class*="market"])')
            row_data = []
            for row in old_rows:
                try:
                    handle = await row.evaluate_handle(
                        "el => { let p = el.parentElement; while (p) { if (p.querySelectorAll('button').length >= 2) return p; p = p.parentElement; } return el; }"
                    )
                    el = handle.as_element()
                    html = (await el.inner_html()) if el else (await row.inner_html())
                    await handle.dispose()
                except Exception:
                    html = await row.inner_html()
                league = "ATP"
                try:
                    league = await row.evaluate("""
                        (el) => {
                            let p = el;
                            for (let i = 0; i < 20 && p; i++) {
                                const t = (p.textContent || '').toUpperCase();
                                const hasWta = t.includes('WTA') || t.includes('WOMEN');
                                const hasAtp = t.includes('ATP') || t.includes("MEN'S") || t.includes("MENS ");
                                if (hasWta && !hasAtp) return 'WTA';
                                if (hasAtp && !hasWta) return 'ATP';
                                p = p.parentElement;
                            }
                            return 'ATP';
                        }
                    """)
                except Exception:
                    pass
                row_data.append({"html": html, "league": league})

        if not row_data:
            print("WARNING: Found 0 match rows. Pinnacle may have changed layout.")
            if not SAVE_HTML:
                HTML_DIR.mkdir(parents=True, exist_ok=True)
                html_path = HTML_DIR / f"pinnacle-no-matches-{now.strftime('%Y%m%d-%H%M%S')}.html"
                html_path.write_text(page_html, encoding="utf-8")
            await browser.close()
            return []

        print(f"  Found {len(row_data)} candidate rows")

        # ── Phase 2: Total Games tab (O/U supplement) ──
        ou_scraped = []
        try:
            total_tab = None
            for sel in [
                'button:has-text("Total")',
                '[data-test-id*="total"]',
                'button:has-text("Total Games")',
                'a:has-text("Total")',
                '[class*="market"] button:has-text("Total")',
                'div[role="tab"]:has-text("Total")',
            ]:
                try:
                    tab = page.locator(sel).first
                    if await tab.count() > 0:
                        total_tab = tab
                        break
                except Exception:
                    continue

            if total_tab:
                await total_tab.click()
                await page.wait_for_timeout(2000)

                if SAVE_HTML:
                    totals_html = await page.content()
                    totals_path = HTML_DIR / f"pinnacle-totals-{now.strftime('%Y%m%d-%H%M%S')}.html"
                    totals_path.write_text(totals_html, encoding="utf-8")

                ou_rows_els = await page.query_selector_all(
                    '[data-test-id="event-row"], [class*="eventRow"], [class*="matchup"], div[class*="gameInfo"]'
                )
                if not ou_rows_els:
                    ou_rows_els = await page.query_selector_all('div[class*="row"]:has(button[class*="market"])')

                for ou_row in ou_rows_els:
                    try:
                        ou_html = await ou_row.inner_html()
                        ou_text = _text_from_html(ou_html)
                        if not ou_text or "/" in ou_text or " & " in ou_text:
                            continue
                        line_match = re.search(r"\b(1[5-9]|2[0-9]|3[0-5])\.5\b", ou_text)
                        if not line_match:
                            continue
                        line_val = float(line_match.group(0))
                        all_odds = re.findall(r"\b(\d+\.\d{2,3})\b", ou_text)
                        valid_odds = [float(x) for x in all_odds if 1.01 < float(x) < 20]
                        if len(valid_odds) < 2:
                            continue
                        p1, p2 = None, None
                        if " (Sets)" in ou_text or " (sets)" in ou_text:
                            parts = re.split(r"\s*\([Ss]ets\)\s*", ou_text)
                            names = [re.sub(r"\s+", " ", p).strip() for p in parts
                                     if p.strip() and not re.match(r"^\d", p.strip())]
                            if len(names) >= 2:
                                p1 = _clean_name(names[0])
                                p2 = _clean_name(names[1])
                        if p1 and p2 and 2 <= len(p1) <= 60 and 2 <= len(p2) <= 60:
                            ou_scraped.append({
                                "p1": p1, "p2": p2,
                                "line": line_val,
                                "over": round(valid_odds[0], 3),
                                "under": round(valid_odds[1], 3),
                            })
                    except Exception:
                        continue

                if VERBOSE:
                    print(f"  Total Games tab: found {len(ou_scraped)} O/U rows")
            else:
                if VERBOSE:
                    print("  No 'Total' market tab found (O/U may be inline).")
        except Exception as e:
            if VERBOSE:
                print(f"  Phase 2 O/U warning: {e}")

        await browser.close()

        # ── Parse each row ──
        for idx, rd in enumerate(row_data):
            row_html = rd.get("html", "") if isinstance(rd, dict) else ""
            league = rd.get("league", "ATP") if isinstance(rd, dict) else "ATP"
            if not row_html or len(row_html) < 20:
                continue
            try:
                # ── Structured parsing (preferred) ──
                ml_odds1, ml_odds2 = _parse_moneyline_from_html(row_html)
                ou_line, ou_over, ou_under = _parse_ou_from_html(row_html)

                # Extract player names from gameInfoMatchName div
                p1_name, p2_name = None, None
                name_match = re.search(
                    r'class="[^"]*gameInfoMatchName[^"]*"[^>]*>(.*?)</div>',
                    row_html, re.S
                )
                if name_match:
                    name_text = _text_from_html(name_match.group(1))
                    for sep in (" - ", " vs ", " v "):
                        if sep in name_text:
                            parts = name_text.split(sep, 1)
                            if len(parts) == 2:
                                p1_name = _clean_name(parts[0].strip())
                                p2_name = _clean_name(parts[1].strip())
                                break

                # Structured path: names + moneyline both found
                if p1_name and p2_name and ml_odds1 and ml_odds2:
                    if is_doubles(p1_name) or is_doubles(p2_name):
                        continue
                    match_data = {
                        "player1_name": p1_name,
                        "player2_name": p2_name,
                        "odds1": ml_odds1,
                        "odds2": ml_odds2,
                        "pinnacle_margin": compute_margin(ml_odds1, ml_odds2),
                        "ou_line": ou_line,
                        "ou_over": ou_over,
                        "ou_under": ou_under,
                    }
                else:
                    # Fall back to flat-text parser
                    match_data = _parse_row_from_html(row_html)
                    if not match_data:
                        continue
                    # Override with structured data where available
                    if ml_odds1 and ml_odds2:
                        match_data["odds1"] = ml_odds1
                        match_data["odds2"] = ml_odds2
                        match_data["pinnacle_margin"] = compute_margin(ml_odds1, ml_odds2)
                    if ou_line is not None:
                        match_data["ou_line"] = ou_line
                        match_data["ou_over"] = ou_over
                        match_data["ou_under"] = ou_under

                match_data["league"] = league
                results.append(match_data)

            except Exception as e:
                if VERBOSE and idx < 3:
                    print(f"  [debug] row {idx} parse error: {e}")
                continue

        # Merge Phase 2 O/U
        if ou_scraped:
            ou_merged = _merge_ou_into_results(results, ou_scraped)
            if VERBOSE:
                print(f"  Merged O/U into {ou_merged}/{len(results)} matches from Phase 2")

        # Dedup by player pair, keep lowest margin
        seen = {}
        for r in results:
            key = (r["player1_name"], r["player2_name"])
            if key in seen:
                if r["pinnacle_margin"] < seen[key]["pinnacle_margin"]:
                    seen[key] = r
            else:
                seen[key] = r
        results = list(seen.values())

        ou_count = sum(1 for r in results if r.get("ou_line") is not None)
        if results and ou_count == 0:
            print("  WARNING: 0/%d matches have O/U. Selectors may need updating." % len(results))
            if not SAVE_HTML:
                HTML_DIR.mkdir(parents=True, exist_ok=True)
                html_path = HTML_DIR / f"pinnacle-no-ou-{now.strftime('%Y%m%d-%H%M%S')}.html"
                html_path.write_text(page_html, encoding="utf-8")
                print(f"  Auto-saved HTML to {html_path}")

    print(f"  Scraped {len(results)} singles matches ({ou_count} with O/U)")
    return results


# ─── Supabase upsert ────────────────────────────────────────────────

def upsert_to_supabase(results: list):
    """Upsert scraped odds to bookmaker_odds_snapshot via Supabase REST API."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("WARNING: No Supabase credentials. Printing to stdout only.")
        return

    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    rows = []
    for r in results:
        league = (r.get("league") or "ATP").strip().upper()
        if league not in ("ATP", "WTA"):
            league = "ATP"
        rows.append({
            "capture_date": today,
            "captured_at": now.isoformat(),
            "bookmaker": "Pinnacle",
            "league": league,
            "player1_name": r["player1_name"],
            "player2_name": r["player2_name"],
            "odds1": r["odds1"],
            "odds2": r["odds2"],
            "pinnacle_margin": r["pinnacle_margin"],
            "ou_line": r.get("ou_line"),
            "ou_over": r.get("ou_over"),
            "ou_under": r.get("ou_under"),
        })

    if not rows:
        print("  No rows to upsert.")
        return

    atp_count = sum(1 for row in rows if row["league"] == "ATP")
    wta_count = len(rows) - atp_count

    conflict_cols = "capture_date,bookmaker,league,player1_name,player2_name"
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/bookmaker_odds_snapshot?on_conflict={conflict_cols}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, json=rows, headers=headers, timeout=30)
            if resp.ok:
                print(f"  Upserted {len(rows)} rows to bookmaker_odds_snapshot ({atp_count} ATP, {wta_count} WTA)")
                return
            elif resp.status_code == 409:
                print(f"  ERROR: 409 Conflict — missing UNIQUE constraint on bookmaker_odds_snapshot.")
                print(f"  Run in Supabase SQL Editor:")
                print(f"    ALTER TABLE bookmaker_odds_snapshot")
                print(f"      ADD CONSTRAINT bookmaker_odds_snapshot_upsert_key")
                print(f"      UNIQUE ({conflict_cols});")
                return
            else:
                print(f"  WARNING: Batch upsert failed (attempt {attempt}/{max_retries}): {resp.status_code} {resp.text[:200]}")
        except requests.exceptions.RequestException as e:
            print(f"  WARNING: Network error (attempt {attempt}/{max_retries}): {e}")

        if attempt < max_retries:
            wait = 2 ** attempt
            print(f"  Retrying in {wait}s...")
            _sleep(wait)

    print(f"  ERROR: All {max_retries} upsert attempts failed.")


# ─── Entry point ────────────────────────────────────────────────────

async def main():
    print(f"{'=' * 60}")
    print(f"  Pinnacle Tennis Odds Scraper")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Mode: {'DRY RUN' if DRY_RUN else 'LIVE'}")
    print(f"{'=' * 60}")

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("\nWARNING: Missing Supabase credentials.")
        print("  Ensure .env.local has NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
        if DRY_RUN:
            print("  (Continuing in dry-run mode without DB...)")
        else:
            print("  Either add credentials or use --dry-run.")
            sys.exit(1)

    results = await scrape_pinnacle()

    if not results:
        print("\nWARNING: No matches scraped. Possible causes:")
        print("  1. Pinnacle layout changed (check saved HTML in data/pinnacle-html/)")
        print("  2. No tennis matches scheduled today")
        print("  3. Network/geo-blocking issue (try with VPN)")
        sys.exit(0)

    if not DRY_RUN:
        upsert_to_supabase(results)

    # CSV backup
    csv_path = Path(f"data/pinnacle-odds-{datetime.now().strftime('%Y-%m-%d')}.csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "player1_name", "player2_name", "odds1", "odds2",
            "pinnacle_margin", "ou_line", "ou_over", "ou_under", "league"
        ])
        writer.writeheader()
        writer.writerows(results)
    print(f"  CSV backup: {csv_path}")

    # Summary
    ou_count = sum(1 for r in results if r.get("ou_line") is not None)
    atp = sum(1 for r in results if r.get("league", "ATP") == "ATP")
    wta = len(results) - atp
    print(f"\n  Summary: {len(results)} matches ({atp} ATP, {wta} WTA), {ou_count} with O/U")


if __name__ == "__main__":
    asyncio.run(main())
