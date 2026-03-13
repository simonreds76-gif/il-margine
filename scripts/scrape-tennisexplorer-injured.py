#!/usr/bin/env python3
"""
Scrape TennisExplorer "Injured players" and "Returning players" into CSV.

No auth. Output: data/injured-players-tennisexplorer.csv
Columns: scraped_at, date, player_name, player_slug, tournament, reason, source

Run:
  python scripts/scrape-tennisexplorer-injured.py
  python scripts/scrape-tennisexplorer-injured.py --max-pages 1   # one page per list
  pip install beautifulsoup4   # if needed
"""
from __future__ import annotations

import csv
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Install: pip install beautifulsoup4", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
OUT_CSV = ROOT / "data" / "injured-players-tennisexplorer.csv"
BASE = "https://www.tennisexplorer.com"
INJURED_URL = f"{BASE}/list-players/injured/"
RETURNING_URL = f"{BASE}/list-players/return-from-injury/"
REQUEST_TIMEOUT = 25
USER_AGENT = "Mozilla/5.0 (compatible; il-margine-scraper/1.0)"


def _parse_date(s: str) -> str | None:
    """Parse DD.MM.YYYY to YYYY-MM-DD."""
    s = (s or "").strip()
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if not m:
        return None
    try:
        d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        return d.isoformat()
    except ValueError:
        return None


def _normalize_reason(text: str) -> str:
    t = (text or "").strip().lower()
    if "walkover" in t or "walk over" in t:
        return "walkover"
    return "retired"


def _slug_from_href(href: str) -> str:
    """Extract player slug from /player/slug/ or /player/slug-123/."""
    if not href:
        return ""
    href = href.strip().rstrip("/")
    parts = href.split("/")
    for i, p in enumerate(parts):
        if p == "player" and i + 1 < len(parts):
            return (parts[i + 1] or "").strip()
    return ""


def _fetch_page(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.text


def _parse_table(html: str, source: str) -> list[dict]:
    """Parse the main injured/returning table; return list of row dicts."""
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    rows_out = []
    for table in tables:
        trs = table.find_all("tr")
        if len(trs) < 2:
            continue
        # Check header: first row should have Start, Name, Tournament, Reason
        header_cells = [th.get_text(strip=True) for th in trs[0].find_all(["th", "td"])]
        if not header_cells:
            continue
        if "Start" not in header_cells[0] and "Name" not in str(header_cells):
            continue
        for tr in trs[1:]:
            cells = tr.find_all("td")
            if len(cells) < 4:
                continue
            start_text = cells[0].get_text(strip=True)
            date_iso = _parse_date(start_text)
            # Name + link
            name_cell = cells[1]
            name_link = name_cell.find("a", href=True)
            player_name = (name_link.get_text(strip=True) if name_link else name_cell.get_text(strip=True)) or ""
            player_slug = _slug_from_href(name_link.get("href", "") if name_link else "")
            # Tournament
            tour_cell = cells[2]
            tour_link = tour_cell.find("a", href=True)
            tournament = (tour_link.get_text(strip=True) if tour_link else tour_cell.get_text(strip=True)) or ""
            # Reason (may contain tooltip junk)
            reason_text = cells[3].get_text(strip=True)
            reason = _normalize_reason(reason_text)
            if not player_name and not player_slug:
                continue
            rows_out.append({
                "date": date_iso or "",
                "player_name": player_name,
                "player_slug": player_slug,
                "tournament": tournament,
                "reason": reason,
                "source": source,
            })
        # Only parse the first matching table (the main list)
        break
    return rows_out


def _scrape_list(base_url: str, source_label: str, max_pages: int) -> list[dict]:
    all_rows = []
    for page in range(1, max_pages + 1):
        url = f"{base_url}?page={page}" if page > 1 else base_url
        try:
            html = _fetch_page(url)
        except requests.RequestException as e:
            print("  fetch %s: %s" % (url, e), file=sys.stderr)
            break
        rows = _parse_table(html, source_label)
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < 30:  # typical page size
            break
    return all_rows


def main():
    max_pages = 5
    if "--max-pages" in sys.argv:
        i = sys.argv.index("--max-pages")
        if i + 1 < len(sys.argv):
            max_pages = max(1, int(sys.argv[i + 1]))

    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_rows = []

    print("Scraping injured list...")
    injured = _scrape_list(INJURED_URL, "injured", max_pages)
    for r in injured:
        r["scraped_at"] = scraped_at
        out_rows.append(r)
    print("  %d rows" % len(injured))

    print("Scraping returning list...")
    returning = _scrape_list(RETURNING_URL, "returning", max_pages)
    for r in returning:
        r["scraped_at"] = scraped_at
        out_rows.append(r)
    print("  %d rows" % len(returning))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["scraped_at", "date", "player_name", "player_slug", "tournament", "reason", "source"]
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)
    print("Wrote %s (%d rows)" % (OUT_CSV, len(out_rows)))


if __name__ == "__main__":
    main()
